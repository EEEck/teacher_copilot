# Agent Architecture And Learnings

## Purpose

This is the current architecture and learning note for the KlassenPilot teacher
copilot. It explains how the agent should behave, how memory is organized, and
which lessons from AutoSci, Hermes, Honcho-style memory, and current agent
practice are relevant to this product.

Product scope lives in `product_vision.md`. Feature sequencing lives in
`../implementation_plans/product_backlog.md`. Reviewable behavior contracts live
in `agent_contracts.md`. The detailed file-by-file memory hierarchy lives in
`memory_hierarchy.md`. The repo-specific OpenAI Agents SDK review lives in
`agent_sdk_practices_review.md`.

## Core Operating Model

KlassenPilot should use one visible teacher copilot with clear workflow
boundaries, not a broad multi-agent graph.

- Planning is read-only with respect to the wiki during chat. Durable class
  materials promotion happens only on teacher plan save.
- Memory update can draft lesson memory, but durable wiki writes happen only
  through teacher-approved commit or explicit revise actions.
- The model receives explicit prompt layers (global teacher profile, active
  class core, workflow/runtime state), then browses only when the teacher
  request needs older or broader evidence.
- The backend owns class scope, allowed paths, write validation, and persistence.
- The agent should cite or name the class memory it uses.

This keeps teacher trust high: no silent writes, no invented class history, and
no opaque memory claims.

## Safety Architecture

KlassenPilot's first safety layer is deliberately small and orthogonal to the
agent flow. The reviewable policy lives in `teacher_agent_security_contract.md`;
the runtime policy is injected into model-facing instructions through
`TEACHER_AGENT_SECURITY_POLICY`.

The important boundary is source trust. Teacher messages are task requests, but
wiki pages, uploads, lesson notes, tool outputs, and raw evidence are untrusted
data. The agent may use them as evidence, but must not follow instructions found
inside them. This targets the main MVP risks from OWASP-style agentic threat
models: direct prompt injection, indirect injection through retrieved content,
memory/context poisoning, hidden write requests, and over-trusting the agent for
high-stakes student decisions.

The safety design is layered rather than prompt-only:

- Prompt policy sets the instruction hierarchy and labels untrusted evidence.
- Tool design limits capabilities; chat tools stay read-only unless a later
  contract adds explicit human approval for side effects.
- Backend validation owns durable writes, class scope, path safety, artifact
  readiness, and final teacher-visible output checks.
- Evals/red-team tests simulate adversarial prompts, malicious uploads/wiki
  content, unsafe tool requests, exfiltration attempts, and high-stakes misuse.

Heavier controls are deferred until the product needs them: SDK input/output
guardrails, full output sanitization, DeepTeam red-team automation, strong
student anonymization, and refactoring the legacy broad wiki tool surface.

Two deterministic backend safety guards now sit outside the model prompt:

- Final output safety validates teacher-visible replies and artifacts for
  obvious internal-data leakage patterns such as raw refs, prompt/trace labels,
  API-key-looking strings, and hidden-write claims. If blocked, the backend
  returns a safe fallback reply and preserves the previous artifact draft.
- Stream safety is mode-based. `APP_ENV=development` keeps raw local diagnostic
  streams. `APP_ENV=production` strips raw reasoning text, tool arguments, and
  tool outputs before SSE events reach the browser; tool names/status and final
  guarded outputs still flow.

## Agents SDK Fit

KlassenPilot uses the OpenAI Agents SDK where it is useful: model/tool looping,
streaming, function tools, and structured outputs. The application still owns
teacher/class scope, prompt assembly, runtime state, artifact persistence, and
approval flows.

This is an intentional SDK integration style:

- `Agent` definitions live in `backend/app/teacher_agent/agent.py`.
- `AgentRunner` uses async `Runner.run` / `Runner.run_streamed` in
  `backend/app/teacher_agent/agents.py`; FastAPI request handlers must not use a
  blocking run loop.
