# Context Management

How KlassenPilot assembles agent prompts, why we removed blunt character caps,
how this maps to the OpenAI Agents SDK conversation strategies, and where to
tune limits.

## The bug we fixed

Before the planning context manager, ingest and some plan paths did:

```python
context = build_context_package(...)  # stacked index + base + mode pack
instructions = ... + context[:14_000]
```

That was meant as a cheap guard when someone confused **14k tokens** with
**14k characters**. In practice it:

- cut arbitrary **tail** content from a stacked pack (misconceptions, open loops,
  recent lessons — whatever happened to fall after char 14,000)
- caused the copilot to **forget** constraints mid-session
- behaved unlike ChatGPT or Claude, which do not slice composed system prompts
  at a fixed character boundary

**Plan chat no longer uses this pattern.** It composes a global teacher layer,
one active-class core layer, and structured `PlanRuntime` state instead.

## How ChatGPT / Claude actually manage context

They do not rely on `prompt[:14000]`. Common patterns (also in the OpenAI Agents
SDK cookbooks):

| Technique | Purpose |
|-----------|---------|
| **Session history trimming** | Keep the last N turns; older nuance moves to summaries or structured state |
| **Compaction at phase boundaries** | Summarize completed work when context grows — not mid-sentence at 95% fill |
| **Structured working state** | Decisions, goals, artifact status live outside the raw transcript |
| **Curated memory injection** | Small, purpose-built slices — not whole-repo dumps |
| **Tool progressive exposure** | Compact briefs in context; raw detail on demand |
| **Bounded durable memos** | Hermes-style profile pages with explicit size budgets |

Large context windows (e.g. GPT-5.x ~200k+ tokens) remove the *need* for blunt
cuts. They do **not** remove the need for **signal curation** — noisy prompts
still hurt tool accuracy and coherence.

References:

