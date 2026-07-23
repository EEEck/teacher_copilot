# Pre-beta QA audit — 2026-07-21

Read-only QA pass before shipping to beta customers. **No code was changed.**
Scope: **risk-prioritized** code review (coupling / single-source-of-truth /
contracts / brittle saves — hot-spots read in full, the rest covered by
structure + grep, **not** an every-file line-by-line read), deterministic test
health, a tool-assisted dead/stale-code scan, and a live browser run of the full
`docs/beta_hitl_golden_e2e.md` playbook against a fresh beta Docker stack
(economy models, traces on).

**Review coverage:** the initial audit read ~7% in full; a **follow-up
full-read pass (§6)** then went through the remaining ~90% file-by-file (tracked
as 8 review tasks). Backend: every logic module full-read or read + grep-scanned
(agent core, memory subsystem, wiki package, services, api/config/cli). Frontend:
core engine + heaviest pages full-read, whole `src` scanned for design-system /
typing / SSE-duplication violations. Pure LLM-prompt strings (`prompts.py`) and
vendored shadcn primitives (`components/ui/*`) were skimmed, not line-audited.

Branch audited: `claude/pre-beta-audit-qa-0032c8` (0-diff from `main`, so findings
reflect the shipping code). Stack: `kp_wonderful_villani_01d4a8_e58bc7`
(frontend `:3270`, backend `:8740`), workspace `ws-hitl-110038`.

---

## TL;DR / go-no-go

- **One hard beta blocker found and reproduced end-to-end (🔴 F1):** a teacher
  with a *normal* lesson diary is blocked from saving in Update Memory because
  the deterministic student-reference verifier extracts ordinary prose (e.g.
  "The redox bridge worked well") as an unknown roster student and returns
  `409 write_verification_blocked` on `ingest/propose`. There is no legitimate
  way for the teacher to "resolve" a non-student. **This should block beta.**
- **The deterministic backend suite is red on `main`: 22 failing tests.** Most
  cluster on the same verification subsystem as F1; the rest is contract drift +
  one test-only bug. Shipping with a red suite is a process risk.
- **Otherwise the product is strong.** Discuss, planning, grounding/sources,
  executive guard (Hartree–Fock pushback), roster correction (S-006→S-046),
  Plan save, ledger staging, and Memory Sweep consolidation all behaved
  correctly live. Frontend shell composition and backend write contracts are
  well-architected.

Recommendation: **fix F1 (and green the suite) before beta; the rest are
post-fix hardening.**

---

## 1. Test health

Frontend: `tsc --noEmit` ✓, `vitest run` ✓ (incl. the chat-turn scenario matrix).

Backend `pytest` (worktree code, main venv, `-p no:deepeval`): **22 failed.**
Note: the run terminates before pytest prints its final summary line (a
pytest-asyncio teardown quirk on Windows) — the FAILED list is complete but the
pass total isn't emitted. Focused AGENTS.md subset was 67 passed / 1 failed.

Failures decompose into 4 clusters (not one cause):

| Cluster | Example tests | Nature |
|---|---|---|
| **Student-reference verification over-block** | `test_api_ingest::test_ingest_full_flow`, `…requires_lesson_results_approved`, `test_workflow_drafts::test_ingest_commit_stale_review_returns_409`, several stub/workflow goldens | **Real behavior** — same root cause as F1; `ingest/propose` now 409s on diaries that used to pass |
| **Verification-report contract drift** | `test_api_plan::test_plan_chat_returns_deterministic_verification_report` | Report now emits `student_leak`, `exit_buckets`, `task_alignment`; test still expects the old `…_provenance` shape. Test lag, not a broken feature (plan save verified working live). |
| **Capture provenance** | `test_mem_v3_capture::test_explicit_claim_with_scope_is_kept` (expects `teacher_explicit`, got `inferred_from_session`) | Possibly real, but **narrow** — live capture labeled explicit prefs `teacher_explicit` correctly (see ledger below), so this is a phrasing-specific edge, not universal. |
| **Test-only bug** | `test_beta_report::test_list_beta_testers_skips_disabled_by_default` → `FileExistsError … seed_wiki` | `seed_wiki.mkdir()` missing `exist_ok=True`; Windows temp reuse. Not a product issue. |

Some eval failures (`test_deepeval_model_receives_reasoning_effort`, layer
goldens) may partly be artifacts of `-p no:deepeval`; worth a clean CI re-run.

### Dead / stale code scan (tool-assisted)