- `@function_tool` wiki tools are read-only during chat and receive class scope
  from backend-created context.
- Structured `output_type` models are the model/backend contract; backend code
  validates and merges state instead of trusting prose.
- Human approval for durable memory remains an API workflow, not a hidden
  side-effecting chat tool.

Prefer the current single-copilot shape until there is a concrete reason to add
handoffs, SDK sessions, sandbox execution, or side-effecting tools with SDK
approval interruptions. See `agent_sdk_practices_review.md` for the current
review and upgrade guidance.

## Memory Architecture

The product uses tiered class memory.

1. **Canonical wiki memory**
   Approved lesson records, saved plans, roll-ups, subject guides, open loops,
   misconceptions, and pseudonymous student observations.

2. **Compact class memory**
   Derived, size-budgeted pages under `wiki/classes/{class_id}/memory/`:
   `planning_brief.md`, `teaching_patterns.md`,
   `teaching_framework_adjustments.md`, `copilot_profile.md`, and
   `session_summaries.md`. Each page has a hard char budget in
   `MEMORY_PAGE_BUDGETS`, enforced at write AND inject time via
   `clamp_memory_page` (Hermes-style: small, high-signal, replace not append).
   `class_state.md` and `taught_so_far.md` were **retired**:
   "current unit" and "taught sequence" are deterministic projections of the
   canonical `course_state.md` / `timeline.md` rollups, so they live in exactly
   one home there and the sweep *reads* them rather than curating a second,
   drifting twin. This is the two-axis rule in practice — **retrieved-and-grows**
   (the canonical wiki, entered on demand) vs **assembled-and-budgeted** (curated
   memory, a task-scoped slice each context builder pulls): every fact has one
   home on exactly one axis.

3. **Workflow prompt layers**
   Read-only packs for base class chat, lesson planning, ingest, and review.
   These are rebuilt from the wiki and compact memory rather than stored as
   separate durable state. The planning chat uses `build_plan_context_slim`: a
   single deduped slice with class identity, recent misconceptions/lessons,
   canonical course state (current unit), bounded subject guide, planning brief,
   and teaching patterns (each component clamped to budget) instead of the
   stacked, duplicated `build_plan_context` pack — so there is no blunt
   end-of-pack truncation. The legacy `_CHAT_CONTEXT_CHARS = 14_000` clip caused
   random tail loss and is removed. The ingest chat now mirrors this with
   `build_ingest_context_slim`, a single deduped logging-oriented slice instead
   of index + base + ingest + embedded query-pack stacking. Limits are
   centralized in `app/context_limits.py` (see
   `context_management.md`).

   Current live planning and Update Memory calls compose explicit layers through
   `prompt_assembly.py`: Teacher Layer, Active Class Core, and workflow-specific
   runtime/task sections. The Active Class Core loads exactly one class and all
   compact `wiki/classes/{class_id}/memory/*.md` pages; the current compatibility
   path also includes the subject guide selected by
   `wiki.get_class(class_id).subject`. Legacy stacked pack builders are
   compatibility/debug views, not the model-facing contract.

   The target subject-know-how design keeps the two dimensions explicit:
   `build_base_assistant_context_trace()` always composes the global Teacher
   Layer, class-only Active Class Core, and compact subject/grade/branch routing.
   Planning and differentiation then add
   `build_active_subject_expert_context_trace()`, which injects the compact
   `chemie.md` front door, the selected immutable Grade 9 key summary, the
   bounded class adjustment page, and the source TOC. These are composed once
   at runtime; no generated profile is persisted. Update Memory receives subject
   identity/routing only by default, preserving its focus on what happened in
   class.

   Planning also receives a bounded trusted-source profile: class branch/grade
   plus an allow-listed source TOC. It does not receive curriculum bodies. The
   planner progressively calls typed list/search/read source tools when making
   an official curriculum claim; section reads are captured as raw evidence and
   their provenance is retained in `PlanRuntime.consulted_sources`.