- [OpenAI Agents SDK: running agents](https://developers.openai.com/api/docs/guides/agents/running-agents)
- [OpenAI Agents SDK: agent definitions](https://developers.openai.com/api/docs/guides/agents/define-agents)
- [OpenAI session memory & trimming](https://github.com/openai/openai-cookbook/blob/main/examples/agents_sdk/session_memory.ipynb)
- [OpenAI compaction at workflow boundaries](https://developers.openai.com/cookbook/examples/agents_sdk/building_reliable_agents_memory_compaction)
- [OpenAI context personalization (structured state)](https://developers.openai.com/cookbook/examples/agents_sdk/context_personalization)

## SDK Conversation Strategy

OpenAI's Agents SDK supports multiple continuation strategies: application-owned
history/state, SDK sessions, OpenAI conversation IDs, or response-to-response
continuation. The practical rule is to choose one strategy per conversation.

KlassenPilot currently chooses application-owned state:

- `ArtifactSessionService` stores the chat messages, artifact markdown, status,
  debug events, and mode-specific runtime object.
- `PlanRuntime` stores lesson-planning working state, evidence briefs, raw refs,
  and memory candidates.
- The model sees only the compact rendered state, current artifact, evidence
  briefs, and recent conversation window.

This is the right strategy for the MVP because the backend must own teacher
approval boundaries, wiki scope, artifact drafts, and trace assembly. If the app
later needs multi-worker or restart-resilient sessions, migrate deliberately:
persist `ArtifactSession` / `PlanRuntime` in app storage first, and only adopt
SDK sessions if they replace the local replay strategy rather than duplicating
it.

## KlassenPilot strategy (by workflow)

### Two-dimensional base context (current assembly and target refinement)

The model should experience one personalized executive assistant, but the
prompt must keep authority boundaries visible. We therefore assemble two
orthogonal dimensions rather than mixing all wiki content into one class page:

1. **Teacher and class dimension** - the global teacher profile, active class
   identity/course state, class signals, compact class memory, and the
   workflow's backend-owned runtime state.
2. **Subject-expert dimension** - compact subject/grade/branch routing for every
   class workflow, plus the full active subject expert for pedagogical work.

The current code already injects `build_teacher_context_trace()` and
`build_active_class_core_context_trace(class_id)` into the main prompts. The
teacher profile is intentionally a separate **Teacher Layer**, not a field
inside Active Class Core: it is global advisory context, while Active Class
Core is class-scoped factual/empirical context. Keeping them separate prevents
teacher preferences from being mistaken for class facts, while still placing
the teacher profile in every main prompt.

The subject-expert refinement adds two traceable builders:

```python
build_active_subject_expert_context_trace(store, class_id, purpose)
build_base_assistant_context_trace(store, class_id, purpose)
```

`build_base_assistant_context_trace` is the canonical composition boundary. It
always contains the Teacher Layer, Active Class Core, and a compact
subject/grade/branch routing block. For planning and other pedagogical
workflows it adds the active subject expert: the compact `chemie.md` front door,
the compiled inherited class profile, and the bounded curriculum/source TOC.
It never injects the Grade 9 summary separately from the class profile.

### Inherited subject expert

The class-level subject expert is derived, not copied into an independently
editable memory page. At class setup, `subject=chemie`, `grade=9`, and
`branch=NTG` select the shared framework; the compiler records `inherits`,
`source_index`, base revision/hash, `authority=teacher_adjusted_class_profile`,
and `generated_at` in
`wiki/classes/chemie_9b_2026_27/memory/teaching_framework_profile.md`.
Teacher-approved adjustments are reapplied when the shared Grade 9 library is
updated. Prompts inject the compiled profile as the effective pedagogical
contract; detailed framework pages remain progressive tool reads.

The purpose-specific subject addition is:

| Workflow | Base context | Subject-expert addition |
|---|---|---|
| Plan chat | Teacher Layer + Active Class Core + runtime | `chemie.md` + compiled Grade 9 NTG profile + source TOC; detailed framework/source reads on demand |
| Plan opening | Slim Teacher/Class routing | Subject/grade/branch routing and compact `chemie.md`; profile after planning begins |
| Differentiation | Same as Plan chat | Same compiled profile; detailed differentiation/representation pages on demand |
| Discuss | Teacher Layer + Active Class Core + discussion state | Add `chemie.md` and profile when the question is pedagogical; otherwise keep class-focused |
| Update Memory | Teacher Layer + Active Class Core + MemoryRuntime/task context | Subject identity/profile identity only by default; no detailed teaching framework |
| Class brief | Teacher Layer + Active Class Core | No framework unless the requested brief requires subject interpretation |
| Verification | Active Class Core + verification state | Authority labels/source scope only; read exact sources for disputed claims |

### Lesson planning chat (primary)

1. **Structured state** — `SessionState`, `LessonPlanningState` persisted on
   backend-owned `PlanRuntime`; the model proposes `state_patch` updates and
   backend merge rules prevent empty fields from wiping accumulated state.
2. **Production skill** — the provisional `PLAN_SKILL` and short Chemistry
   prompt are transitional. The target loads the Anthropic-derived planning
   skill, Bavaria Chemistry subject reference, and differentiation skill as
   one mandatory production procedure.
3. **Teacher layer** — `build_teacher_context_trace()` loads only
   `wiki/teacher_profile.md`.
4. **Active class core** — `build_active_class_core_context_trace(class_id)`
   loads class identity and all existing
   `wiki/classes/{class_id}/memory/*.md` pages, each clamped via
   `MEMORY_PAGE_BUDGETS`. The current implementation still includes the
   selected subject guide here for compatibility; the subject-expert builder
   described above will move that content into its own labeled layer. It also
   includes up to three recent lesson summaries from the snapshot.
5. **Active subject expert** — compiled Chemistry 9 NTG profile plus compact
   subject front door and source TOC; detailed framework/source pages on demand.
6. **Planning orientation** — bounded recent sequence, misconception priorities,
   open loops, and planning brief without duplicate query-pack injection.
7. **Full lesson plan** — current `lessonplan.md` injected each turn (no char
   cap by default).
8. **Verbatim window** — last `plan_history_turns` teacher turns in the user
   message (default 8).
9. **Evidence briefs** — compact tool summaries; raw outputs behind `raw_ref`.
10. **No blunt 14k clip** on composed instructions.

The planning-specific orientation should add only the compact recent taught
sequence, misconception priorities, open loops, and planning brief. The existing
`build_planning_query_pack()` contains those fields and a six-lesson sequence,
but is not currently injected into the live Plan prompt; detailed history is
available through `list_lessons`, `read_lesson`, and `read_lesson_range`. Do not
inject both the full query pack and the same fields from Active Class Core.

### Ingest / memory update

Uses the same `build_teacher_context_trace()` and
`build_active_class_core_context_trace(class_id)` layers as planning, then adds
a lightweight Update Memory task layer for lesson logging. The task layer may
include bounded continuity hints such as previous lesson, roster excerpt, and
the most recent saved plan. It does not stack index + base + ingest +
query-pack layers, and it does not inject `teacher_wiki/AGENTS.md`, full
roll-ups, full student files, or full lesson files by default. Blunt
end-truncation remains **disabled by default** (`ingest_context_backstop=0`).

Update Memory now mirrors planning's runtime-state strategy:

1. **Teacher layer** — global `teacher_profile.md`.
2. **Active class core** — one active class and all compact class `memory/*.md`
   pages. The current compatibility path also carries the selected subject
   guide; the target path supplies only subject identity/profile identity to
   Update Memory unless interpretation requires more.
3. **Task context** — bounded previous lesson, roster excerpt, and saved-plan
   continuity.
4. **Split runtime state** — target state, session decisions/questions,
   lesson-result category state, and compact evidence briefs are rendered as
   separate traceable sections.
5. **Verbatim window** — last `ingest_history_turns` teacher turns in the user
   message (default 8); older decisions must survive in `MemoryRuntime`.

### Shared memory-classification context pack

Durable-memory classification uses a shared **compact context pack** across all
three chat workflows. It is assembled from:

1. the current teacher message verbatim;
2. the last eight teacher turns plus interleaved assistant replies;
3. the workflow's typed runtime state;
4. the compact Teacher Layer and Active Class Core;
5. the current plan or diary when the workflow has one;
6. task-specific continuity such as the ingest target/lesson context;
7. compact evidence briefs and review-only memory candidates.

The workflow-specific runtime state is the structured summary mechanism. Plan
uses `PlanRuntime`, Update Memory uses `MemoryRuntime`, and Class Discussion
uses `ClassDiscussionRuntime` with `ClassDiscussionState`. The model proposes a
typed `state_patch`; the backend merges it rather than accepting a full model
snapshot. This is commonly called backend-owned structured state or a rolling
structured summary, not a raw transcript summary.

The model uses this pack to classify speech act and scope. The backend still
uses the current teacher message as the provenance authority for exact quote
checks. Context can resolve “that”, standing-vs-temporary intent, and block or
class scope; it cannot turn assistant/tool/wiki text into teacher evidence.

The context pack must be traceable by section and source. Raw tool results stay
behind `raw_ref` and are fetched only when needed. Full chat-history storage is
still out of scope.

Class Discussion has no lesson-plan artifact. Its compact state is:
`current_focus`, `answered_questions`, `key_observations`, `confusion_signals`,
`open_questions`, and `next_best_actions`, plus evidence briefs and candidates.

### Durable wiki memory (Hermes-style)

`MEMORY_PAGE_BUDGETS` in `wiki/memory.py` cap each memory page at write and
inject time. This is intentional — small high-signal memos, not session
forgetting.

## Central configuration

**Code:** `backend/app/context_limits.py` (policy + `apply_char_limit`)

**Settings:** `backend/app/config.py` (env-overridable via pydantic-settings)

| Setting | Default | Meaning |
|---------|---------|---------|
| `plan_history_turns` | 8 | Verbatim teacher turns in planning user message |
| `plan_current_chars` | **0** | Max chars for lessonplan in system prompt; 0 = unlimited |
| `plan_instructions_backstop` | **0** | Emergency cap on full plan instructions; 0 = disabled |
| `ingest_context_backstop` | **0** | Emergency cap on ingest context pack; 0 = disabled |
| `ingest_history_turns` | 8 | Verbatim teacher turns in ingest user message |
| `memory_capture_batch_max_candidates` | 8 | Operational per-turn capture guard; overflow becomes one review bundle |
| `plan_opening_context_chars` | **0** | Plan opening agent context; 0 = unlimited |
| `compile_context_chars` | **0** | Compile diary context; 0 = unlimited |
| `plan_lesson_context_chars` | **0** | One-shot plan lesson context; 0 = unlimited |
| `lint_context_chars` | **0** | Wiki lint context; 0 = unlimited |
| `profile_propose_field_chars` | **0** | Profile proposal field cap; 0 = unlimited |
| `memory_compact_source_chars` | **0** | Memory compaction source packet; 0 = unlimited |
| `ingest_previous_lesson_chars` | **0** | Previous lesson excerpt in slim ingest context; 0 = unlimited |
| `ingest_student_roster_chars` | **1800** | Student roster excerpt in slim ingest context; 0 = unlimited |
| `ingest_course_state_chars` | **0** | Course state excerpt in slim ingest context; 0 = unlimited |
| `ingest_open_loops_chars` | **0** | Open loops excerpt in slim ingest context; 0 = unlimited |
| `ingest_saved_plan_chars` | **0** | Most recent saved plan excerpt in slim ingest context; 0 = unlimited |
| `ingest_draft_chars` | **0** | Current diary draft in ingest user input; 0 = unlimited |
| `upload_attachment_chars` | **0** | Per-upload content in chat user input; 0 = unlimited |
| `plan_state_list_limit` | 24 | Max items per state list injected into prompt |
| `plan_state_bullet_max_chars` | 160 | Max chars per injected state bullet |
| `plan_briefs_inject_limit` | 12 | Evidence briefs shown in system prompt |
| `plan_brief_lines_per_item` | 4 | Lines per brief in prompt |
| `plan_briefs_store_cap` | 40 | Evidence briefs kept in session RAM |
| `plan_raw_store_cap` | 60 | Raw tool outputs kept in session RAM |
| `plan_candidates_cap` | 50 | Memory candidates kept in session RAM |

Set any `*_chars` or `*_backstop` to **0** to disable truncation for that field.

Example `.env` for a conservative deployment on a smaller model:

```env
INGEST_CONTEXT_BACKSTOP=50000
PLAN_INSTRUCTIONS_BACKSTOP=80000
```

Example for modern large-context models (recommended default):

```env
# Leave backstops at 0 — rely on structured state + Hermes page budgets.
PLAN_HISTORY_TURNS=10
```

## What still truncates (by design)

| Mechanism | Why |
|-----------|-----|
| `plan_history_turns` | Verbatim chat window; durable facts live in `PlanRuntime` |
| `plan_state_list_limit` | Injection cap; full lists stay in RAM (watch very long sessions) |
| `plan_briefs_inject_limit` | Only last N briefs in prompt; older briefs still in RAM + `raw_store` |
| `MEMORY_PAGE_BUDGETS` | Hermes durable memory — intentional size discipline |
| `USER_PROFILE_SECTION_LIMIT` etc. | Profile write bounds |

## Debugging Context Behavior

Use the plan trace endpoint to inspect what the backend actually injected and
remembered:

```text
GET /api/classes/{class_id}/plan/sessions/{session_id}/trace
```

The response includes the teacher layer, active class core, compatibility
`class_slice`, rendered `SessionState` / `LessonPlanningState`, current
`lessonplan.md`, evidence briefs, streamed tool/final events, raw evidence refs,
prompt assembly, and the latest runtime payload. Treat this as local developer
diagnostics; it may contain teacher content and raw tool output.

`prompt_assembly` is the preferred debug view when asking "what exactly got fed
to the model?" It breaks the prompt into:

- section name
- builder function
- source file/object
- included flag
- character count
- exact rendered text

For planning, this covers the lazy opening call and every chat turn. The useful
mental model is:

```text
wiki/source file -> builder function -> compacted/rendered section -> prompt
tool call input -> raw output -> raw_ref -> evidence brief -> next prompt
```

This is intentionally more useful than ad-hoc `print()` calls because it is
request-local, serializable, comparable across runs, and available through the
API trace endpoint.

Trace event logs intentionally exclude per-token reasoning deltas. A real FCKW
planning run showed that reasoning-token spam can fill the trace cap and hide
the tool behavior we actually need to inspect.

The SDK also emits built-in traces for model calls, tool calls, guardrails, and
handoffs. Use those for live run inspection once they are correlated with local
`class_id`, `session_id`, workflow mode, and artifact version. Keep the local
trace endpoint because it exposes KlassenPilot-specific prompt assembly,
evidence refs, and artifact state in one bundle.

For live agent-behavior regression checks, use the opt-in API test:

```powershell
$env:RUN_LIVE_API_TESTS="1"
$env:LIVE_API_BASE_URL="http://localhost:8010"
cd backend
python -m pytest tests/test_live_api_plan_trace.py
```

This test calls the running backend and may use real OpenAI credits. It runs the
default three-turn FCKW scenario (initial plan, review-of-last-lectures, final
recap tweak) and verifies wiki retrieval tools, phase transitions through
`finalize`, a usable 45-minute plan, and a high-signal trace bundle.

## Anti-patterns (do not reintroduce)

- `context[:14000]` or any blind end-slice on a composed pack
- Full replace of session state without merge guards
- Duplicating the same wiki section multiple times in one pack (use slim builder)
- Raising blunt caps instead of fixing pack composition
- Debug evidence blocks inside teacher-facing artifacts; evidence belongs in
  runtime state and traces, while artifacts should cite sources naturally
