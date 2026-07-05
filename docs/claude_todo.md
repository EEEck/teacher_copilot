# Claude TODO — beta feedback roadmap (living document)

> Working progress document for the improvements derived from the first beta
> tester results (demo workspace `w_demo_chem9b`). Organized as orthogonal
> milestones, **one PR each**. Update the "Implementation status" section at
> the bottom as PRs land. Linked from the root [`CLAUDE.md`](../CLAUDE.md).

## Background — what the beta run showed

Telemetry (`backend/beta_data/beta.sqlite3`), the memory-candidate ledger,
and the demo workspace wiki surfaced these findings:

1. **Lost chat turn**: a stream failure produced silence — no assistant
   reply, no failure telemetry. *(fixed, see status)*
2. **Ghost duplicate sessions**: React StrictMode double-fired the session
   bootstrap POST; every page open created a dead twin session. *(fixed)*
3. **Implausible lesson date**: results committed to 2027-02-03 polluted
   course state and planner context. *(guard + seed cleanup done)*
4. **Review overwhelm**: ~10 file proposals per save; tester rubber-stamped
   everything, sometimes wanted detail. → **Milestone 1**
5. **Memory sweep re-proposed applied candidates**: the same "MBB-style"
   preference was proposed/approved 6×. → **Milestone 2**
6. **One-off requests became durable rules**: "organize this in mbb style"
   (a one-off formatting ask) became a global communication preference.
   → **Milestone 3**
7. **No date awareness**: prompts never state today's date; the model cannot
   tell past from future lessons. → **Milestone 4**
8. **Saved artifacts are dead ends**: no way to reopen a saved plan into a
   chat session; the tester re-did an identical plan from scratch.
   → **Milestone 5**
9. **No lightweight "add one thing" flow**: adding a forgotten observation
   requires a full session + full re-review. → **Parked** (no design yet).

## Milestone 1 — Review brief (teacher-first save screen)

**Goal:** replace the file-list wall as the *default* review surface with a
plain-language brief; keep every existing detail surface intact behind it.

**Hard constraint:** do not rewrite the review machinery. Reuse
`useFileChangeReview`, `FileChangeReviewPanel`, `MarkdownLineDiff`,
`WikiProposalEditor`; commit payload and the lesson-results-required guard
stay unchanged. The brief is a new layer on top.

Target design (default view after "Ready to save memory"):

```
Save lesson memory — 2 Jul 2026                    [ Save all (9) ]
NEW
 ✚ Lesson results for 2 Jul (incl. archive copy)    [view] [skip]
 ✚ Student page S-046 — 1 new observation           [view] [skip]
UPDATED
 ✎ Lesson timeline — entry for this lesson added    [view] [skip]
 ✎ Course state — unit & next focus refreshed       [view] [skip]
 ✎ Misconceptions — 2 notes added                   [view] [skip]
REMOVED / REPLACED
 − Open follow-ups — 1 completed item removed       [view] [skip]
▸ Show technical details (file list & line diffs)
```

Implementation:
- `frontend/src/lib/review-brief.ts` — pure `briefFromChanges(items)`:
  deterministic categories (NEW when no previous content; REMOVED/REPLACED
  when the diff removes more than it adds; else UPDATED, via
  `computeMarkdownDiff`), friendly-name map per wiki path, count summaries
  ("2 notes added"), and pairing of the `raw/` archive proposal into the
  lesson-results item (teachers never see the raw layer).
- `ReviewBrief` / `ReviewBriefSection` / `ReviewBriefItem` components in
  `frontend/src/components/klassenpilot/review/`; [view] expands the
  unchanged detail card (diff + edit), [skip] unchecks with undo, "Save all"
  triggers the existing commit; `FileChangeReviewPanel` lives intact behind
  a "Show technical details" collapsible.
- Host: review step of `MemoryWorkspace`
  (`frontend/src/app/classes/[classId]/memory/page.tsx`).
- Optional polish: reword the SWE-ish `rationale` strings in
  `backend/app/teacher_agent/wiki/rollups.py` / `commit.py` for the detail
  cards.

Verification: `npx tsc --noEmit`, `npx vitest run` (tests for
`briefFromChanges`), backend pytest unchanged-green, manual smoke: log a
lesson → brief groups render; skip one item → only kept files committed.

> **Superseded (2026-07-05):** Milestones 2 and 3 below merged into the
> **Memory V3** effort after deeper root-cause analysis — see
> [`mem_v3/design.md`](mem_v3/design.md) (why + architecture),
> [`mem_v3/implementation_plan.md`](mem_v3/implementation_plan.md) (phases /
> PR boundaries), [`mem_v3/testing.md`](mem_v3/testing.md) (test-driven
> approach). The sweep brief (now "M1b") becomes mem_v3 Phase 6 and consumes
> the new card model. Sections below kept for history.

## Milestone 2 — Sweep dedup: never re-propose what was applied

Root cause: `_cluster_key()`
(`backend/app/services/memory_candidate_ledger.py`) is deterministic on
content, so a re-captured preference gets a new row with the same
cluster_key and status `captured`; `list_review_candidates()` never checks
whether an `applied` row already exists for that cluster_key.

1. At capture/insert: same cluster_key already applied → store new row as
   status `already_covered`, `rejection_reason="auto: duplicate of applied
   candidate <id>"` (statuses are free text; no migration).
2. Defensive filter in `list_review_candidates()`: exclude cluster_keys
   with an applied row.
3. Near-duplicates (different wording → different hash): feed the last ~20
   applied `candidate_update` texts per target into the sweep alignment
   prompt so the LLM marks them `already_covered` (card operation exists).