4. **Runtime session memory (lesson planning and update memory)**
   `PlanRuntime` (in `planning_state.py`): backend-owned `SessionState`,
   `LessonPlanningState`, compact `EvidenceBrief`s with a raw-output store
   behind `raw_ref` (progressive exposure via `get_raw_evidence`), consulted
   trusted-source sections, and
   accumulated `MemoryCandidate`s. The model proposes `state_patch` updates;
   backend code validates and applies them. Runtime state is persisted on the
   session and re-injected compactly each turn so the verbatim window can be
   trimmed (`plan_history_turns`) without losing decisions/constraints.

   `MemoryRuntime` (in `memory_update_state.py`) applies the same pattern to
   Update Memory: target/date identification, intent, phase, lesson-result
   category progress, compact evidence briefs, raw refs, and accumulated
   `MemoryCandidate`s live on the session until the teacher approves the normal
   memory commit. Its model-facing context is rendered as separate `Memory
   target state`, `Memory session state`, `Lesson result state`, `Memory
   evidence briefs`, and `Memory candidates` sections. This keeps the workflow
   free-agent from the teacher's perspective while preserving backend-owned
   validation and no hidden wiki writes. Timeline/detail entry points can pass a
   structured date/intent hint into the same ingest session start call; the
   backend seeds the target and draft from canonical lesson detail when a
   planned or taught lesson is found. Unknown hinted dates may seed a dated
   draft, but remain unconfirmed and stay in target discovery.

5. **Shared executive verification runtime**

   Every registered artifact workflow also receives one `ExecutiveRuntime`
   owned by `ArtifactSession`, separate from its workflow-specific runtime.
   It records authority-aware assumptions and advisory/blocking findings across
   turns. A small deterministic resolver checks class, student, and lesson
   references against committed wiki indexes; existing search/read tools remain
   responsible for broader teaching concepts and history.

   ```text
   ArtifactSession
   ├── ExecutiveRuntime
   ├── PlanRuntime | MemoryRuntime | future workflow runtime
   ├── authority-labeled wiki context
   └── shared verification + workflow-specific tools
   ```

   Open blocking findings prevent readiness but do not discard the foreground
   artifact. Advisory findings allow work to continue. Every session is
   capability-scoped to one active class: the resolver is active-class-only,
   and neither the model nor the UI may offer a class switch as recovery.
   Unresolved consequential facts are held out of the artifact and durable
   candidates until an active-class correction is confirmed. A teacher question
   about prior coverage retrieves and answers from the active-class record; it
   is not itself a candidate update. Durable-write fingerprint verification is
   a later boundary and remains separate from this proactive chat loop.

   The first workflow-specific pack is Plan verification: deterministic package,
   source-read, and timing rows are immediate; a bounded no-tools economy-model
   report follows after the draft is returned. Its report is revision-bound and
   lives inside `ExecutiveRuntime`, not in the lesson artifact or durable wiki.
   It is teacher-facing through the Plan draft channel, while full inputs stay
   trace-only. Advisory scope/pedagogy notes never block; only a completed
   severe-safety hold for the same Markdown fingerprint prevents saving.

   The second pack is Update Memory integrity. It runs deterministically on
   every diary edit and again immediately before proposal or commit. It compares
   a confirmed target lesson date with the diary date and accepts student
   observations only when they use known active-class `S-###` roster IDs. A
   malformed ID (for example `S006`), an unknown ID, or a name-style student
   label is a blocking correction request. The pack is deliberately not an LLM
   quality review: it preserves the teacher's Markdown, names the exact
   correction, and clears itself when the same draft is repaired. Its compact
   report stays in `ExecutiveRuntime` and trace/debug output; the normal
   teacher path sees the existing concise write-blocking recovery message.

