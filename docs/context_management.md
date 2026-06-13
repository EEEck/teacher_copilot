# Context Management

How KlassenPilot assembles agent prompts, why we removed blunt character caps,
and where to tune limits.

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

**Plan chat no longer uses this pattern.** It uses `build_plan_context_slim` +
structured `PlanRuntime` state instead.

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

- [OpenAI session memory & trimming](https://github.com/openai/openai-cookbook/blob/main/examples/agents_sdk/session_memory.ipynb)
- [OpenAI compaction at workflow boundaries](https://developers.openai.com/cookbook/examples/agents_sdk/building_reliable_agents_memory_compaction)
- [OpenAI context personalization (structured state)](https://developers.openai.com/cookbook/examples/agents_sdk/context_personalization)

## KlassenPilot strategy (by workflow)

### Lesson planning chat (primary)

1. **Structured state** — `SessionState`, `LessonPlanningState` persisted on
   backend-owned `PlanRuntime`; the model proposes `state_patch` updates and
   backend merge rules prevent empty fields from wiping accumulated state.
2. **Slim class slice** — `build_plan_context_slim` (each wiki page clamped via
   `MEMORY_PAGE_BUDGETS`).
3. **Full lesson plan** — current `lessonplan.md` injected each turn (no char
   cap by default).
4. **Verbatim window** — last `plan_history_turns` teacher turns in the user
   message (default 8).
5. **Evidence briefs** — compact tool summaries; raw outputs behind `raw_ref`.
6. **No blunt 14k clip** on composed instructions.

### Ingest / memory update

Uses `build_ingest_context_slim`: one purpose-built pack for lesson logging.
It includes each high-signal source once (previous lesson, roster excerpt,
course state, open loops, misconceptions, compact memory, logging conventions)
instead of stacking index + base + ingest + query-pack layers. Blunt
end-truncation remains **disabled by default** (`ingest_context_backstop=0`).

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
| `plan_opening_context_chars` | **0** | Plan opening agent context; 0 = unlimited |
| `compile_context_chars` | **0** | Compile diary context; 0 = unlimited |
| `plan_lesson_context_chars` | **0** | One-shot plan lesson context; 0 = unlimited |
| `lint_context_chars` | **0** | Wiki lint context; 0 = unlimited |
| `profile_propose_field_chars` | **0** | Profile proposal field cap; 0 = unlimited |
| `memory_compact_source_chars` | **0** | Memory compaction source packet; 0 = unlimited |
| `ingest_previous_lesson_chars` | **0** | Previous lesson excerpt in slim ingest context; 0 = unlimited |
| `ingest_student_roster_chars` | **0** | Student roster excerpt in slim ingest context; 0 = unlimited |
| `ingest_course_state_chars` | **0** | Course state excerpt in slim ingest context; 0 = unlimited |
| `ingest_open_loops_chars` | **0** | Open loops excerpt in slim ingest context; 0 = unlimited |
| `ingest_logging_conventions_chars` | **0** | Wiki logging conventions excerpt; 0 = unlimited |
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

The response includes the class slice, teacher/copilot profile slices, rendered
`SessionState` / `LessonPlanningState`, current `lessonplan.md`, evidence
briefs, streamed tool/final events, raw evidence refs, prompt assembly, and the
latest runtime payload. Treat this as local developer diagnostics; it may
contain teacher content and raw tool output.

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
