# Ingest Context Alignment (Hermes 3-Layer Model)

Goal: align **Update Memory** context loading with the same Hermes-style
discipline already used by **lesson planning** — small core memory, task-specific
slice, on-demand wiki browse — and remove developer/schema noise from teacher
prompts.

Status: **proposal** (investigation complete; no code changes yet).

> Note (2026-07): this doc predates mem_v3 PR2. The compact pages `class_state`
> and `taught_so_far` referenced in the tables below were retired — current unit
> and taught sequence are now derived from the canonical `course_state.md` /
> `timeline.md` rollups. Read the compact-page lists here as historical.

Related docs:

- [`docs/agent_architecture.md`](../docs/agent_architecture.md) — retrieval and
  compact-memory intent
- [`docs/memory_hierarchy.md`](../docs/memory_hierarchy.md) — file scope and
  load rules
- [`docs/context_management.md`](../docs/context_management.md) — limits and
  trace debugging
- [`update_memory_free_agent_plan.md`](update_memory_free_agent_plan.md) —
  runtime/tools/hints (mostly done); this plan covers **prompt context assembly**

Evidence: live trace `backend/runs/phase-fix-check/` (2026-06-14) and code read
of `context_packs.py`, `prompt_assembly.py`, `agents.py`.

---

## Target Architecture (shared mental model)

Every KlassenPilot chat turn should compose three layers:

| Layer | Purpose | Loaded when |
|-------|---------|-------------|
| **1. Core memory pack** | Small, high-signal, Hermes-budgeted class memory every turn needs | Every chat interaction |
| **2. Task-specific pack** | Workflow slice (plan vs update memory) + backend runtime + live artifact | Every turn of that workflow |
| **3. On-demand wiki** | Canonical detail, date-specific lessons, long roll-ups, entity pages | Tool calls when the teacher question needs evidence not in layers 1–2 |

Design rules (already stated in architecture docs):

- Prefer `clamp_memory_page` / `MEMORY_PAGE_BUDGETS` over dumping full roll-ups.
- Do not stack index + base + query packs in the live prompt.
- Tool policy: use the pack first; browse by information need, not keyword triggers.

---

## Current State

### Lesson planning — **mostly aligned**

Live path: `AgentRunner._prepare_plan_turn` → `build_plan_chat_agent` →
`build_plan_chat_prompt_assembly`.

| Layer | What loads today | Key files |
|-------|------------------|-----------|
| **Core** | Class identity, top misconceptions, recent lesson titles, subject guide (clamped), compact pages: `class_state`, `taught_so_far`, `planning_brief`, `teaching_patterns` | `backend/app/teacher_agent/wiki/context_packs.py` (`build_plan_context_slim_trace`), `wiki/memory.py` (`clamp_memory_page`, `MEMORY_PAGE_BUDGETS`) |
| **Profiles (core-adjacent)** | `wiki/teacher_profile.md` + class `memory/copilot_profile.md` — separate **Profiles** section, clamped | `backend/app/teacher_agent/prompt_assembly.py` (`build_profiles_assembly`) |
| **Task** | `PLAN_SKILL`, `PLAN_MEMORY_POLICY`, `PlanRuntime` session/lesson state, evidence briefs, current `plan_markdown`, trimmed conversation | `prompts.py`, `planning_state.py`, `agents.py` |
| **On-demand** | `list_lessons`, `read_lesson`, `read_lesson_range`, `search_memory`, `read_memory_page`, `get_raw_evidence` | `tools.py` (`create_chat_wiki_tools`) |

**Plan opening** is intentionally slimmer: class slice only, no profiles, no tools
(`build_plan_opening_agent`).

**Gaps (minor):**

- `class_state.md` omitted when file missing (observed in FCKW trace).
- Legacy stacked builders still in repo for tests (`build_plan_context`,
  `build_base_class_context`) — not live paths.

Debug: `GET .../plan/sessions/{id}/trace` → `prompt_assembly.sections[]`.

---

### Update memory — **not aligned**

Live path: `AgentRunner._prepare_ingest_turn` → `build_ingest_agent` →
`build_ingest_chat_prompt_assembly`.

| Layer | What loads today | Gap vs target |
|-------|------------------|---------------|
| **Core** | Partial: compact pages (`taught_so_far`, `planning_brief`, `teaching_patterns`) inside one monolithic pack | No shared **profiles** slice; no Hermes-style shared core builder reused from plan |
| **Task** | `MEMORY_SKILL`, `MemoryRuntime`, diary section list, current `diary_markdown`, conversation | OK structurally |
| **On-demand** | `list_memory_targets`, `read_memory_target`, `search_memory`, `read_memory_page`, `get_raw_evidence` | OK; used correctly in `phase-fix-check` trace |