- **Backend — clean.** `ruff --select F401,F811,F841` over `app/` = *All checks
  passed* (no unused imports, redefinitions, or unused vars). An orphan-module
  scan of all 72 `app/` modules found **no genuinely unused module** (the 5
  low-reference hits — `beta_cli`, `cli/repl`, `skills/chemie_bayern`,
  `package_renderer`, `stream_safety` — are all live via `python -m` entry
  points, `__init__` re-exports, or service imports). Only **14** staleness
  markers total across backend+frontend, and the "retired" references
  (`class_state.md`/`taught_so_far.md`, mem_v3 PR2) are **intentional migration
  comments** with active path-rewriting shims (`class_brief_service`,
  `wiki-viewer-links.ts`), i.e. cleanly retired, not rotting. (Deep unused
  *function/class* detection needs `vulture`, which isn't installed — not run to
  avoid a network install into the shared venv.)
- **Frontend — unverified.** There is **no dead-code guard**: `tsconfig` has no
  `noUnusedLocals`/`noUnusedParameters`, no knip/ts-prune/depcheck, and ESLint
  isn't configured. Unused exports/files/deps could accumulate silently. A
  `knip` run (needs a one-off `npx` fetch) would answer this — offered, not yet
  run.

---

## 2. Findings

Severity: 🔴 blocker · 🟠 fix-before-or-just-after-beta · 🟡 hardening/tech-debt.

### 🔴 F1 — Update-Memory save blocked by phantom "students" (roster verifier over-reach)

- **Where:** `backend/app/teacher_agent/roster_resolve.py`
  (`extract_reference_candidates`, `_BULLET_LABEL_RE` line 27, `_NAME_SPAN_RE`,
  `resolve_reference` → "not in roster" block at line 342-343), surfaced by
  `backend/app/teacher_agent/memory_verification.py` and gated in
  `backend/app/services/ingest_service.py:383` (`WriteVerificationBlocked`).
- **Root cause:** the extractor scans the whole diary and treats any bullet
  label (`- Something:`) or capitalized prose span as a *candidate student*.
  For `kind in {"label","id"}` an unmatched candidate is a hard **block**
  ("not in roster"). So ordinary lesson text becomes an unresolvable
  "student the teacher must fix against the roster."
- **Reproduced (deterministic tests):** fixtures flag `Homework`,
  `Rushed ending`, `## Student observations` as unresolved students.
- **Reproduced live (golden UM L1):** after correctly resolving the real S-006
  issue, the Save-prep flagged **"The redox bridge worked well (not in roster)"**
  and `POST …/ingest/…/propose` returned **`409 Conflict`** on every attempt.
  The wiki-change review / Save-all screen is never reached → **teacher cannot
  save the lesson.** The agent could not self-heal it either.
- **Blast radius:** high. Diaries routinely contain `- Homework:`,
  `- Exit ticket:`, section labels, and sentences starting with capitalized
  words. Many realistic diaries will hit this.
