# Memory — Next Implementation Plan

Status: draft for owner review (one more pass before starting)
Single source of truth for the post-V3 memory work. Execution (phases, files,
tests, acceptance) is up top; the full rationale, research, sources, and
discussion that produced these decisions live in the **appendices** at the
bottom (folded in from the former `next_steps_tmp.md`).

## Current status & progress (2026-07-06)

**Done and green** (committed through `5dee384`): speech-act lanes, verified
fast lane + quote provenance, occasion-based reinforcement, insert-time
folding, single-call sweep, the live judge eval. 264 backend / 31 frontend
tests pass.

**This plan is the next block.** Five PRs, sequenced. State:

| PR | Scope | State |
|---|---|---|
| PR1 | Post-save `/memory/apply` closes ledger rows (B1) | **done** (`686f5eb`) |
| PR2 | Retire wiki-derived compact files `class_state`/`taught_so_far` (B3) | **done** (`8c037fa`) |
| PR4 | `remember(...)` capture tool + validation/retry (A — the emission gap) | **done** (`a91a171`) — live emission on gpt-5.5 unverified |
| PR3 | Typed `MemoryWrite`/`MemoryRead` service interface (C step 1) + B2 canonical folding | **done** (`6e9fb60`) |
| PR5 | Focus-grouped agent skills + subagent capabilities (C step 2) | later — **rediscuss after testing PR1–4** |

Built in owner-requested order (1, 2, 4, 3). Docs across `docs/` were updated to
match (`d82bb56`). **Gate:** owner tests PR1–4 (especially PR4's live emission
via `RUN_LIVE_AGENT_EVALS=1`) before PR5, which is deliberately under-specified
and to be rediscussed.

Tracked in the roadmap as the current highest-priority block:
[`docs/claude_todo.md`](../claude_todo.md).

## Decisions locked (discussion 2026-07-06 + Q&A)

- **Capture (A)**: an explicit `remember(...)` tool the model calls, with
  backend validation grounded in the *teacher's words* (lane policy + quote
  provenance) and **retry feedback** on failure. Not a passive output field.