6. **Profiles (four clearly-scoped files)**
   - `user.md` (`wiki/teacher_profile.md`, GLOBAL): teacher communication style,
     stable preferences, default lesson structure, and only teacher-confirmed
     professional context that materially improves future assistance.
   - `teaching_patterns.md` (class + subject): how this class learns and which
     approaches work/fail (the class learning profile).
   - `copilot.md` (`copilot_profile.md`, class): copilot working agreement only.
   - `teaching_framework_adjustments.md` (class + subject/grade): bounded
     teacher-approved replacement/refinement rules. Prompt assembly combines it
     with the immutable shared Grade 9 framework in memory.
   Durable writes go through teacher-approved memory endpoints
   (refresh/propose/apply), never silently from chat.
   Lesson-plan save surfaces the current runtime state and accumulated memory
   candidates so the UI can call the profile-proposal skill after the plan is
   saved, then present suggested `user.md` / `copilot.md` updates for approval.
   After an approved Update Memory commit, the backend returns a
   `class_memory_proposal` so class evolution can be reviewed and applied
   immediately without waiting for the weekly sweep.
   Update Memory also surfaces accumulated candidates after the teacher-approved
   lesson-memory commit, so subtle chat signals such as repeated communication
   preferences can be reviewed for `teacher_profile.md`, `copilot_profile.md`,
   `teaching_patterns.md`, or `planning_brief.md`. `canonical_wiki` remains
   review-only in this path. A recommended future extension is explicit,
   teacher-requested professional context in `teacher_profile.md` (for example
   under `Professional context`) with verbatim provenance and the same
   teacher-review requirement as preferences. Casual disclosures remain session
   context, not durable memory. Profile context is advisory; it never expands
   the active class, available tools, or durable-write authority.

7. **Candidate ledger and Memory Sweep (Memory V4)**
   Planning and Update Memory chats capture review-only durable facts. The
   **primary path is an explicit
   `remember(target, content, speech_act, scope, quote, routing_reason)` tool** the
   model calls the moment the teacher gives a standing instruction. This
   replaced a passive `memory_candidates` output field the
   model reliably forgot to fill while doing planning/ingest work — the measured
   "emission gap" (durable requests understood but never routed, the original V2
   capture-bug shape). The shift matches the 2026 self-editing-memory pattern
   (Mem0 / Letta / hermes): capture is a tool call the model *decides* to make,
   which keeps it model-swappable and inspectable. The tool's deterministic
   guard (`validate_remember_call`) grounds only in ground truth — a supported
   preference target and **verbatim quote provenance** (the quoted sentence must
   appear in the teacher's real message) — and returns a structured, model-facing
   error so the agent self-corrects and retries within the turn; it never guesses
   intent. `routing_reason` is an internal one-sentence rationale for traces and
   eval diagnostics, not teacher-facing reasoning and not a persistence verdict.
   The passive field remains as a fallback. Whichever path emits, the
   candidate flows through the same review pipeline: candidates must be grounded
   in the teacher's own words (never the agent's own artifact output), silence is
   the normal outcome of a turn, and `teacher_explicit`/high status requires a
   verified quote plus target lane policy — the backend downgrades unsupported
   explicit claims to weak inferred signals (`discipline_memory_candidates`),
   which remains the authoritative fast-lane decision at persist time regardless
   of how the candidate was emitted. Persistence goes through deterministic
   insert-time folding (`insert_with_folding`): sections are normalized onto a
   fixed per-target vocabulary, same-session exact duplicates are rejected as
   noise, cross-session exact or near duplicates (stemmed overlap coefficient,
   calibrated on recorded beta data) join the matched claim's cluster as
   reinforcement, and re-captures of applied/rejected content are neutralized
   on arrival. The ledger stays episodic working memory, not prompt-facing
   truth and not durable wiki memory.

   Between the ledger and the sweep sits a deterministic priority gate
   (`memory_gate.py`, OpenClaw-inspired): explicit teacher asks receive the
   highest priority when provenance is verified, inferred claims receive
   reinforcement/occasion metadata, and stale unreinforced singletons expire
   silently. Held singletons still reach the second judge with lower priority;
   they are not silently hidden. Teacher rejections have teeth — a rejected
   cluster resurfaces only on a fresh explicit ask.

   Memory Sweep itself is teacher-triggered and runs ONE consolidation call on
   the strongest reasoning model (`OPENAI_SWEEP_MODEL`; mini models fail the
   add-vs-adjust judgment — verified live). The call sees everything at once:
   reinforced and held singleton claims with priority metadata, every
   in-scope memory file with its bullets enumerated by ephemeral ids, recently
   applied and rejected texts, page-budget usage, and today's date. It returns
   mem0-style ID-referenced write operations (`add` / `update(id)` /
   `delete(id)` / `none`) plus a semantic `sweep_action` (`promote`, `merge`,
   `already_covered`, `downgrade`, `reject`, or `needs_review`). Backend
   validation is structural: every claim is accounted for exactly once,
   referenced ids must exist, operations cannot cross their claim targets, and
   updates quote their bullet — no lexical token-overlap second-guessing of the
   model's semantics; teacher review is the safety net. A failed run degrades
   to one plain-language notice, never per-candidate fallback cards. Semantic
   actions map onto review cards (update → adjust with the referenced bullet as
   `replaces_content`; downgrade/reject/needs_review stay review-only), and the
   sweep brief UI pins explicitly requested changes first. The MBB/executive
   communication scenario remains a live trace and regression test, not a
   hardcoded system-prompt alias or backend synonym rule.