- **Nuance (in the product's favour):** on *student-ID-led* bullets
  (`- S-014 asked …`) the resolver is correct — it flagged S-006, validated
  S-014/S-021/S-033, and refused to fabricate. The bug is specifically the
  over-broad *candidate extraction*, not roster matching itself.

### 🟠 F2 — Contradictory teacher-facing block copy

The block surfaces `"message":"The draft is ready for the requested action."`
(and the live banner "…no blocking mismatch remains") **while** `status` is
`needs_decision` with an open blocking finding. The teacher is told it's ready
and simultaneously blocked. (`ingest_service` / `executive_verification`
default message; `memory_verification.build_memory_verification_report`.)

### 🟠 F3 — Deterministic suite red on `main`

22 failures (see §1). Even excluding F1's cluster, the verification-report and
capture-provenance tests are stale/unclassified. A green suite is table stakes
before a customer ships; right now a regression here is invisible.

### 🟠 F4 — SQLite stores have no concurrency hardening (systemic)

`workflow_drafts`, `memory_candidate_ledger`, `memory_sweep_reviews`, `beta`,
`memory_v4_debug_capture` all open bare `sqlite3.connect(...)` with **no
`busy_timeout` and no WAL**. The frontend polls `GET /api/workflow/active`
every 3 s (reads `workflow_drafts`) *during* turn writes, and beta telemetry
writes on every message → under concurrency SQLite's default 0 ms busy-timeout
raises `database is locked`. Also `workflow_drafts.save_from_session` does a
read-then-write revision bump across two connections (not atomic). Low
probability per single-user workspace, but a cheap, high-value hardening.

### 🟠 F5 — Contract single-source-of-truth drift

Three uncoordinated copies of the API contract with **no codegen**:
`backend/app/schemas/api.py` (Pydantic, authoritative), `contracts/openapi.yaml`
(documents **9 of ~60 endpoints**, untouched since 2026-05-27 while
`routes.py` changed 2026-07-20), and `frontend/src/lib/api.ts` (hand-mirrored TS
types). Drift is silent — nothing fails to compile if they diverge.

### 🟡 F6 — `MemoryWorkspace` is the brittle frontend surface

`frontend/src/app/classes/[classId]/memory/page.tsx` (~480 lines) carries
sessionStorage review persistence keyed on draft/rev/hash, a `beforeunload`
guard, four separate review-reset `useEffect`s, and an explicit **double-commit
idempotency guard** whose comment cites a real double-commit seen in beta
telemetry (lines 423-425). It works, but it's the highest-maintenance page and
asymmetric with the much simpler Plan review. Candidate for extracting a
`useMemoryReview` hook / state machine. (Note: shell composition elsewhere is
excellent — see Positives.)

### 🟡 F7 — `routes.py` monolith + repeated telemetry boilerplate

One 2613-line module, ~60 endpoints, three near-parallel workflow families
(discussion/ingest/plan). Each non-stream chat handler repeats the same 5
beta-telemetry calls (the stream path already shares
`_stream_chat_with_beta_telemetry`). Split into per-domain routers and a shared
non-stream telemetry wrapper.

### 🟡 F8 — Untyped `dict` passthroughs in the API contract

`memory_candidates: list[dict]`, `session_state`, `lesson_planning_state`,
`executive_state`, `memory_state` are untyped on both ends. Flexible, but the
frontend mirrors their shape implicitly (e.g. `memory/page.tsx` reaches into
`memoryState.target.lesson_date`). Typing at least `executive_state` and the
memory-candidate shape would harden the seam the review UI depends on.

### 🟡 F9 — Small correctness/robustness nits

- `memory_apply._normalize_operation` — ternary returns `operation` in **both**
  branches (dead no-op).
- `commit_ingest` gates on substring `"lesson_results.md" in u.wiki_path`
  (brittle path check; a path containing that substring elsewhere would match).
- `workflow_drafts` migrates only 4 columns via `_ensure_column`;
  `active_review_revision/hash` are only in `CREATE TABLE`, so a DB created
  before those columns existed wouldn't get them (low risk given greenfield).
- Every `/api/workflow/active` poll triggers a CORS preflight (no preflight
  caching) → 2 requests every 3 s per open tab.

### 🟡 F10 — Frontend has no dead-code / unused guard

No `noUnusedLocals`/`noUnusedParameters` in `tsconfig`, no knip/ts-prune/depcheck,
ESLint unconfigured. Unused exports, files, and deps can accumulate undetected.
Add `noUnusedLocals` + a `knip` CI check. (Backend is already covered by ruff.)

### Positives (explicitly validated — keep these)

- **Frontend shell composition is strong.** Plan / Update Memory / Discuss all
  compose the same `ArtifactSessionPage` + `ArtifactSessionWorkspace` +
  shared `Thread`/runtime + `ReviewBrief`; no forked SSE, message list, or
  one-off pages. `DESIGN.md`/`ARCHITECTURE.md` document and enforce the rules.
- **Backend write contracts are disciplined:** one typed
  `MemoryWriteSkill` per write (`memory_skills.py`), bounded apply helpers,
  optimistic-concurrency guards on save (`validate_review_snapshot` → 409), a
  shared streaming telemetry wrapper.
- Chat-turn resilience (live Reasoning, Running box, duplicate-send protection,
  off-page streaming) works and is regression-gated by the Vitest matrix.

---

## 3. Browser golden E2E results (full playbook)

Fresh beta stack, economy models, traces on. Turn-by-turn:

| Step | Result | Notes |
|---|---|---|
| Setup + beta login + profile | ✅ | Invite/login/mini-profile all worked |
| D1 session-only MBB tone | ✅ | Acked as session-only; **0** ledger candidates |
| D2 search last 3 lectures | ✅ | `read_lesson_range` on real dates 05-21/25/29; grounded summary, no invention |
| D2 Chemie 9 NTG guidance | ✅ | LehrplanPLUS source cards (Atombau / Erkenntnisgewinnung / Donator-Akzeptor), German source links |
| D3 humor + Dota/LC preference | ✅ | Acked; **1** global `teacher_profile.md` fast-lane candidate (`teacher_explicit`) |
| D4a Dota detour → task anchor | ✅ | Honest "depends on patch/team" + explicit return to the ochem task (beat the documented M4-LIVE-06 gap) |
| Plan L1 generate | ✅ | Grounded plan, redox→organic bridge, target 2026-09-28 (economy latency ~3.5 min — see below) |
| Plan L1 Hartree–Fock bait | ✅ | Executive guard held: refused HF/UHF as core, kept grade-9, offered teacher-only note |
| Plan L1 agree + kits/sketches pref | ✅ | Confirmed grade-9; staged class-scoped kits candidate |
| Plan L1 **Save → 2026-09-28** | ✅ | Wrote lesson_plan.md, redirected to lesson page with LehrplanPLUS citations; plan-save verification did **not** false-block |
| UM L1 ingest diary (incl. S-006) | ✅ | Target auto-confirmed to planned 2026-09-28; diary structured; 2 candidates staged |
| UM L1 roster check | ✅ | Correctly flagged S-006 not-in-roster, validated S-014/S-021/S-033, placeholdered rather than fabricating |
| UM L1 correction Mira → S-046 | ✅ | Resolved dominant student to S-046 |
| UM L1 **Save-all / Apply** | 🔴 **BLOCKED** | `ingest/propose` → **409**; phantom student "The redox bridge worked well". **F1.** Save unreachable. |
| Ledger state | ✅ | 5 well-formed candidates; correct scope/fast_lane/source (explicit→`teacher_explicit`, inferred→`inferred_from_session`) |
| Memory Sweep (step 9) | ✅ | Consolidated 5→3; pinned EXPLICITLY REQUESTED (humor + kits), grouped open-loop under ALREADY COVERED; Simple/Detailed toggle |
| FE stay/leave 6-pack | ✅ (via Vitest) | Matrix passed; live streaming/Running/duplicate-send observed |

**Coverage note.** Deferred to conserve real-model budget, since each adds
little beyond what passed/failed above: Plan cancel probes (throwaway), Plan L2
(repeat of the L1 path that passed), UM small probes S1/S2 (the S-006 roster
gate was exercised in UM L1), **UM L2 (would hit the same F1 propose block)**,
and Sweep *Apply* (optional per the playbook; stage-only review validated).

Other live observations: economy-profile **plan generation latency ~3.5 min**
(mitigated by the Running box + off-page resilience, but a real beta UX concern
if economy is default); and minor send-button hit friction during automation
(not a confirmed product bug).

---

## 4. Proposed fix plan (for your approval — no code changed yet)

Ordered by beta-gating priority; MVP-scoped.

**P0 — must fix before beta**

1. **F1 roster extractor over-reach.** Narrow candidate extraction so only
   real student references are considered — scope `_BULLET_LABEL_RE` to the
   student-observations section (or require an S-### / known-name affinity
   before a label/prose span can *block*), and downgrade unmatched free prose
   from `block` to ignore/soft-note. Add regression fixtures with the golden
   UM-L1 diary ("The redox bridge worked well", "Homework:", etc.).
2. **F3 green the suite.** After F1, update the verification-report tests to the
   new `student_leak`/`exit_buckets`/`task_alignment` contract, fix the
   `beta_report` `mkdir(exist_ok=True)` test bug, and re-run the eval tier
   without `-p no:deepeval` to confirm those aren't flag artifacts.
3. **F2 fix the contradictory block copy** — when there's an open blocking
   finding, don't emit "ready / no blocking mismatch remains."

**P1 — right after beta opens**

4. **F4 SQLite hardening** — set `PRAGMA busy_timeout` (e.g. 5000 ms) + WAL on
   every connection helper; make the `save_from_session` revision bump a single
   transaction. One small shared `_connect()` change per store.
5. **F5 contract SSOT** — generate `frontend/src/lib/api.ts` types (and/or
   `openapi.yaml`) from the FastAPI schema, or at minimum regenerate and CI-check
   `openapi.yaml` so drift fails the build.

**P2 — tech-debt / maintainability**

6. **F6** extract a `useMemoryReview` hook/state-machine out of `MemoryWorkspace`.
7. **F7** split `routes.py` into per-domain routers; share the non-stream
   telemetry wrapper.
8. **F8** type `executive_state` + the memory-candidate shape at the API seam.
9. **F9** the small nits (dead ternary, substring path check, preflight caching).

---

## 5. Not done / available on request

- **Full every-file code read.** This pass read ~7% in full and mapped the rest;
  a complete file-by-file review of the remaining ~90% (esp. `agents.py` 1359,
  `memory_sweep.py` 1164, `context_packs.py` 1028, `prompt_assembly.py` 918,
  `memory_candidate_ledger.py` 862, and the untouched frontend components) is a
  larger follow-up if you want line-level assurance.
- **Frontend dead-code scan** (`knip` — needs one `npx` fetch).
- **Deep backend unused-symbol scan** (`vulture` — needs a venv install).
- **Golden steps deferred:** Plan L2, UM L2, small cancel/probe turns, Sweep
  Apply (all low marginal value given §3).

## 6. Full-read pass findings (added after the initial audit)

Reading the remaining ~90% file-by-file, tracked as 8 review tasks. New findings
are numbered F11+. Overall the code is high quality; most notes are minor.

### Backend — agent core (agents/agent/tools/prompt_assembly/models/plan_verification/executive_verification/stream_events/citation/quality/workflow_contract/runtime_render)

Verdict: **well-architected.** Clean prepare/finalize/final-event split per
workflow, every LLM call has a deterministic fallback, prompt assembly doubles
as the debug trace (can't drift), progressive-exposure tool outputs (raw_ref),
one typed `remember` capture tool, backend-owned source provenance.

- **🟠 F11 — English-only routing heuristics (German audience).**
  `_is_high_stakes_student_request` (agents.py) and
  `_discussion_needs_full_subject_expert` (prompt_assembly.py) match English
  substrings (`grade`, `diagnose`, `introduce`, `scaffold`, `pedagog`, `how
  should i`). The users are German Gymnasium teachers who often type German, so
  the high-stakes student-decision guard and the full-subject-expert routing
  silently won't trigger on German input. (Citation/quality guards *are*
  bilingual — `source|quelle` — so this is scoped to the routing cues.)
- **🟡 F12 — F2 mechanism confirmed.** The teacher-facing block message is
  `WriteVerificationOutput.message` (defaults to "Verification complete."),
  chosen in `WriteVerificationBlocked.__init__` independently of the separate
  memory-verification *blocking finding*. Two sources → the "draft is ready"
  vs. "needs_decision" contradiction. Fix alongside F2.
- **🟡 F13 — scattered magic-number truncations.** tool output caps
  (6000/2500/1500/800), `_SSE_TRUNCATE=500`, `tool_output_limit=500` are inline
  literals rather than `context_limits` entries; harder to tune consistently.
- **🟡 F14 — `PlanTurnOutput` dual state path.** Keeps `session_state` +
  `lesson_planning_state` full-snapshot fields as a "compatibility fallback"
  next to the preferred `state_patch`; migration debt to retire.
- Confirmed: plan-verification rows (`student_leak`/`exit_buckets`/
  `task_alignment`) are advisory-only and **never block save** — so F3's
  `test_plan_chat_returns_deterministic_verification_report` failure is pure
  test-drift (matches the live Plan-save success).

### Backend — memory subsystem (memory_capture/memory_candidate_ledger/memory_gate/memory_targets/planning_state/memory_update_state/class_discussion_state)

Verdict: **model-quality.** Strong capture trust boundary (the model only
proposes speech_act/scope; backend verifies the teacher quote against the real
message and owns the fast-lane verdict, with defense-in-depth in
`is_fast_lane_row`). Controlled section vocabulary prevents cluster
fragmentation; persistence-gated promotion (explicit fast-lane OR ≥2 distinct
occasions); `_merge_state` never lets an empty model value wipe persisted state.

- **F11 scope grows to 4 heuristics.** Besides the two agent-core ones,
  `teacher_signals_plan_finalize` (planning_state.py) and
  `teacher_signals_finalize` (memory_update_state.py) also key on English
  acceptance phrases (`"ready to save"`, `"looks good"`, `"done"`). German
  acceptance won't auto-advance the phase (low impact — the Save button still
  works; but combined with the guard/routing cases, worth one bilingual fix).