**Problems found in investigation:**

1. **`teacher_wiki/AGENTS.md` injected into every ingest turn** as “Wiki logging
   conventions”. This is the wiki **maintainer/schema** doc (points developers at
   repo `AGENTS.md`), not teacher-facing memory. ~3k chars in the FCKW trace;
   duplicates rules already in `INGEST_SYSTEM` (`prompts.py`). Plan chat does
   **not** load this file.

2. **`copilot_profile.md` missing from ingest** — loaded for plan via
   `build_profiles_assembly`; ingest has no equivalent. Agent only sees
   `teaching_patterns.md` (class learning profile) plus a **mention** of
   `copilot_profile` inside the injected `AGENTS.md` routing table, not the
   actual profile content.

3. **`teacher_profile.md` missing from ingest** — same as copilot; plan-only today.

4. **Heavy roll-ups inlined instead of on-demand** — full `students.md`,
   `course_state.md`, `open_loops.md` in slim pack. Plan keeps these behind tools;
   ingest front-loads them (13k+ chars in trace vs Hermes-clamped plan slice).

5. **Prompt/code mismatch** — `INGEST_SYSTEM` says “index + roll-ups + recent
   lesson detail” but `build_ingest_context_slim` does not include `index.md`.

6. **Legacy builders still present** — `build_ingest_context`, `build_ingest_query_pack`
   also embed `AGENTS.md`; used in tests only, not live chat.

Debug: `GET .../ingest/sessions/{id}/trace` or
`scripts/run_memory_update_trace_bundle.py` →
`prompt-XX-ingest_chat-sections.md` → section **Ingest class context**.

---

## Key Files (touch map)

| Area | File | Role today |
|------|------|------------|
| Ingest slim pack | `backend/app/teacher_agent/wiki/context_packs.py` | `build_ingest_context_slim` — **remove AGENTS.md**, refactor sections |
| Plan slim pack | same | `build_plan_context_slim_trace` — reference implementation |
| Profiles | `backend/app/teacher_agent/prompt_assembly.py` | `build_profiles_assembly` — plan only; reuse or mirror for ingest |
| Ingest prompt | `backend/app/teacher_agent/prompt_assembly.py` | `build_ingest_chat_prompt_assembly` |
| Agent wiring | `backend/app/teacher_agent/agent.py` | `build_ingest_agent`, `build_plan_chat_agent` |
| Turn prep | `backend/app/teacher_agent/agents.py` | `_prepare_ingest_turn`, `_prepare_plan_turn` |
| System prompts | `backend/app/teacher_agent/prompts.py` | `INGEST_SYSTEM`, `PLAN_CHAT_SYSTEM` — fix stale “index + roll-ups” wording |
| Limits | `backend/app/context_limits.py`, `config.py` | `ingest_*_chars`, `MEMORY_PAGE_BUDGETS` |
| Tools | `backend/app/teacher_agent/tools.py` | `create_memory_update_tools`, `create_chat_wiki_tools` |
| Tests | `backend/tests/test_wiki_context_packs.py` | Asserts `AGENTS.md` in ingest — update after fix |
| Contract | `backend/tests/eval/test_memory_update_contract.py` | Trace shape regressions |
| Docs | `docs/memory_hierarchy.md`, `docs/agent_contracts.md` | Update load rules when behavior changes |
| Maintainer schema | `backend/teacher_wiki/AGENTS.md` | Keep for wiki editors; **stop injecting into teacher prompts** |

---

## Target State

### Shared layer 1 — core memory (both workflows)

Extract or reuse a single builder (working name: `build_core_class_memory`) that
returns traceable sections:

- Class identity snapshot (label, subject, unit, last lesson, open-loop count)
- Top misconceptions (snapshot, bounded)
- Compact Hermes pages (clamp each): `class_state`, `taught_so_far`,
  `planning_brief`, `teaching_patterns`
- **Profiles** (clamp each): `teacher_profile.md`, `memory/copilot_profile.md`

Both plan and ingest consume this core pack. Plan may still add subject guide in
task layer if we keep subject-wide guidance planning-specific.

### Layer 2 — task-specific

**Plan (mostly keep as-is):**

- `PLAN_SKILL` + runtime + current plan + evidence briefs
- Optional: subject guide if not moved into core

**Ingest (slim down):**