Evaluation follows the same separation of concerns. Deterministic tests pin
class scope, exact-draft write gates, and held-back artifact facts. Opt-in live
goldens are derived from anonymized real teacher behavior and exercise full
multi-turn context; an LLM judge evaluates the teacher-facing contract against
the relevant active-class baseline. A complete draft and an accepted draft are
distinct states, and UI scaffolding must not be judged as teacher-created
artifact content.

The wiki remains the source of truth. Compact memory is derived and rebuildable.
Profiles should be small, stable, correctly scoped, and source-backed where
possible.

Wiki/input reconciliation follows the same authority split. The committed wiki
is the factual baseline; teacher input that contradicts it is a proposed change
that needs clarification before write. Deterministic code should detect factual
mismatches such as non-roster student IDs/names, while the model owns the
teacher-facing clarification and the teacher confirms the resolution.

## Retrieval Architecture

The Karpathy-style wiki is the readable map; deterministic retrieval tools are
the compass.

For larger wiki memory, the agent should not rely on a flat dump of pages or an
opaque vector top-k result. It should:

- start from compact class context
- use `search_memory` as a deterministic pathfinder for broad topic requests
- return source-bearing ranked results with `path`, `kind`, `title`, `snippet`,
  `score`, `matched_terms`, and `source`
- drill into specific lessons or memory pages when snippets are not enough
- synthesize only after selected evidence is loaded

AutoSci's useful pattern is deterministic, purpose-specific retrieval:
weighted corpus fields, stable scoring, source paths, evidence packets, and
small compiled context packs. We should borrow that discipline, not the full
research graph or multi-agent orchestration.

## Tool Architecture

The planning agent should choose tools from clear capability descriptions, not
from brittle keyword triggers in the system prompt.

OpenAI's function-calling guidance treats tool names, descriptions, parameter
descriptions, and output shapes as part of the model interface. The practical
standard for KlassenPilot is the "intern test": a human should be able to choose
the right tool using only the tool schema and the agent job description.

Design rules:

- Keep the planning tool surface small and obvious. Six focused read tools is
  acceptable; a large surface should be grouped into namespaces or higher-level
  tools.
- Keep the update-memory tool surface equally purpose-specific. It uses
  `list_memory_targets` for date/lesson discovery, `read_memory_target` for one
  planned or taught lesson, and the shared memory search/page/raw-evidence
  pattern for continuity.