- **F3 mem_v3 failure explained (not a clear bug):** `discipline_memory_candidates`
  now downgrades a `teacher_explicit` claim to `inferred_from_session` when it
  lacks a verified `Direct teacher quote:` token. `test_explicit_claim_with_scope_is_kept`
  encodes the pre-quote-provenance expectation → needs a product decision on
  whether explicit+scope without a verified quote should keep `teacher_explicit`,
  then update or fix accordingly.
- F4 confirmed on `memory_candidate_ledger` (bare `sqlite3.connect`, additive
  `_ensure_column` migrations).

### Backend — wiki package (store facade + 13 submodules)

Verdict: **clean.** `WikiStore` is a thin facade delegating to focused
submodules. Full-read: store.py, parsing.py, rollups.py, commit.py. Grep-scanned
the rest (context_packs, memory, search, trusted_sources, subject_frameworks,
read_api, indexing, paths_io, constants, registry, diary) — no TODO/FIXME, no
SQLite, no bare `except`, no `type: ignore`; term-loops are legitimate
search-relevance scorers over (English) wiki content.

- **Positive — the write path is idempotent, not brittle.** rollups upserts
  replace a `## {date}` section (drop-then-readd) so revising a lesson corrects
  in place; `_upsert_course_state` is a deterministic full re-projection.
  Directly answers the "brittle saves" concern for the wiki layer.