- `MEMORY_SKILL` + runtime + diary draft + required section headings
- Small logging-oriented extras only:
  - **Roster excerpt** (bounded) for pseudonym mapping — not full table if tool can serve names
  - **Previous lesson excerpt** (bounded) OR rely on `read_memory_target` when correcting
  - Drop full `open_loops.md` / `course_state.md` from default pack → tools
- Remove `teacher_wiki/AGENTS.md` entirely from prompt; diary format stays in
  `INGEST_SYSTEM` only (or a tiny teacher-facing snippet if we want one file)

### Layer 3 — on-demand (unchanged surface)

Keep existing read tools; update `INGEST_WIKI_TOOLS_POLICY` to reflect the new
default pack contents (what is in vs out).

---

## Proposed Phases

### Phase A — Stop the bleed (small, safe)

- Remove `store.read_text(store.root / "AGENTS.md")` from
  `build_ingest_context_slim` (and legacy `build_ingest_context` /
  `build_ingest_query_pack` for consistency).
- Fix `INGEST_SYSTEM` placeholder text (“index + roll-ups…”) to match slim pack.
- Update `test_wiki_context_packs.py` — stop requiring `AGENTS.md` in ingest context.
- Re-run `run_memory_update_trace_bundle.py`; confirm slimmer prompt, same behavior.

**Acceptance:** trace section “Ingest class context” has no `AGENTS.md` / directory
layout content; contract tests pass.

### Phase B — Add missing profiles to ingest

- Inject `build_profiles_assembly` into `build_ingest_chat_prompt_assembly`
  (mirror plan: separate **Profiles** section or fold into shared core builder).
- Update `docs/memory_hierarchy.md` ingest load rules.
- Extend offline contract test: profiles section present in ingest trace when files exist.

**Acceptance:** `copilot_profile.md` body text appears in ingest trace; not only
`teaching_patterns.md`.

### Phase C — Extract shared core + slim ingest task pack

- Introduce `build_core_class_memory_trace` used by plan slim + ingest.
- Move full roll-ups (`open_loops`, `course_state`) out of default ingest pack;
  document tool path for open-loop follow-ups during logging.
- Apply `ingest_*_chars` budgets where currently 0 (unlimited) if trace shows bloat.
- Align `update_memory_free_agent_plan.md` phase 5 with scenario traces for context size.

**Acceptance:** ingest and plan traces share the same core section names/sources;
ingest context char count drops materially vs `phase-fix-check` baseline; live
scenario still resolves 2026-05-29 target and pseudonyms correctly.

### Phase D — Docs and backlog

- Update `agent_contracts.md` with explicit 3-layer compose rules per workflow.
- Link from `product_backlog.md` v1.1 if we want “context inspectability” as a
  trust item (trace already supports this).

---

## Non-Goals (this plan)

- Changing commit/HITL write semantics.
- Adding vector search or new tool types.
- Loading repo-root `AGENTS.md` into any teacher prompt.
- Replacing `teacher_wiki/AGENTS.md` as wiki maintainer documentation — only stop
  prompt injection.

---

## Validation

Offline:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests/test_wiki_context_packs.py tests/eval/test_memory_update_contract.py -v
```

Live (backend on :8010):

```powershell
.\backend\.venv\Scripts\python .\scripts\run_memory_update_trace_bundle.py --run-name "context-align-check"
```

Compare `prompt-03-ingest_chat-sections.md`:

- Section list and char counts vs `phase-fix-check`
- Presence of profile content; absence of wiki schema doc
- Tool calls unchanged for default 3-turn scenario

Plan parity check: `run_plan_trace_bundle.py` — core sections stable after shared
extract in phase C.

---

## Open Questions

1. Should **subject guide** live in shared core or stay plan-only? (Recommend
   plan-only for v1; ingest rarely needs subject-wide patterns.)
2. Should ingest keep a **bounded roster excerpt** in layer 2 for pseudonym
   quality, or rely on roster table + tool? (Recommend bounded excerpt until
   pseudonym errors show up in eval.)
3. When `class_state.md` is missing, should compaction/refresh seed it so core
   pack is complete? (Separate backlog item; noted in FCKW trace.)

---

## Follow-on work (out of scope here)

After phases A–C (ideally full A–D), implement
[`ingest_session_state_parity_plan.md`](ingest_session_state_parity_plan.md):
split runtime inject (target / session / lesson-result / evidence), last-8-turn
history trim, and `MEMORY_SKILL` guidance for patching decisions into
`MemoryRuntime`. That plan assumes the slimmer core pack and profiles from this
document are already in place.