- Capture is a tool, not a passive field. `remember(target, content,
  speech_act, quote, routing_reason)` is the one write-capable tool on both chat
  surfaces, and even it writes nothing durable: it stages a review-only
  candidate grounded in the teacher's verbatim words, with a deterministic guard
  that returns a structured error for the model to retry. Making
  the durable-memory decision an explicit, salient tool call is what closed the
  emission gap; `routing_reason` gives live evals and traces a compact rationale
  for wrong-target failures without exposing model reasoning to teachers.
- Put capability semantics in tool docstrings and output shapes. Example:
  `list_lessons` is the sequence-map tool; `read_lesson_range` is the
  multi-lesson evidence tool; `search_memory` is the broad topic pathfinder.
- Keep the prompt policy at the workflow/evidence level: browse when the task
  needs source-backed class evidence not explicit in the compact slice; choose
  tools by information need, not by hardcoded phrases.
- Use backend code for what the backend already knows: class id, selected wiki
  root, allowed paths, current artifact, raw evidence refs, and persistence.
- Prefer a higher-level tool when a teacher task naturally implies a repeated
  sequence of low-level calls. A future `retrieve_lesson_history(topic, count,
  purpose)` would be better than repeatedly asking the model to coordinate
  `list_lessons` plus several `read_lesson` calls.

This is the lesson from the FCKW trace review: after moving behavior from a
hardcoded "last N lessons" prompt rule into clearer tool descriptions, the
model selected `read_lesson_range` earlier and produced cleaner teacher-facing
output.

## Workflow Context

The agent should use purpose-specific prompt layers, not whole-wiki dumps.

- `teacher_context`: global teacher profile only.
- `active_class_core`: one active class, selected subject guide, and compact
  class memory pages.
- `plan workflow context`: current plan artifact, planning session state,
  lesson-planning state, compact evidence briefs, and recent conversation.
- `ingest workflow context`: update-memory task hints, current diary artifact,
  target/session/result runtime state, compact evidence briefs, and recent
  conversation.
- `review_context` or future workflows: build a separate overview/task layer
  instead of overloading active-class core.

The teacher should not have to restate class state in each chat. The model
should receive enough context to start well and use tools for the long tail.

## Best-Practice Learnings

- Keep active context small and high-signal.
- Prefer just-in-time retrieval over loading the whole wiki.
- Separate short-term conversation state from long-term class memory.
- Keep memory writes deterministic, bounded, and auditable.
- Let LLM synthesis propose state/memory updates; let backend code validate,
  merge, version, and persist only allowed paths.
- Treat explicit teacher corrections as high-priority memory.
- Prefer stable reusable facts over raw session logs.
- Keep student-specific sensitive details out of broad profile memory.
- Use source-bearing retrieval so the teacher can audit the plan.
- Add embeddings or vector search only after deterministic wiki retrieval shows
  measurable limits.
- Treat tool descriptions as product surface. Improve tool names, descriptions,
  parameter meanings, and structured outputs before adding brittle prompt
  triggers.
- Trace prompt assembly and tool calls during development. The useful debug
  view is source -> function -> compacted text -> prompt/tool context, not only
  final output quality.
- Keep teacher-facing artifacts clean. Evidence briefs and raw refs belong in
  runtime state / trace diagnostics; lesson plans should cite sources naturally
  rather than include debug evidence blocks.
- Use SDK features only at the boundary they improve: sessions for persistent
  conversation state, guardrails for automatic validation, human review for
  side-effecting tool calls, and traces/evals for behavior inspection. Do not
  add them just because they exist.
- Use candidate-led durable memory updates. Active chat/session state can catch
  subtle behavior changes, but durable memory promotion should happen as a
  separate teacher-reviewed step after the artifact save or memory commit.
  This matches the OpenAI SDK separation between resumable conversation state
  and distilled reusable memory, and the Hermes pattern of small curated memory
  files rather than transcript stuffing.