- **🟡 F15 — facade exposes many `_private` methods.** `WikiStore` surfaces
  ~30 underscore-prefixed methods that other modules (memory_apply, rollups)
  call as de-facto public API; the public/private boundary is blurred. Cosmetic.

### Backend — services (memory_sweep/artifact_session_service/artifact_spec/beta/ingest_service/plan_service/discussion_service/memory_sweep_reviews/beta_report/memory_v4_debug_capture/class_brief_service/stream_safety/output_safety/beta_cli)

Verdict: **sound.** No issue signatures (no TODO/bare-except/keyword heuristics).
`ArtifactSessionService` is a genuinely shared core for all three workflows
(spec-driven per mode; ingest/plan/discussion services are thin adapters — no
per-workflow duplication). Full-read: ingest_service.py + the F1 path in
artifact_session_service.py; grep-scanned the rest (validated live: sweep
consolidation, beta login/telemetry).

- **F1 path fully confirmed & shown deterministic.** `propose()`/`commit()` call
  `ensure_memory_verification()` → `_apply_workflow_verification` →
  `build_memory_verification_report` → `resolve_diary_student_references`
  immediately before the write gate, explicitly to stop the LLM clearing the
  finding (ingest_service.py:510-512). So the over-broad roster finding is
  re-injected every time → the 409 is guaranteed. **Fix must be in
  `roster_resolve` extraction; there is no LLM-side escape.** (The re-apply
  design is otherwise correct — it's the extractor that's wrong.)
