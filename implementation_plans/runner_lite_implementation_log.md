# Runner-lite implementation log

Design: `docs/beta_readiness_audit_2026-07-13.md` Appendix A.1 (v2, all
questions resolved 2026-07-14). One entry per step; each step leaves
`npx tsc --noEmit && npx vitest run` green.

Planned steps:

1. **A.0 hotfix** — stable `EMPTY_THREAD` selector (exported selector factory)
   in the store + regression test (invariant I6).
2. **Store** — `turnByDraftId` phase map; runner-facing actions
   (`beginTurn` / `applyTurnProgress` / `completeTurn` / `markAwaitingBackend`
   / `failTurn`); snapshot reducer table in `upsert` (replaces
   `shouldKeepLiveThread`; keeps `mergeFinalReplyIntoThread` for the
   `awaiting_backend`+complete row); snapshot gains `readyToSave` /
   `lastChangeSummary`; I5 guards. Reducer unit tests, one per table row.
3. **Turn runner** — `turn-runner.ts` (module controllers map, `runTurn`,
   `cancelTurn`, `hasLiveRunner`), stream-end classification confined here;
   failure toast (Q5) + marker clear on `failTurn` path (side effects live in
   the runner, store actions stay pure — deliberate deviation from A.1.5
   wording, noted). Runner unit tests with fake SSE generators.
4. **Provider slim-down** — `ArtifactSessionRuntimeProvider`: delete
   unmount-abort, `finally` race-guard, six mirrored states + 2 sync effects;
   `onNew` → marker + `runTurn`; `onCancel` → `cancelTurn`; flags/meta from
   store selectors; recovery poll condition from §A.1.7. Context value shape
   unchanged (workspaces untouched). Discard call sites gain `cancelTurn`.
5. **Scenario tests rework** — leave-mid-turn asserts the thread keeps growing
   after "unmount"; new hard-refresh, Stop, and discard-mid-turn scenarios;
   retire abort-on-leave cases with the behavior.
6. **Full suite + browser pass** — `tsc`, `vitest`, then scenarios 1/2/4/5/8
   from §A.1.9 in the dev stack, watching assistant-ui issue #2603
   (`isRunning`) per §A.1.15.

---

## Log

### 2026-07-14 — Step 0: setup

- Design v2 signed off (A.1.14 all resolved). Decisions folded into docs:
  v1.1 backlog item for server-side cancellation; `settled` limitation
  documented in §A.1.3; failure toast in scope; marker system lives only
  until M2.
- Best-practice review added as §A.1.15 (validates P3 and the M3 deferral;
  adds assistant-ui `isRunning` watch item to the browser pass).

### 2026-07-14 — Steps 1–5 implemented (tsc + 157 vitest tests green)

**Step 1 — A.0 hotfix.** `EMPTY_THREAD` + exported `selectThreadMessages`
selector factory in the store; `workflow-chat-runtime.tsx` now uses it
(inline `?? []` removed). Regression test asserts reference identity for a
missing key.

**Step 2 — store.** `workflow-draft-store.ts` rewritten around the §A.1.4
reducer: new `turnByDraftId` phase map; actions `beginTurn` /
`applyTurnProgress` / `completeTurn` / `markAwaitingBackend` / `failTurn` +
`applyDraftPatch`; snapshot gains `readyToSave` / `lastChangeSummary` /
`memoryCandidates`. Deleted: `shouldKeepLiveThread`, `threadHasRichParts`,
`lastAssistantLacksText` gating. Kept: `mergeFinalReplyIntoThread` (used by
the two `awaiting_backend` resolution rows only; the interrupted row reuses it
with a synthetic error message). 18 unit tests, one per reducer row + actions
+ guards (I5) + selector identity (I6).
  - Deviation from A.1.5 wording: `failTurn` (store) is pure state; the
    *runner* clears the marker and fires the failure toast — side effects
    stay out of the store.
  - Addition found during implementation: `applyDraftPatch` must also carry
    the PATCHed `artifactMarkdown`, otherwise the store→editor sync effect
    could revert a teacher edit to the stale mirror.

**Step 3 — runner.** `turn-runner.ts`: module `controllers` map, `runTurn` /
`cancelTurn` / `hasLiveRunner`; stream-end classification delegates to the
existing `resolveClientStreamEnd` (kept in `workflow-turn-state.ts`), with
explicit abort → `awaiting_backend`; hard failure clears the pending marker
(injectable `pendingStorage` for tests) and fires the Q5 failure toast when
off-page. `chatFailureToastLabel` upgraded to mode-specific retry copy.
Shared error copy moved to `chat-errors.ts`.