- **Two-axis memory model**: **retrieved-grows-wiki** (deterministic event
  record, reaches context only via on-demand reads / progressive discovery, so
  it can grow) vs **assembled-budgeted memory** (self-evolving; curated by the
  sweep and pulled into task context by the per-task context builders —
  `build_plan_context_slim`, `build_ingest_context_slim`,
  `build_teacher_context_trace`, `build_active_class_core_context_trace` in
  `wiki/context_packs.py`). It is **not blindly injected into every prompt**;
  each builder assembles a task-scoped slice — which is *why* it must stay
  small (a task's slice is a fixed budget, not a growing store). **Every fact
  has exactly one home.**
- **B3 files**: retire `memory/class_state.md` and `memory/taught_so_far.md`
  as wiki-derived; **migrate useful content into canonical (course_state /
  timeline), then remove** (report-first script).
- **Visibility**: unified read surface for the *agent*; wiki-forward for the
  *teacher* (curated memory reached only through the sweep).
- **Skills (C)**: moderate granularity, **grouped by focus** (Communication /
  Teaching / Student) with progressive disclosure. **Service interface first
  (no behavior change), agent/subagent tools later.**
- **Order**: B1 first (isolated), then the Memory Map effort.

## The Memory Map (target end state)

"Read" = how the fact reaches the model. Curated memory is **assembled per
task by the context builders** (`context_packs.py`), not injected into every
prompt — but within a task it's a fixed budgeted slice, hence "budgeted".

| Entry | Nature | Home | Write | Read | Budget |
|---|---|---|---|---|---|
| lesson_results, raw diary, timeline, course_state, misconceptions, open_loops, students/* | deterministic event | wiki (retrieved) | `commit_lesson_record` (direct, HITL at review) | on-demand wiki read | none (grows) |
| teacher_profile, copilot_profile | pref (self-evolving) | curated memory | sweep apply (`close_candidates`) | task context builder | budgeted |
| teaching_patterns, subject guides | pattern (self-evolving) | curated memory | sweep apply | task context builder | budgeted |
| ~~class_state, taught_so_far~~ | derived from wiki | **removed** | — | read course_state/timeline | — |

---

## PR1 — Post-save `/memory/apply` closes ledger rows (B1)

**Goal:** applying a fast-lane candidate on the post-save panel marks its
ledger row `applied`, so the sweep never re-proposes it.

**Changes**
- `backend/app/schemas/api.py`: add `candidate_ids: list[str] = []` to
  `MemoryApplyItem`.
- `backend/app/api/routes.py::apply_memory`: add the ledger dependency
  (`get_memory_candidate_ledger`); after `apply_memory_items` succeeds, close
  the rows for the applied items — mirror the sweep-apply loop
  (`ledger.update_status(candidate_id, "applied", ...)` at routes.py:987).
  Only close rows whose write actually landed (respect `skipped`).
- `frontend`: `memoryApply` in `lib/api.ts` sends `candidate_ids`; the
  post-save panel already has them on each candidate (`candidate_id`).

**Tests** (`backend/tests/test_memory_apply.py`, new)
- seed one `fast_lane` candidate row → POST `/memory/apply` with its
  `candidate_ids` → assert wiki written AND ledger row `applied`.
- then `propose_memory_sweep_review` → assert the candidate is NOT
  re-proposed.
- a skipped/unsupported item does NOT close its row.
- frontend: `proposed-memory-updates.test.ts` asserts `candidate_ids` flow
  into the apply payload.

**Acceptance:** apply a post-save candidate, run the sweep, it's gone. Full
suite green.

---

## PR2 — Memory Map: retire the wiki-derived compact files (B3)

**Goal:** remove the twins so every "current unit / taught sequence" fact has
one home (canonical), and the sweep no longer proposes them.

**Changes**
- `backend/app/teacher_agent/memory_targets.py`: remove `class_state`,
  `taught_so_far` from `COMPACT_TARGETS` / section vocabulary /
  channel routing; anything targeting them at capture is dropped or rerouted
  to `inferred` (they are no longer valid durable targets).
- `backend/app/teacher_agent/wiki/memory.py`: remove them from
  `memory_paths` and `MEMORY_PAGE_BUDGETS`.
- Sweep: `memory_sweep_target_excerpts` and gate no longer see them; the
  consolidation call's in-scope targets shrink to the true curated set.
- **Migration script** `backend/scripts/migrate_retire_compact_state.py`
  (report-first, backup-before-write, like `cleanup_memv3_ledger.py`):
  for each workspace + seed wiki, read any still-current fact from
  `memory/class_state.md` / `taught_so_far.md`, confirm it's reflected in
  `course_state.md` / `timeline.md` (report if not), then delete the two
  files. Emits before/after markdown reports for owner review.

**Tests**
- `test_memory_targets.py`: `class_state.md` / `taught_so_far.md` are no
  longer supported runtime targets; a candidate aimed at them is not durable.
- sweep backend: gate/claims never include the retired targets.
- migration script: on a fixture workspace, produces a report and (with
  `--apply`) removes the files while leaving canonical intact.

**Acceptance:** sweep proposes only preference/pattern/subject memory;
retired files gone from seed + workspaces; canonical rollups unchanged.

---

## PR3 — Typed `MemoryWrite` / `MemoryRead` service interface (C step 1)

**Goal:** one declared contract behind every memory write/read, no behavior
change. B2 (folding dedup scope) falls out of the contract.

**Changes** (`backend/app/services/memory_skills.py`, new — service layer,
NOT agent-facing yet)
- Define typed operations wrapping the existing functions:
  - `commit_lesson_record` → wraps `commit_ingest` (`ledger_effect: none`,
    `hitl: at_review`, `dedup_scope: none`, targets: canonical lesson files).
  - `apply_curated_bullet` → wraps `apply_memory_items` /
    `apply_memory_sweep_decisions` (`ledger_effect: close_candidates`,
    `dedup_scope: ledger+canonical`, targets: curated files).
  - reads: `read_target_excerpt`, `enumerate_bullets`, `list_open_claims`,
    `recent_applied_texts` (wrap existing ledger/wiki reads).
- Each op declares `{targets, ledger_effect, hitl, dedup_scope}` and enforces
  its target allowlist (out-of-allowlist write → error).
- Route `apply_memory` and sweep-apply through `apply_curated_bullet` so
  ledger-close is contract-driven (retroactively guarantees PR1).
- **B2:** `dedup_scope: ledger+canonical` — folding/insert consults current
  canonical excerpts for targets that declare it, so a fact already in
  canonical wiki folds to `already_covered`.

**Tests**
- existing 264 backend tests are the no-behavior-change net.
- per-op contract test: declared `{targets, ledger_effect, ...}` matches
  actual behavior; out-of-allowlist write rejected.
- B2 folding test: seed a canonical-applied fact → re-capture folds to
  `already_covered`.

**Acceptance:** no behavior change (suite green); every write path goes
through a declared skill; B1 and B2 are contract invariants, not patches.

---

## PR4 — `remember(...)` capture tool (A)

**Goal:** close the emission gap by making capture an explicit tool call with
validation + retry, replacing the brittle passive-field policy.

**Changes**
- `backend/app/teacher_agent/agents.py` / agent tool defs: add a
  `remember(target, content, speech_act, quote)` function tool available in
  ingest + plan turns.
- Backend validator (reuse `discipline_memory_candidates` logic): lane
  policy + quote provenance against the actual teacher message. On failure,
  the tool returns a **structured error** ("quote not found in the teacher's
  message — use their exact words" / "class_state is not a preference
  target") so the model retries within the turn.
- On success, stage the candidate via the PR3 `MemoryWrite` path (so
  fast_lane + occasion + folding all apply unchanged).
- Simplify `DURABLE_MEMORY_CANDIDATE_POLICY` prose to a short contract; keep
  the passive `memory_candidates` field as a transition fallback (typed-state
  repair remains the safety net, not the primary path).
- Config: run the capture-relevant turn on a stronger model if measurement
  says the prompt alone doesn't close the gap (new setting, mirrors
  `OPENAI_SWEEP_MODEL`).

**Tests**
- deterministic: `remember` with a fabricated quote → tool error; with a
  valid quote → staged fast_lane candidate. (extends the existing capture
  goldens.)
- **live judge eval** (`test_klassenpilot_memory_capture_live.py`): flip the
  emission-gap xfails to expected passes; track the emission rate as the
  success metric. Owner sets the bar.

**Acceptance:** live eval emission rate ≥ bar; the three current XFAIL
emission gaps pass; no over-capture regression against the beta fixtures.

---

## PR5 — Focus-grouped agent skills + subagent capabilities (C step 2, later)

**Goal:** expose the typed ops as focus-grouped, progressive-disclosure
skills the agent/subagents can be assigned.

**Changes (sketch — design at the time)**
- Group the PR3 ops into **focus skills**: Communication, Teaching, Student
  (+ the deterministic event-write skill outside any focus).
- Progressive disclosure: each focus exposes a short description always
  visible; full op set loaded when the task is in that focus.
- Subagent capability sets: assign a focus (or a few) per subagent; a skill
  set cannot invoke outside itself.

**Tests**
- selection: agent picks the right focus for a task.
- capability: a subagent cannot call a skill outside its assigned set.
- (defer detailed plan until PR3/PR4 land.)

---

## Testing strategy (whole effort)

- **Contracts offline** (pytest, CI): schema/route/skill-contract tests;
  the recorded beta ledger fixtures (`tests/fixtures/mem_v3/`) guard against
  over-capture regressions through every phase.
- **Behavior live** (opt-in): the capture live judge eval is the emission
  metric for PR4; the MBB/executive sweep trace stays the consolidation bar.
- **Migration** (PR2): report-first + backup; owner reviews the before/after
  report before `--apply`.
- **No-behavior-change gate** (PR3): the full existing suite must stay green
  through the service extraction before any contract change.

## Sequencing summary

1. **PR1** — post-save ledger close (small, standalone).
2. **PR2** — retire class_state/taught_so_far + migration.
3. **PR3** — typed MemoryWrite/MemoryRead service interface (no behavior
   change); B2 folds in.
4. **PR4** — `remember(...)` capture tool + validation/retry; re-measure
   emission.  *(Pullable earlier if the emission gap is the priority — it's
   independent of PR2/PR3 except for writing through the PR3 path.)*
5. **PR5** — focus-grouped agent skills + subagent capabilities (later).

## Still-open (flag before starting)

- PR4 model choice: does prompt-simplification alone close emission, or do we
  also upgrade the capture turn's model? (measure in PR4, decide then.)
- PR2 migration: any workspace where a `class_state`/`taught_so_far` fact is
  NOT reflected in canonical → the report will flag it; decide handling
  per-case (likely: write it into course_state before deleting).
- PR5 is deliberately under-specified until PR3/PR4 land.

---
---

# Appendices — findings, rationale, research, sources

> Everything below is the analysis that produced the plan above (folded in
> from the former `next_steps_tmp.md`). It is reference material: proof with
> file:line + test output, the design discussion, the 2026 research, and the
> source list. The plan above is the decision; this is the *why*.

The three workstreams are independent and can be sequenced separately:

- **A — Capture emission gap** (durable teacher requests aren't emitted) → PR4.
- **B — Memory write-boundary leaks** (ledger vs canonical wiki seams) → PR1/PR2/PR3.
- **C — Composable memory read/write skills** (the north-star refactor that
  makes B impossible by construction and enables subagents) → PR3/PR5.

Everything committed through `5dee384` (speech-act lanes, occasions, live
judge eval) is done and green; this is what comes *after*.

## Appendix A — Capture emission gap (→ PR4)

### The finding (from the live judge eval)

The opt-in live eval
(`backend/tests/evals/test_klassenpilot_memory_capture_live.py`) runs each
speech-act golden through a real chat turn on `gpt-5.4`. Verbatim result:

```
XFAIL ...[conduct_request_teacher_profile_fast_lane] - capture emission gap:
  model emitted no teacher_profile.md candidate for
  'From now on, always keep future lesson plans in English.'
XFAIL ...[conduct_request_no_marker_fast_lane] - capture emission gap:
  model emitted no teacher_profile.md candidate for
  'Please be more concise in how you talk to me.'
XFAIL ...[store_request_teaching_patterns_fast_lane] - capture emission gap:
  model emitted no teaching_patterns.md candidate for
  'For the next block of organic chemistry, remember to use molecule kits
   before formal terminology.'
3 passed, 3 xfailed in 171.96s (0:02:51)
```

Interpretation:
- **Judgment is sound** — all 3 negatives (an observation, a one-off
  "make this worksheet shorter", a class-state statement) correctly stayed
  out of the fast lane.
- **Emission is the bottleneck** — all 3 positives (durable conduct/store
  requests) emitted **no `memory_candidates` at all**. Confirmed not an
  extraction bug: both the SSE `final.memory_candidates` and
  `trace.runtime.memory_candidates` were `[]`.

This is the exact shape of the original V2 capture bug
(`docs/mem_v2/candidate_capture_bug.md`): the model understands the durable
preference, follows it, even puts it in transient state — but does not route
it into `memory_candidates`. All the downstream discipline/gate/lane work is
correct and moot if the candidate is never emitted.

### Proof

- Eval + result: `backend/tests/evals/test_klassenpilot_memory_capture_live.py`
  (run: `$env:RUN_LIVE_AGENT_EVALS="1"; pytest tests/evals/test_klassenpilot_memory_capture_live.py -rx`).
- Deterministic side is fine:
  `backend/tests/evals/test_klassenpilot_memory_capture_stub.py` (7 goldens
  pass) — proves discipline works *given* an emitted candidate.
- Prior art / repair hook that already exists but may not fire for direct
  requests: `discipline`/`durable_preference_candidates_from_state_values`
  in `backend/app/teacher_agent/memory_capture.py`; capture policy in
  `backend/app/teacher_agent/prompts.py` (`DURABLE_MEMORY_CANDIDATE_POLICY`).

### Research insight — the emission gap is a *capture-shape* problem

Owner's inclination (a simple prompt + maybe a better model) is well
supported by 2026 practice, and the research points at *why* emission fails:

- **Capture is currently a passive side-output field, not an explicit
  tool.** `memory_candidates` is one field the model must remember to
  populate *while doing planning*. The 2026 SOTA is the opposite: agents
  **self-edit memory by calling a tool** — Mem0/Letta(MemGPT)/Zep and hermes
  all expose an explicit `save`/`update` memory operation the model invokes,
  which "operates entirely outside the model's internals — you can inspect
  it, debug it, edit it, and **swap the underlying model without touching
  your memory layer**"
  ([Steve Kinney, agent memory systems](https://stevekinney.com/writing/agent-memory-systems);
  [mem0 state of memory 2026](https://mem0.ai/blog/state-of-ai-agent-memory-2026)).
  hermes' background-review fork is exactly a model *choosing* to call the
  memory tool (`ref_repos/hermes-agent/agent/background_review.py`).
- **Trust the model's judgment, not rules** — the literature explicitly
  favors "knowledge distillation using LLM judgment rather than rules" for
  the capture decision, which matches the owner's dislike of deterministic
  formulation-guessing ("from now on…" vs "please always…" vs "going
  forward…" is unbounded — a rule can't enumerate it, but a strong model
  classifies it, as Opus-4.8-class models do here).
- **Model choice is a real lever** — `gpt-5.4-mini` (the current chat model
  the capture turn runs on) is weak for this; the decision is
  model-swappable precisely because it's a token-level operation. MemoryArena
  shows strong models still need memory as *decision-relevant operations*,
  not passive recall — reinforcing "make capture an explicit decision"
  ([memory survey 2026](https://arxiv.org/html/2603.07670v1)).

### Options that were evaluated (decision → PR4 = option 1)

1. **Make capture an explicit `remember(...)` tool with backend validation +
   retry feedback (chosen — owner-endorsed).** Replace the brittle
   `DURABLE_MEMORY_CANDIDATE_POLICY` prose + passive field with a small
   `remember(target, content, speech_act, quote)` tool the model calls when
   the teacher gives a durable instruction, plus a short contract ("if the
   teacher tells YOU how to behave or to remember something, call remember
   with their exact words"). This is the Mem0/Letta/hermes pattern, is
   model-swappable, and directly targets emission (the model decides once,
   explicitly).
   - **The deterministic validation stays — because it grounds in the
     *teacher's* words, not the model's.** Lane policy + quote provenance
     (the quoted sentence must appear in the teacher message) run as the
     tool's backend validator. This is legitimate: it validates against
     ground truth (what the teacher actually said), not against a heuristic
     guess about intent.
   - **On failure, feed the error back and let the model retry** — the modern
     agent-loop pattern (owner's point). A `remember` call with a fabricated
     quote or wrong target returns a structured tool error ("quote not found
     in the teacher's message; use their exact words" / "class_state is not a
     preference target"), and the model corrects on the next step. This turns
     the brittle one-shot side-output into a self-correcting loop and keeps
     the human-grounded guardrail without guessing the teacher's phrasing.
2. **Simplify the capture prompt + upgrade the capture model.** Cheapest
   first step even before a tool: strip the policy to a short contract, run
   the capture-relevant turn on a stronger model, re-measure emission with
   the live eval. Low-risk, fast signal on how much is model vs prompt. (PR4
   keeps this as the first sub-step / measurement.)
3. **Typed-state repair for direct requests** (fallback, not preferred).
   If the model records the preference in `state_patch` but not the tool/
   field, synthesize the candidate. Deterministic and formulation-fragile —
   the owner's exact concern — so keep it only as a safety net, not the
   primary path.

### Testing plan for A

- The live judge eval is already the measurement instrument. Extend it to
  report an **emission rate** (positives emitted / positives expected) as a
  tracked number, and flip xfail→pass as emission improves.
- Add ingest-side goldens (not just plan) since store requests are
  ingest-natural.
- Keep the deterministic stub as the discipline contract guard.
- Success bar: emission rate for the positive goldens ≥ some threshold
  (owner to set) on the target sweep/chat model.

Effort: S (prompt) to M (repair). Risk: emission fixes can over-capture —
must re-check against the over-capture goldens (`tests/fixtures/mem_v3/`).

## Appendix B — Memory write-boundary leaks (→ PR1/PR2/PR3)

Two physically separate memory layers, separate on purpose:

| Layer | Files | Write path | Nature |
|---|---|---|---|
| **Canonical event record** | `lesson_results.md`, raw diary, `course_state.md`, `misconceptions.md`, `open_loops.md`, `students/*.md`, `timeline.md` | Update Memory commits **directly** after review (`commit.py`) | deterministic projection of the approved diary |
| **Curated durable memory** | `memory/class_state.md`, `taught_so_far.md`, `teaching_patterns.md`, `copilot_profile.md`, `teacher_profile.md`, subject guides | chat → **ledger** → sweep → HITL apply | LLM-curated, deduped, gated, budgeted |

The boundary is **correct** (you want profiles/patterns to go through
sweep+HITL; you want the lesson record written directly). The leaks are at
the seams.

### B1 — Post-save `/memory/apply` never closes ledger rows (clean bug → PR1)

Proof — the request carries no candidate ids and the route has no ledger
dependency at all:

```python
# backend/app/schemas/api.py:95
class MemoryApplyItem(BaseModel):
    target: str          # teacher_profile.md | copilot_profile.md | class_state.md | ...
    section: str = "General"
    content: str         # <-- no candidate_id / candidate_ids

# backend/app/api/routes.py:806  apply_memory(...)
#   depends on: wiki, beta_auth   <-- NOT the ledger
#   calls apply_memory_items(...) then returns; never updates ledger status
```

Contrast — the sweep-apply path does it right:

```python
# backend/app/api/routes.py:987
ledger.update_status(candidate_id, status, updated_at=now, ...)
```

Effect: a teacher applies a fast-lane candidate on the post-save panel → wiki
file written, but the originating ledger row stays `captured` → the next
sweep re-proposes an already-applied fact.

**Would-be failing test (illustrative):**
```
seed ledger with one fast_lane candidate row (teacher_profile.md)
POST /memory/apply with that item (+ its candidate_ids)   # contract needs ids
assert wiki updated
assert ledger row status == "applied"                     # FAILS today
propose sweep → assert candidate not re-proposed           # FAILS today
```

Fix sketch: add `candidate_ids` to `MemoryApplyItem`, give the route the
ledger dependency, mirror the sweep-apply close loop. Small, unambiguous.

### B2 — Insert-time folding is blind to canonical writes (→ PR3)

`insert_with_folding`
(`backend/app/services/memory_candidate_ledger.py`) dedups a new candidate
only against prior **ledger** `applied`/`rejected` rows. It cannot see facts
already written to canonical wiki (via `commit.py`) or applied post-save
(B1). So the same fact can sit "open" in the ledger while already live in a
file.

Options: (a) at canonical commit, mark matching open ledger rows
`already_covered`; (b) the single-call sweep already reads current target
excerpts — lean on that for the compact files it manages, and accept that
canonical files (course_state) are out of its scope. B2's severity depends
heavily on B3; the chosen path is `dedup_scope: ledger+canonical` declared on
the PR3 skill contract.

### B3 — The `course_state.md` / `memory/class_state.md` twin (→ PR2)

Proof — two separate files, same "current unit" fact, two mechanisms:

```
roll_up_paths (canonical, direct-written by Update Memory):
  course_state   wiki/classes/chemie_9b_2026_27/course_state.md

memory_paths (compact, ledger+sweep-managed):
  class_state    wiki/classes/chemie_9b_2026_27/memory/class_state.md
```

`commit.py` `_upsert_course_state` writes the "Current unit" line to
`course_state.md` immediately and deterministically from the diary. The chat
*also* stages a `class_state.md` candidate ("class moved to organic
chemistry") that the sweep later proposes. **One fact, two homes, updated by
two mechanisms, out of sync by design.** This is the root of the observed
"we wrote it in the ledger but also directly edited the files."

Owner's read (2026-07-06): the whole curated-memory file set is **not
real-world-proven — it was an initial wiki idea**, and `class_state` vs
`course_state` (and arguably `taught_so_far`) is genuinely redundant. So B3
is really "tighten the curated-memory model to fewer, clearer files," not
just a dedup patch.

The current set has grown organically into overlapping files:

| File | Layer | Source of "current unit / sequence" fact | Overlaps |
|---|---|---|---|
| `course_state.md` | canonical rollup | diary (deterministic) | current unit, next focus |
| `memory/class_state.md` | compact/sweep | chat candidate (LLM) | current unit ⟵ twin of course_state |
| `memory/taught_so_far.md` | compact/sweep | chat candidate (LLM) | taught sequence ⟵ derivable from timeline/lessons |
| `timeline.md` | canonical rollup | diary (deterministic) | the lesson sequence itself |

Direction (→ PR2):
- **Derive, don't curate, what's already canonical.** `current unit`,
  `next focus`, `taught sequence` are deterministic projections of the diary
  + timeline — keep them in the canonical rollups and let the sweep *read*
  them, not maintain compact twins. Retire `class_state.md` and likely
  `taught_so_far.md`.
- **Reserve curated/sweep memory for what has NO canonical source** —
  teacher preferences (`teacher_profile`), copilot working agreement
  (`copilot_profile`), class learning patterns (`teaching_patterns`), subject
  guides. These are genuinely curated, deduped, reinforcement-gated.
- Research anchor: OpenClaw's memory-wiki draws exactly this line — compiled
  deterministic pages vs the self-evolving memory layer, with the wiki as a
  *synthesis/read* surface over memory, not a second write target (see
  Appendix C). Their compile pipeline keeps "managed" (regenerated) blocks
  separate from "human" blocks in one page rather than splitting the same
  fact across files
  (`ref_repos/openclaw/extensions/memory-wiki/src/chatgpt-import.ts`,
  `preserveExistingPageBlocks`, `HUMAN_START/END_MARKER`).

### Testing plan for B

- B1: API contract test (above) + a ledger-close assertion; add to
  `test_memory_sweep_backend.py` / a new `test_memory_apply.py`.
- B2: folding test seeding a canonical-applied fact, asserting a re-capture
  folds to `already_covered` (only if we implement option (a)).
- B3: redundancy-removal migration test (report-first) + a canonical↔ledger
  dedup check.

Effort: B1 = S; B2 = M; B3 = product decision then S–M. Risk: low for B1;
B3 touches the compact-memory model, so higher.

## Appendix C — Composable memory read/write skills (→ PR3/PR5)

### Why

The three write paths each re-implement the boundary differently, which is
*why* the seams leak:

- `commit_ingest` (`commit.py:108`) — writes 7 canonical files, no ledger
  contact.
- `apply_memory_items` (`memory_apply.py`) — writes 4 target types, no
  ledger close (B1).
- `apply_memory_sweep_decisions` — writes *and* closes ledger rows.

Nobody declares "does this write close ledger rows? is it HITL-gated? what's
its dedup scope?" — the contract is implicit and duplicated.

### Two write *modes* the design must hold together (owner's framing)

The elephant in the room is that KlassenPilot actually has two legitimately
different memory behaviors and they currently don't know about each other:

1. **Deterministic single-task writes** — one action completes a known
   artifact: lesson planning writes a fixed `lesson_plan.md`; update-memory
   writes the dated lesson record and student memos. These are *events*,
   written directly, source-of-truth.
2. **Self-evolving curated memory** — hermes/OpenClaw style: bounded,
   budgeted, deduped, reinforcement-gated, HITL-consolidated (profiles,
   patterns). These *evolve* over time.

The requirement: **both must see each other and work together** — the
curated layer should read the event record as ground truth, and the event
record shouldn't re-enter the curated layer as a duplicate (this is exactly
the B leaks).

### Research anchor — OpenClaw's memory-wiki solves this exact split

`ref_repos/openclaw/extensions/memory-wiki` +
[docs](https://docs.openclaw.ai/plugins/memory-wiki). Directly transferable
mechanisms:

- **Layered, not replacement.** "It does not replace the active memory
  plugin. Recall, promotion, indexing, and dreaming stay owned by the memory
  backend." The wiki is a *compiled synthesis/read surface* over memory — it
  does not become a second write target. → maps to: canonical rollups +
  curated memory are two layers; don't let the sweep maintain twins of
  canonical facts (B3).
- **Managed vs human blocks in one page.** `preserveExistingPageBlocks`
  (`src/chatgpt-import.ts`) keeps machine-regenerated blocks
  (`MANAGED`) and human-authored blocks (`HUMAN_START/END_MARKER`) separate
  *within a single page*, so regeneration never clobbers human edits. → maps
  to: a page can hold a deterministic block (from the diary) and a curated
  block (from the sweep) without splitting the fact across two files.
- **Dual-corpus read, single call.** `search.corpus: "all"` lets one
  `memory_search` span the compiled wiki and durable memory; `wiki_search`/
  `wiki_get` when you want wiki-specific ranking/provenance. → maps to: one
  read surface over both layers so the two "see each other."
- **Narrow typed write ops, not freeform surgery.** `wiki_apply` performs
  "narrow synthesis/metadata mutations without freeform page surgery";
  reads are `wiki_search` / `wiki_get`; validation is `wiki_lint`
  (contradiction detection). → this *is* the composable read/write skill set,
  already proven in a shipping plugin.
- **Claims carry status/confidence/evidence/provenance** — contestable,
  sourced, resolvable back to origins. → richer than our flat bullets;
  optional future direction for the curated layer.

### Owner's grouping idea — organize skills/memory by use-case focus

Instead of a flat file list, group curated memory (and the skills that touch
it) by **focus area**: e.g. *student focus*, *teaching focus*,
*communication focus*. This is attractive because it (a) collapses the
redundant file sprawl into a few meaningful surfaces, and (b) gives
subagents a natural capability partition — a "student-focus" subagent reads/
writes only student memory; a "communication-focus" subagent only the
teacher/copilot preference surface. Worth pressure-testing against the
current targets:

| Focus | Curated memory | Read/write skills |
|---|---|---|
| Communication | teacher_profile, copilot_profile | append/replace preference bullet |
| Teaching | teaching_patterns, subject guides | append/replace pattern bullet |
| Student | students/*.md summaries | update student summary |
| (Event record) | lessons, timeline, rollups | commit_lesson_record (deterministic) |

Note the event record is deliberately *not* a focus — it's the shared
ground truth all focuses read.

### Where we diverge from OpenClaw (owner's calls, and I agree)

OpenClaw is the right reference for *layering + visibility*, but two of its
choices don't fit a teacher product, and the owner's alternatives are
better here:

1. **Separate files, not managed/human blocks in one page.** OpenClaw packs
   machine + human blocks into a single page; the owner prefers wiki and
   self-evolving memory as *separate files with different approaches*. I
   agree — and the sharper principle underneath it is **retrieved-on-demand
   vs assembled-into-task-context**:
   - **Wiki = retrieved.** Only the relevant slice enters context per task
     (progressive discovery / `wiki_get`), so it **can grow arbitrarily** —
     detail is fine if traversal is efficient. This is exactly Anthropic's
     progressive-disclosure model (metadata → page → references) and the
     answer to "is lots of detail ok": yes, because it's not always in
     context.
   - **Self-evolving memory = assembled per task, hence budgeted.** It is
     **not** blindly injected into every prompt — the per-task context
     builders (`build_plan_context_slim`, `build_ingest_context_slim`,
     `build_teacher_context_trace`, `build_active_class_core_context_trace`
     in `wiki/context_packs.py`) assemble a task-scoped slice. But that slice
     is a fixed budget for the task, so the store it draws from **must stay
     small** or the assembled slice degrades / pollutes the turn. Curated,
     deduped, budgeted (hermes/letta; our page budgets).
   - So the boundary isn't only "deterministic vs self-evolving" — it's
     "retrieved (can grow) vs assembled-into-context (must be bounded)." The
     two axes line up, which is why the model is clean. **Hard rule: every
     memory fact has exactly one home** — wiki OR curated memory, never both
     (this is the B twin fix stated as an invariant).

2. **Asymmetric teacher visibility, not symmetric dual-corpus.** OpenClaw's
   `corpus: all` unifies the read surface *for the agent* — good, keep that
   for agent reads. But the owner's point stands: a non-technical teacher
   should not browse the self-evolving memory as a corpus. The **wiki is the
   teacher's mental model** (class-management state — lessons, students,
   course state — concrete and legible); the curated memory is the agent's
   working memory that the teacher touches **only through the sweep review**
   (approve/reject), never as a browsable store. So: unified read model for
   the *agent*, wiki-forward visibility for the *teacher*.

### Sketch (to be pressure-tested against OpenClaw's tool set)

```
WriteSkill:
  name:          append_compact_bullet | replace_bullet | commit_lesson_record | append_profile_pref
  targets:       explicit allowlist of files it may touch
  ledger_effect: none | close_candidates | stage_candidate
  hitl:          direct | requires_approval
  dedup_scope:   ledger | ledger+canonical | none
ReadSkill:
  name:          read_target_excerpt | list_open_claims | enumerate_bullets | recent_applied_texts
```

Payoffs:
- **Leaks become impossible by construction** — any write skill with
  `ledger_effect: close_candidates` closes rows; post-save apply just *uses*
  that skill, so B1 can't recur. `dedup_scope: ledger+canonical` is a
  declared capability folding honors uniformly (B2).
- **Substrate for subagents** — a consolidation subagent gets
  `read:[enumerate_bullets, list_open_claims, recent_applied_texts]` +
  `write:[replace_bullet, append_compact_bullet]` and *cannot* touch the
  lesson record; a lesson-logging subagent gets `commit_lesson_record` and
  nothing else. Capabilities are assignable, narrow, auditable. Pairs with
  the `approach.md` priming block: a subagent primed on the approach +
  handed a typed capability set is safe by construction, not by hoping it
  read the docs.

### Migration path

1. Extract the three existing write paths behind one typed `MemoryWrite`
   interface with **no behavior change** (pure refactor, fully covered by
   existing tests). → PR3.
2. Add the declared contract fields; make B1/B2 fixes fall out of the
   contract rather than bespoke patches. → PR3.
3. Layer read skills + capability sets; then subagent assignment. → PR5.

### Testing plan for C

- Step 1 is a refactor: existing suite (264 backend tests) is the safety
  net; add a per-skill contract test asserting each skill's declared
  (targets, ledger_effect, hitl, dedup_scope) matches its behavior.
- Golden: attempt an out-of-allowlist write per skill → rejected.
- Subagent capability test: a skill set cannot invoke a skill outside it.

Effort: L (staged). Risk: medium — it's a cross-cutting refactor, so do
step 1 as a pure no-op-behavior extraction first and land it green before
anything else.

## Appendix D — Skill granularity: recommendation + 2026 SOTA

Owner's open question: lots of small skills vs larger groups. The 2026
literature is fairly decisive, and it lands between the extremes:

- **There is a hard ceiling on tiny skills.** Research finds a *phase
  transition*: beyond a critical library size, skill-selection accuracy
  "degrades sharply"
  ([Agent Skills architecture survey](https://arxiv.org/html/2602.12430v3);
  [SoK: Agentic Skills](https://arxiv.org/html/2602.20867v1)). So "many tiny
  atomic tools" is actively harmful to selection.
- **Anthropic's answer is progressive disclosure + logical grouping**, not
  atomicity: metadata (name/description) always loaded → full `SKILL.md` on
  relevance → reference files as needed; "group *logically related*
  capabilities rather than pursuing maximum atomicity"
  ([Anthropic — Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)).
  For very large registries, a Tool Search step cuts token overhead ~85%.

**Recommendation: moderate granularity, grouped by focus areas, atomic ops
inside.** Concretely:
- A small number of **focus skills** (Communication, Teaching, Student) —
  this is exactly the owner's grouping, and it matches "logically related
  capabilities." Each is a progressive-disclosure skill: a short description
  the agent always sees, a `SKILL.md` loaded when the task is in that focus.
- Inside each focus, a few **atomic operations** (`read_excerpt`,
  `propose_update`, `list_open_claims`) — composable building blocks, not a
  do-everything call.
- Plus the deterministic **event-write skills** (`commit_lesson_record`,
  `save_lesson_plan`) which are single-task and don't belong to a focus.
- This scales: adding a focus (e.g. "Assessment") is one new grouped skill,
  not N new tools competing in selection. It also gives subagents a clean
  capability partition (a Student-focus subagent gets the Student skill +
  wiki read, nothing else) — extensible without hitting the phase transition.

Why not "one big memory skill" or "1000 tiny tools": the former can't be
partitioned for subagents or loaded selectively; the latter degrades
selection. Focus-grouped progressive-disclosure skills are the SOTA middle.

## Appendix E — Resolved in discussion (2026-07-06)

- **A**: explicit `remember(...)` tool + user-grounded deterministic
  validation + retry feedback (not a passive field). → PR4.
- **C**: deterministic wiki (retrieved, can grow) vs self-evolving memory
  (assembled per task, budgeted) as **separate files**, one home per fact;
  asymmetric teacher visibility (wiki-forward, memory via sweep only);
  moderate focus-grouped skills. → PR3/PR5.
- **B3 and C merge** into one **Memory Map** design pass (the table at the top
  of this doc). → PR2 (files) + PR3 (skills).

## Appendix F — Research & sources

Industry / literature (2026):
- [mem0 — state of agent memory 2026](https://mem0.ai/blog/state-of-ai-agent-memory-2026)
  and [AI memory benchmarks 2026](https://mem0.ai/blog/ai-memory-benchmarks-in-2026)
  — self-editing memory, write-time conflict resolution, LoCoMo/LongMemEval.
- [Steve Kinney — agent memory systems](https://stevekinney.com/writing/agent-memory-systems)
  — capture via LLM judgment not rules; token-level memory is model-swappable.
- [Memory for Autonomous LLM Agents (survey, 2026)](https://arxiv.org/html/2603.07670v1)
  — MemoryArena: passive recall ≠ decision-relevant memory operations.
- [Hindsight — consolidation problem](https://hindsight.vectorize.io/blog/2026/05/21/agent-memory-consolidation)
  and [benchmark manifesto](https://hindsight.vectorize.io/blog/2026/03/23/agent-memory-benchmark)
  — write-time is the cheapest control point; the write step is under-measured.
- [Letta — sleep-time compute](https://www.letta.com/blog/sleep-time-compute/)
  — background consolidation; budget-exceed forces compaction.

Agent skills / granularity (2026):
- [Anthropic — Equipping agents with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
  — progressive disclosure (metadata → SKILL.md → references); group
  logically related capabilities, not maximum atomicity.
- [Agent Skills: architecture, acquisition, security](https://arxiv.org/html/2602.12430v3)
  and [SoK: Agentic Skills](https://arxiv.org/html/2602.20867v1)
  — the phase transition: selection accuracy degrades past a critical
  library size (argues against many tiny skills).
- Anthropic Advanced Tool Use — Tool Search reduces token overhead ~85% for
  large registries.

Reference repos (cloned under `ref_repos/`):
- **OpenClaw memory-wiki** — `ref_repos/openclaw/extensions/memory-wiki/`
  ([docs](https://docs.openclaw.ai/plugins/memory-wiki)); key files:
  `src/chatgpt-import.ts` (`preserveExistingPageBlocks`, HUMAN/MANAGED
  blocks), `README.md` (modes: isolated / bridge; `search.corpus: all`),
  `src/apply.ts` (managed synthesis writes).
- **hermes-agent** — `agent/background_review.py` (model chooses to call the
  memory tool), `tools/memory_tool.py` (budget-as-error, exact-dup reject).
- **mem0** — `mem0/configs/prompts.py` (ID-referenced ADD/UPDATE/DELETE/NONE),
  `mem0/memory/main.py` (extraction pipeline).

Our own: `approach.md` (the taught approach), `lecture.md` (field survey +
eight design dimensions), `learnings.md` (post-mortem, incl. the live-eval
emission finding), `design.md`.