- Save paths have real optimistic concurrency (`validate_review_snapshot`) and
  commit idempotency — not brittle.
- F4 confirmed across beta.py / memory_sweep_reviews.py /
  memory_v4_debug_capture.py (all bare `sqlite3.connect`).

### Backend — api/config/cli (routes remainder, deps, errors, config, context_limits, main, cli/*, lesson_package, package_renderer, skills)

Verdict: **clean, strong SSOT.** config.py is the tunables source of truth
(model profiles, reasoning tiers, all context caps); context_limits.py sources
everything from Settings — this largely mitigates F13 (only a couple of inline
tool-output truncations remain). errors.py centralizes a typed error envelope
with full-traceback logging.

- **🟡 F16 — unbounded per-workspace DI caches.** deps.py keeps module-level
  dicts (`_AGENT_CACHE`, `_INGEST_CACHE`, `_LEDGER_CACHE`, …) keyed by wiki root
  with no eviction; they grow one entry per workspace for the process lifetime.
  Negligible at beta scale; a latent leak for long-lived multi-workspace uptime.

**Backend summary: high quality.** The only beta blocker is F1; everything else
is hardening/tech-debt. No dead modules, no unused imports (ruff clean),
disciplined SSOT (targets, tunables, contracts), deterministic idempotent writes,
strong capture/verification trust boundaries.

### Frontend — features/lib + app pages + components (tasks 6–8)

Verdict: **strong, composable, disciplined.** Full-read: workflow-draft-store.ts,
turn-runner.ts, memory/page.tsx, memory-sweep/page.tsx (+ earlier plan/page.tsx,
api.ts). Grep/scan across all of `src`.

- **Core turn engine is principled, not brittle.** The zustand draft store is a
  documented reducer with an explicit (turn-record × snapshot → thread) decision
  table and named invariants; turn-runner.ts is a module-level SSE runner outside
  React (navigation never aborts a turn; only Stop/process-death do). Matches the
  passing Vitest scenario matrix.
- **Composition verified objectively:**
  - `fetch()` exists only in `api.ts` (one client); no `EventSource`/duplicate
    SSE (centralized in `sse-chat.ts`). No forked network layer.
  - **Zero ad-hoc hex in feature code** (only the `agent-mark.tsx` mascot SVG and
    vendored `ui/`+`assistant-ui/`). Design-system/semantic-token rule holds.
  - **Zero `: any` / `as any`** in non-test source. Strong typing throughout.
  - Plan / Memory / Memory-Sweep / Discuss all compose the same shells + shared
    review components; no one-off page chrome.
- **F6 refined:** the two Memory pages (`memory/page.tsx`,
  `memory-sweep/page.tsx`) are the heaviest surfaces — lots of local review
  orchestration/state — but they *compose* from shared components and the design
  system; the risk is orchestration complexity/maintainability, **not**
  copy-paste divergence. Extracting a `useMemoryReview` hook/state-machine is the
  main frontend cleanup. (F10: still no frontend dead-code guard.)

**Frontend summary: high quality.** No blockers; F6 + F10 are the only notes.

## 7. Fix progress — Bundle A (done; evals deferred)

Deterministic suite: **22 → 4 failures** (the 4 remaining are the eval-tier
goldens, deferred by decision). No commits yet.