**Step 4 — provider slim-down.** `artifact-session-runtime.tsx` rewritten:
deleted the six mirrored `useState`s, both sync effects, the unmount-abort,
the `finally` race-guard, and the in-component SSE loop (−~180 lines of
lifecycle code). `onNew` = marker + `runTurn`; `onCancel` = `cancelTurn`;
flags/meta/activity derive from store selectors; recovery poll condition is
now `awaiting_backend || (no record && snapshot.turnInProgress)`. Context
value shape unchanged — no workspace/page changes needed beyond discard:
memory + plan discard flows now call `cancelTurn` before `remove` (I5).

**Step 5 — scenario tests.** `chat-turn-scenarios.test.ts` rewritten to drive
the REAL runner + store singleton with controllable fake SSE streams
(closes the audit's "false green" gap at the unit level): stay-on-page,
leave-mid-turn (thread keeps growing after leave; later flat upsert cannot
flatten the settled thread), hard-refresh, Stop→merge, dropped-stream→
awaiting_backend (marker kept), fail-before-content (marker cleared once,
error reply), duplicate-send no-op, discard-mid-turn (late events no-op).
8 scenarios × 3 modes = 24 tests.

**Suite:** `npx tsc --noEmit` clean; `npx vitest run` 31 files / 157 tests
green.

### 2026-07-14 — Step 6: browser verification pass (prod mode, sandbox wiki)

Dev stack on 8011/3001, `APP_ENV=production`, `MODEL_PROFILE=production`,
`WIKI_ROOT=teacher_wiki_sandbox`. Results against the §A.1.9 scenarios:

- **Scenario 8 — discard → fresh send (Bug A regression): PASS.** Discarded
  the resumed draft, sent immediately; no console errors (previously:
  "Maximum update depth exceeded" swallowed by the error boundary), stream
  rendered live with Reasoning + tool call + Stop button.
- **Scenario 1 — stay on page: PASS.** Live reasoning/tool parts; Stop button
  present while streaming (assistant-ui issue #2603 watch item: `isRunning`
  behaves); final reply + diary update landed; spinner cleared.
- **Scenario 2 — leave mid-turn (client-side nav), return: PASS.** Clicked
  "← Class home" mid-stream (class home rendered fully — no H1 hang), returned
  via "Update memory": full rich thread (reasoning + tool call) AND the final
  reply present; turn had completed in the background runner. This is the
  path that previously froze parts or lost the reply.
- **Scenario 5 — Stop button: PASS.** Stop aborted the client stream
  (composer flipped to Send immediately); the backend finished; the recovery
  poll merged the full reply into the rich thread (reasoning + 5 tool-call
  parts preserved). No stuck spinner.
- **Scenario 4 — hard refresh mid-turn: PARTIAL.** The refresh itself behaved
  correctly, but the in-flight turn genuinely failed server-side mid-test
  (OpenAI quota exceeded), so the bootstrap correctly rendered the
  *interrupted-turn* alert instead of "Still working…" — which is the right
  UI for that state and incidentally live-verified the interrupted path. The
  "refresh → Still working → poll completes" variant is covered by the unit
  scenario tests; re-run in the browser when API quota is available.

Live testing ended by OpenAI quota exhaustion (billing, not a product bug).

**Open items:** re-run scenario 4 end-to-end when quota resets; commit/PR
after Matthias reviews the diff.

### 2026-07-14 — Step 6 completed: full browser acceptance pass (dev + economy)

Re-ran on `APP_ENV=development`, `MODEL_PROFILE=economy` (gpt-5.4-mini) at
Matthias' request — the chat lifecycle is model-agnostic and this cuts token
cost. Cleared workflow drafts + restarted backend for a clean slate. Dev mode
also streams raw CoT, so reasoning parts are directly visible. All four
acceptance criteria PASS:

1. **Live SSE reasoning + tool calls (on page):** user msg → streamed reasoning
   (raw CoT) + tool calls ("Patching lesson results", "Updating diary markdown")
   → final reply; target resolved to 2026-10-05; diary updated. Turn settled
   cleanly (Send button back, no spinner).
2. **Leave/return + hard refresh:** in-app nav to class home mid-turn (class
   home rendered fully — no H1 hang; Running box visible), turn completed in the
   background runner, return to memory showed the full completed reply — no lost
   parts, no stuck spinner. Hard refresh mid-turn showed persisted plain
   messages (rich parts dropped, as accepted).
3. **Still-working → final → spinner clears:** cleanest via hard refresh into a
   running turn — "Still working on your response…" with persisted messages and
   no Stop button, then the recovery poll landed the final reply and cleared the
   spinner. Stop button also verified: aborts the client stream, no stuck
   spinner, reply lands complete with rich parts preserved (the transient
   "Still working" is sub-second with the mini model, so best observed via the
   refresh path).
4. **Running box + completion toast:** Running box appeared during the turn and
   cleared on completion; the off-page completion toast "Finished updating
   memory" fired (caught via in-page polling at ~6.8s).

Also re-confirmed the **Bug A regression** (discard → immediate send): no
"Maximum update depth" crash, clean stream.

**Tooling note (not a product issue):** after a browser-pane window resize, the
Browser tool's *synthetic* clicks/keys stopped reaching the assistant-ui
composer (typed text went to `document.body`; Send/Enter were no-ops). Driving
the composer via real DOM calls (`textarea.focus()` + `sendButton.click()`)
worked immediately and `onNew` fired end-to-end — i.e. the app is fine; it was
a pane input glitch. Worth knowing for future browser passes.

**Suite after debug-log cleanup:** `tsc` clean; `vitest run` 157/157 green
(one transient flake in a pre-existing slow render test — ReviewBrief /
thread-background-status, ~2–4.5 s — cleared on re-run; runner scenario tests
24/24 stable across repeated runs). Debug `console.log`s removed.

**Status: runner-lite verified end-to-end, ready to commit.**

### 2026-07-14 — Post-review lightweight refactor (commits `5f87089`, `de01b4c`)

Embedding review of the shipped changes against the original asks surfaced
three items, all applied after sign-off:

1. **H2 v2 — dateless drafts.** The v1 placeholder (`Target date: (set when
   saving)`) contradicted the plan prompt's mandated structure, which has no
   Target date line. Template now emits only `> Duration: 45 min`;
   `normalize_plan_target_date` stamps the date onto the Duration line at save
   (replace branch kept as defense, regex hardened to stop at `|`). Dead
   `lesson_date` param dropped from `empty_plan_template`.
2. **Store reducer merge gap.** `upsert()` full-replaced snapshots while draft
   GET responses never carry `readyToSave` / `lastChangeSummary` /
   `memoryCandidates`, so notifier/recovery upserts silently reset what
   `completeTurn` wrote. `upsert` now treats undefined as "unknown, keep
   existing" for those three fields (same semantics as `applyDraftPatch`);
   regression test added.
3. **Dead code:** `applyBackendDraftFlags` + its test deleted (zero call
   sites).

Suite: backend H2 tests 9/9 hermetic; frontend `tsc` clean, 157/157 (one
known pre-existing slow-render flake on cold runs, passes on re-run;
workflow-drafts suites 57/57 stable across repeated runs).

### 2026-07-15 — Phase-vocabulary unification (H2-v2-style embedding pass)

Applying the same "read the surroundings" lens that produced H2 v2 to
runner-lite found the codebase carrying **two phase vocabularies**: the old
hybrid's 5-phase `WorkflowTurnPhase` (`workflow-turn-state.ts`) and the store's
real 3-phase `TurnPhase`. The old file survived only as two trivial lookups —
`flagsForPhase` (4 store call sites, each discarding one of the three returned
fields) and `resolveClientStreamEnd` (one runner call site, always
`gotFinal:false`, i.e. a ternary needing vocabulary translation back). Applied:

- Inlined the four two-boolean flag writes in the store actions (with comments
  on the non-obvious pairs) and the abort/streamed ternary in the runner.
- Deleted `workflow-turn-state.ts` + its test (~70 lines, one whole concept).
- `frontend/ARCHITECTURE.md` updated to describe the runner-lite lifecycle
  (it still documented the old hybrid), the 24-scenario test matrix, and the
  M1 Upcoming-card change.

Also recorded (NOT applied — expanded M2 scope in the redesign plan): the
provider recovery poll and `completeTurn`'s `snapshot.messages` mirror exist
only to compensate for / feed the legacy marker heuristics; both get deleted
with the markers in M2. Verified: markers survive hard refresh and the
root-layout notifier covers all happy paths through the same reducer.

Suite after: `tsc` clean; 153/153 (4 tests removed with the deleted file).