4. Tests: apply → re-capture in new session → absent from review list.

## Milestone 3 — Weaker signals for inferred preferences

Root cause: `teacher_preference_candidate()`
(`backend/app/teacher_agent/memory_capture.py`) hardcodes
teacher_explicit/explicit/high, and `_DURABLE_PREFERENCE_MARKERS` matches
loose phrases. Owner rule: only explicit future scoping ("always", "from now
on", "use this for all future briefs") justifies a durable rule.

1. Tighten markers to clearly future-scoped phrases only.
2. No marker → `inferred/low` → routed to the sweep queue, not instant apply.
3. Reinforcement threshold (openclaw-style): inferred/low clusters become
   sweep cards only after captures in ≥2 distinct sessions; expose
   `reinforcement_count` on the card ("seen 2×").
4. SAVE/SKIP rules (hermes-style) in `DURABLE_MEMORY_CANDIDATE_POLICY`
   (`backend/app/teacher_agent/prompts.py`): one-off formatting/task
   requests are weak signals, never durable rules.
5. Tests: one-off phrasing → inferred/low; future-scoped phrasing →
   explicit/high; once-seen held back, twice-seen proposed.

## Milestone 4 — Date awareness

1. Inject `Today is {YYYY-MM-DD} ({Weekday}). Lessons dated after today are
   planned, not yet taught.` into the shared teacher-context builder
   (`backend/app/teacher_agent/wiki/context_packs.py`) so ingest, plan, and
   sweep prompt stacks all receive it.
2. Data fix: demo workspace `class_state.md` stale "Last Lesson: 2027-02-03"
   → 2026-07-02.
3. Test: prompt-assembly test asserting the date line (freeze `date.today`).

## Milestone 5 — Reopen saved artifacts into a session

Mirror the `IngestStartHint` pattern for plans (plan page currently accepts
no hints; saved plans are dead ends).

1. `PlanSessionStartRequest {lesson_date?}` (`backend/app/schemas/api.py`);
   plan session POST accepts optional body.
2. `PlanService.start_session(class_id, hint)`: load saved `lesson_plan.md`
   into `session.partial_markdown`, patch planning runtime to phase
   `lesson_refinement` — mirrors `IngestService._apply_start_hint`.
3. `lib/api.ts` `startPlanSession(classId, hint?)`; plan page reads
   `?lessonDate=`, header "Editing plan for {date}".
4. Timeline + lesson detail: "Edit plan with agent" (lessons with plans);
   relabel taught-lesson action "Edit results with agent" (route exists via
   `intent=correct_existing_results`).
5. Tests: start-with-hint API test (draft contains saved plan, phase
   lesson_refinement); tsc.

## Parked

- **"Add one thing" delta flow** — adding a forgotten note without a full
  session + full re-review. No good design yet; revisit after Milestone 1
  (the skip/brief mechanics may suggest a shape).

## Design decisions taken

- Brief lines are deterministic (friendly-name map + diff counts), not
  LLM-generated — zero latency/cost; an LLM one-liner can be added later.
- Reinforcement threshold N=2 distinct sessions (Milestone 3).
- `raw/` archive proposal is hidden from teachers, paired with the
  lesson-results decision.
- Sweep dedup uses the free-text status `already_covered` (no migration).

---

## Implementation status

_Update this section as PRs land._

**Pre-milestone fixes — implemented on `chat_feature_improvments`:**

- [x] `chat_turn_failed` telemetry + SSE error line on stream failures
  (`backend/app/api/routes.py`)
- [x] StrictMode double-bootstrap dedupe — no more ghost sessions
  (`frontend/src/components/klassenpilot/artifact-session-page.tsx`)
- [x] Lesson-date guard: commit rejects dates >365 days ahead
  (`backend/app/teacher_agent/wiki/commit.py`)
- [x] Results-title cleaning — strips inherited "Lesson Plan —" prefix
  (`backend/app/teacher_agent/wiki/parsing.py`)
- [x] Timeline summary bullet-marker fix (`parsing.py`)
- [x] Seed wiki: bogus 2027-02-03 lesson removed, course_state restored

**Milestones:**

| Milestone | Status |
|---|---|
| M1a — Save-review brief | implemented — `lib/review-brief.ts` + `review/review-brief.tsx`, wired into both the memory-update review and the lesson-plan save review; detail cards & technical file list unchanged behind it. tsc + vitest green. Owner review round pending. |
| Memory V3 (supersedes M2+M3) — capture discipline, ledger gate, single-call sweep, budgets | **backend complete** — Phases 1–5 done and live: fixtures/goldens from real beta ledger; insert-time folding (cross-session re-statements reinforce clusters) + section vocabulary + gate/decay; capture discipline in the persistence path; `propose_memory_sweep_review` now runs gate → ONE consolidation call (`OPENAI_SWEEP_MODEL`) → structural validation → cards; two-pass packet machinery + lexical validators deleted (−2,182 lines); budget usage fed into the call (hermes-style page budgets already existed in `wiki/memory.py`). Open: live MBB trace re-run (`scripts/trace_memory_mbb_executive_consolidation.py`, needs API key) + DeepEval Tier-2/3 goldens. Next: M1b sweep brief (Phase 6, frontend PR). |
| M1b — Memory Sweep brief (mem_v3 Phase 6) | planned, after mem_v3 Phase 4 |
| M4 — Date awareness | planned |
| M5 — Reopen saved artifacts | planned |
| Parked — "add one thing" delta flow | parked |