- **F1 done (two-part fix).** (a) `roster_resolve` now scopes name/label
  extraction to the student sections (derived from the `LESSON_RESULTS_SECTIONS`
  SSOT, not hardcoded) with S-### ids still global; (b) `_BULLET_LABEL_RE` now
  excludes newlines (`[^:\n]`) — a genuine latent bug: `[^:]` matched across
  blank lines, so a bullet with no colon bridged to a later bullet's colon and
  produced a phantom multi-line "student" (e.g. `Active discussion - S-014`).
  Together these greened the whole ingest propose/commit family (incl.
  `test_ingest_full_flow`, the commit tests, and the `test_workflow_drafts`
  stale-review tests) plus the roster fixtures, and malformed ids now render in
  canonical `S-###` form. New regression test added.
- **F2 done.** `WriteVerificationBlocked` now surfaces the open blocking
  finding's own summary/question when a deterministic pack blocks after the
  write-verifier passed (no more "draft is ready" while blocked).
- **F3 partial.** Green: `test_api_plan` verification-report keys (advisory rows
  are test-drift, confirmed); `test_beta_report` `mkdir(exist_ok=True)`.

**Resolved after investigation:**

1. **🔴→✅ plan safety-hold was a REAL bug (now fixed).** At save,
   `normalize_plan_target_date` stamped the lesson date into the plan, changing
   its fingerprint *after* the safety review ran on the un-stamped draft — so the
   completed `safety_hold` report stayed pinned to the un-stamped fingerprint,
   `evaluate_write_gate` could no longer match it, and **the plan safety gate was
   silently bypassed** (a plan flagged for a severe safety issue could be saved).
   Fix: **verify and gate the exact undated draft the teacher reviewed, and stamp
   the lesson date only into the persisted file after the gate passes** — the
   date is a deterministic final-write transform, not reviewed content, so it
   must not enter the verified fingerprint. Behavior is unchanged (the draft
   stays undated; a blocked save leaves it undated); only the safety hole closes.
   This belongs on the beta-blocker list alongside F1.
2. **mem_v3 capture (4 tests) — confirmed intentional mem_v4 hardening, tests
   updated.** git history + `docs/mem_v4/brainstorm.md` confirm capture was
   deliberately tightened to require claim↔quote grounding (mem_v3's
   scope-marker / whole-message-quote approach over-emitted fast-lane
   candidates). So the code is correct; the 4 mem_v3 Phase-3 goldens were
   superseded and now supply real mem_v4 grounding (scope + verified quote) to
   exercise the kept/fast-lane path. Not a regression.

**Deferred (by decision): the 4 eval-tier goldens** — `chat_stub[9b_ingest_turn3_ready]`
/ `workflows_stub[9b_memory_update_3turn]` (ready-state) + `layers` ×2
(context-layer). Triage against the eval tier in a separate pass (they run under
deepeval; may just need a golden refresh).

## 7b. Roster resolution redesign (supersedes the F1 section-scoping patch)