- Treat raw memory signals and curated memory as different lifecycle phases:
  observe into ledger evidence, normalize into claim groups, stage review cards,
  consolidate with teacher approval, then inject only relevant curated memory.
  Do not collapse these phases back into transcript replay or one-row/one-card
  promotion.

## Deliberate Non-Goals

- Full AutoSci graph or edge schema.
- Multi-agent review pipeline.
- Agents SDK handoffs or sandbox agents for normal lesson planning.
- External Honcho service as the default memory layer.
- Vector database as the default retrieval path.
- General web search as default class-memory retrieval. A future trusted-source
  search tool can support special topics, resources, news, quizzes, or essays,
  but it should stay separate from class wiki memory.
- Autonomous wiki writes.
- Raw-source fallback as normal planning behavior.
- Grading automation without teacher review.

## Implementation Map

- Agent prompts: `backend/app/teacher_agent/prompts.py`
- Agent tools: `backend/app/teacher_agent/tools.py`
- Agent runner: `backend/app/teacher_agent/agents.py`
- Structured outputs: `backend/app/teacher_agent/models.py`
- Planning runtime context manager: `backend/app/teacher_agent/planning_state.py`
- Update-memory runtime context manager: `backend/app/teacher_agent/memory_update_state.py`
- Shared runtime render helpers: `backend/app/teacher_agent/runtime_render.py`
- Workflow spec contract: `backend/app/teacher_agent/workflow_contract.py`
- Plan-session trace bundle: `GET /api/classes/{id}/plan/sessions/{session_id}/trace`
- Prompt assembly source of truth: `backend/app/teacher_agent/prompt_assembly.py`
- Prompt trace compatibility wrapper: `backend/app/teacher_agent/prompt_trace.py`
- Wiki facade: `backend/app/teacher_agent/wiki/store.py`
- Wiki retrieval: `backend/app/teacher_agent/wiki/search.py`
- Class materials registry: `backend/app/teacher_agent/wiki/materials.py`
- Materials OCR / scratch: `backend/app/services/materials_ocr.py`,
  `materials_ocr_prompts.py`, `materials_ocr_packaging.py`, `materials_scratch.py`
- Context packs (incl. `build_plan_context_slim` / `build_ingest_context_slim`): `backend/app/teacher_agent/wiki/context_packs.py`
- Compact memory + budgets/clamp + bounded profile writers: `backend/app/teacher_agent/wiki/memory.py`
- Shared memory candidate capture + discipline + `remember(...)` validation (`validate_remember_call`): `backend/app/teacher_agent/memory_capture.py`
- `remember(...)` capture tool wiring: `backend/app/teacher_agent/tools.py` (`create_remember_tool`)
- Wiki/input reconciliation eval scaffold: `backend/tests/evals/test_klassenpilot_wiki_reconciliation.py`
- Post-save `/memory/apply` ledger-close: `backend/app/api/routes.py` (`apply_memory`)
- Memory candidate ledger + insert-time folding: `backend/app/services/memory_candidate_ledger.py`
- Promotion gate and silent decay: `backend/app/services/memory_gate.py`
- Single-call Memory Sweep consolidation (Mem V4 second judge): `backend/app/services/memory_sweep.py`
- Memory V4 design, learnings, and test strategy: `docs/mem_v4/`
- Memory refresh/propose/apply endpoints: `backend/app/api/routes.py`
- Wiki schema rules: `backend/teacher_wiki/AGENTS.md`

## Testing Expectations

Agent and memory tests should stay offline and deterministic.

Use focused backend tests when changing agent memory or retrieval:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_wiki_tools.py tests\test_wiki_search.py tests\test_api_plan.py tests\test_prompts.py tests\test_api_stream.py tests\test_wiki_context_packs.py tests\test_memory_compaction.py tests\test_plan_context_manager.py tests\test_memory_skills.py
```

From repo root, use:

```powershell
.\scripts\test.ps1
```