After review, the F1 patch (section-scoping + newline fix) was replaced by a
cleaner design that matches how teachers actually work (they write names, often
typo'd — not `S-###`) and the principle **false positives are worse than false
negatives** (a bad block is worse than a missed note the teacher will catch).

- **Name→id resolution at the write boundary.** New
  `roster_resolve.resolve_student_observations()` resolves each observation's
  *subject* (a structured field — the token before the colon, or a `## Subject`
  heading), never free prose, so there is no NER-over-sentences brittleness. It
  maps names → roster `S-###` via exact → alias → `rapidfuzz`. The write path
  (`_finalize_lesson_writes`, `_compile_students_and_timeline`) writes only
  observations that resolve; unmappable subjects are **skipped and warned**,
  never fabricated, never silently dropped.
- **Weak guard.** The deterministic `memory-student-references` finding is now
  **advisory, not blocking** — a subject we can't map can never hard-block a
  save. `memory-target-date` stays blocking. Safety now lives in the write rule
  ("only write what maps"), not a pre-save block.
- **Warnings surfaced** in `CommitIngestResponse.warnings` ("couldn't save
  'Jens Haller' — fix the name or add to the roster"). Fuzzy matches write but
  emit a "confirm this is the right student" note.
- **Deleted the whole superseded extraction subsystem** (`_BULLET_LABEL_RE`,
  `_NAME_SPAN_RE`, `extract_reference_candidates`, `resolve_diary_student_references`,
  section-scoping) — removes more than it adds. Also fixed a latent
  `extract_section_body` over-capture of empty sections (resolver stops at any
  known diary-section heading, SSOT-derived).
- **Aliases:** not hand-curated — `rapidfuzz` + auto prefix-keys cover typos /
  initials; genuine nicknames (which neither fuzzy nor the LLM can invent) fall
  to warn-and-skip and are a future "learn on teacher confirmation" enhancement.
- This is the P0 **Input-to-wiki reconciliation** roadmap slice. Tests rewritten
  to the advisory/write-resolve contract; full deterministic suite green.
- **Follow-up (small):** frontend display of `CommitIngestResponse.warnings` in
  the "Memory saved" card (backend returns them; UI doesn't show them yet).

## 7c. Plans no longer carry an echoed target date into verification

Investigation of "the backend blocks plans with wrong dates":

- There is **no deterministic date-block for plans** (`validate_lesson_date` /
  the 365-day cap is Update-Memory-only; no plan-target-date runtime compare;
  `empty_plan_template` is `""`).
- "Target date" appears in **no prompt or template** — the model **echoes** the
  date from the teacher's request, and `_finalize_plan_turn` kept it, so it
  reached the LLM write-verifier at save. A "wrong"/past echoed date could then
  draw a blocking `time_state`/planning-assumption finding (LLM-driven, so a
  clean date passed while an odd one could block).

Fix (matches the safety-gate contract: date = post-save stamp, selector-owned):
`_strip_plan_target_date` now removes any echoed `Target date:` at plan-turn
finalize, so the draft is **dateless** — nothing date-related reaches the write
verifier, and the teacher-selected date is stamped into the persisted file only
(`normalize_plan_target_date`, after the gate). Prose dates (e.g. "review the
2026-05-25 lesson") are untouched. Unit test:
`test_strip_plan_target_date_drops_echoed_date_keeps_content`.

## 8. Fix progress — Bundle B (done)

Backend deterministic suite (excl. evals): **all green**. Frontend: `tsc` ✓
(with new guards), `vitest` **167/167** ✓. No commits yet.

- **F4 done** — new `app/services/sqlite_util.connect()` sets
  `PRAGMA busy_timeout=5000` on every connection; wired into all 6 SQLite stores
  (workflow_drafts, ledger, sweep_reviews, beta, beta_report, debug_capture).
  WAL deliberately **not** forced (hosted beta targets EFS/NFS, where SQLite WAL
  is discouraged); `busy_timeout` fixes the lock-contention risk safely.
- **F9 done** — removed the dead `_normalize_operation` ternary; `commit_ingest`
  now matches `…/lesson_results.md` by path suffix, not substring; added
  `_ensure_column` migrations for `active_review_revision/hash`; set
  CORS `max_age=3600` so the 3s poll stops re-preflighting.
- **F10 done** — added `noUnusedLocals`/`noUnusedParameters` to tsconfig; the
  guard immediately caught **3 real dead imports** (`Link` in beta login, `React`
  in two test files) — removed. `knip` deferred (needs an `npx` install).
- **F11 done** — added distinctive German terms to all 4 English-only heuristics
  (high-stakes guard, discussion subject-expert routing, plan- and ingest-
  finalize signals).
- **F13 done** — the two streamed tool-output caps now come from
  `Settings.agent_tool_stream_chars` (one tunable) instead of hardcoded `500`.
- **F16 assessed, intentionally left.** The per-workspace DI caches hold
  `ArtifactSessionService` with in-memory sessions; naive eviction would drop
  live/in-flight turns. Growth is negligible at beta scale (a handful of
  workspaces). Proper fix = idle-TTL eviction, a post-beta item — not a safe
  quick change.

**Audit correction:** §1 reported frontend `vitest` fully green. That was wrong —
a `| tail` pipe masked vitest's non-zero exit (same trap as the pytest totals).
There was **1 pre-existing** failing frontend test
(`artifact-session-workspace.test.ts`, brittle exact-className match that drifted
when the component moved to `ResizablePanel` on 2026-07-20). The layout intent
(diff pinned to 70%) was intact; the test now asserts the durable tokens and
passes.

### Deferred (unchanged): Bundle C refactors (F5/F6/F7/F8/F14/F15) + the 4 eval-tier goldens.

## Appendix — how to reproduce

```powershell
# Fresh beta stack (from this worktree root)
scripts\worktree-stack.cmd up --beta --fresh-beta-data --fresh-wiki --app-env development --model-profile economy
# provision a tester, then drive docs/beta_hitl_golden_e2e.md
```

F1 fires at UM step "Save all / Apply": watch for
`POST …/ingest/…/propose → 409` in `docker compose logs backend` and the
"unresolved: <non-student sentence> (not in roster)" banner. Deterministic
repro without the browser: `pytest tests/test_api_ingest.py::test_ingest_full_flow`.
