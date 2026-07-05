# The KlassenPilot Memory Approach — A Teaching Guide

Audience: anyone (human or agent) who needs to understand how this system
remembers things — and why it remembers so little on purpose. `design.md`
says *what* we built, `learnings.md` says *what went wrong before*; this doc
teaches the approach from first principles. If you are an agent being primed
to work on this codebase, read the "Priming block" at the end first, then
come back.

## 1. The problem, as a story

A teacher finishes a chemistry lesson and tells the copilot three things in
one breath: the class finally moved from redox into organic chemistry, the
molecule kits worked better than formal notation, and "can you organize the
lesson results in a mbb style so it is easier to review."

A naive memory system saves all three, every time they come up, in whatever
words they arrive in. Our first beta did exactly that: one day of testing
produced twelve stored candidates encoding four actual facts, the one-off
formatting request became a permanent global communication rule approved six
separate times, and the weekly review became a wall of near-duplicate cards
with internal error ids leaking into teacher-facing text.

The goal is the opposite: **a curated memory small enough to read, built
from claims the teacher actually made, surfaced for review at most once,
writable only with the teacher's approval.** Every mechanism below exists to
serve one of those four clauses.

## 2. The axioms

1. **The teacher owns every durable write.** No memory file changes without
   an approval click. This is non-negotiable and shapes everything else:
   because review is expensive teacher attention, the system's real job is
   *minimizing what needs reviewing*.
2. **Memory is plain markdown the teacher can read and edit.** No
   embeddings, no vector store, no graph database. A memory the owner cannot
   inspect is a liability in a school context.
3. **Memories come from the teacher's words.** The agent never memorializes
   its own output — plans it wrote live in the saved plan artifact, not in
   memory. Self-sourced memories compound: the agent plans from memory,
   memorizes its plan, and the loop reinforces itself.
4. **Silence is the normal outcome.** Most chat turns produce zero memory
   candidates. A system biased to notice things drowns; one biased to
   silence stays legible.
5. **Attention must be earned.** An inferred observation needs independent
   reinforcement (seen in ≥2 sessions) before it may ask for teacher time.
   Only an explicit, future-scoped teacher request ("from now on…", "for all
   briefs…") skips the queue — and even then it only skips *ahead*, never
   *past* review.
6. **Deterministic code owns structure; the model owns meaning.** Folding,
   gates, budgets, id checks, and no-op demotion are plain code. Judging
   whether "MBB style" and "executive communication" are the same preference
   is the model's job — validated structurally, never second-guessed with
   token matching.
7. **Rare calls deserve strong models and full context.** Consolidation runs
   about weekly on a teacher click. At that frequency, token thrift is a
   false economy: one big call on the strongest reasoning model, seeing
   everything at once, beats a pipeline of small cheap calls that each see a
   fragment. (Verified live: the mini model repurposes unrelated bullets;
   the strong model consolidates correctly and even flags in-batch
   duplicates unprompted.)

## 3. The life of one claim

Follow "keep redox review brief now that we've moved to organic chemistry"
from the teacher's mouth to durable memory. Three lanes, one gate, one call.

**Lane 1 — Capture (during chat, cheap, silent by default).**
The chat agent emits a review-only candidate because the teacher stated a
class-state change. Capture discipline applies immediately:
- grounded in the teacher's words (axiom 3);
- no future-scoped wording → even if the model labels it
  `teacher_explicit/high`, the backend downgrades it to a weak inferred
  signal (`discipline_memory_candidates`);
- at insert (`insert_with_folding`, no LLM): the free-form section name the
  model invented ("organic_chemistry_lesson_design") is normalized onto a
  fixed vocabulary; if a near-duplicate open claim exists — measured with
  stemmed content tokens and the overlap coefficient, threshold calibrated
  on recorded beta data — the new row **joins that claim's cluster** instead
  of becoming a new one. An identical re-statement in a *new* session is the
  strongest reinforcement signal; the same statement twice in *one* session
  is noise. Re-captures of already-applied content are neutralized as
  `already_covered`; re-captures of teacher-rejected content are
  `suppressed` (rejections have teeth).

**The gate (deterministic, invisible).**
The claim's cluster now has rows from two different sessions → it passes the
promotion gate (`memory_gate.py`). Had it stayed a singleton, it would wait,
and after ~6 weeks unreinforced it would expire silently. The ledger is
invisible staging — human-in-the-loop applies to *writes*, not to *staging*.

**Lane 3 — The sweep (teacher-clicked, one strong call).**
When the teacher hits "Memory Sweep", the backend assembles ONE call:
- all gate-passing claims with reinforcement metadata (seen 4×, 3 sessions,
  first/last seen, explicit flag);
- every in-scope memory file with its bullets **enumerated by ephemeral
  ids** (`M2_1: **Current Unit:** Practicing redox half equations…`);
- recently applied and recently rejected texts per file;
- per-file budget usage ("412/1500 chars");
- today's date.

The model returns mem0-style ID-referenced operations:
`add` / `update(id, new_text)` / `delete(id)` / `none` — every claim id
accounted for exactly once, ids copied from the input only. Our claim comes
back as `update(M2_1)`: the current-unit bullet is a *temporal* fact, so the
newest claim supersedes it even though "organic chemistry" shares no words
with "redox half equations" — the exact case that deadlocked V2's lexical
validators. Validation is structural only; a failed call (after one retry)
becomes a single plain-language notice, never a pile of fallback cards.

**Review and write.**
The operation renders as one row in the sweep brief — old text struck
through, new text below, "seen 4×" — under "Changed (old → new)". Explicit
asks would be pinned above it. The teacher taps ✓; the apply layer replaces
exactly that bullet (verbatim-quote check), clamps the page to its hermes-
style character budget, and marks all four ledger rows `applied`. Future
re-captures of this claim now fold into `already_covered` on arrival — the
teacher will never be asked about it again.

**Injection.** Only the curated markdown files enter prompts, inside hard
page budgets. The ledger never does.

## 4. Where this sits in the landscape

| System | Capture | Dedup/consolidation | Human review | What we took |
|---|---|---|---|---|
| **mem0** | LLM fact extraction per add | v2: LLM ADD/UPDATE/DELETE/NONE vs existing; v3 add-only, resolve at retrieval | none | the ID-referenced operation contract; "facts from user messages only" |
| **Zep/Graphiti** | per-episode graph extraction | temporal validity windows: close old fact, open new | none | supersession-over-conflict for current-state facts |
| **Letta** | agent tool calls into bounded blocks | sleep-time agents consolidate in background ([sleep-time compute](https://www.letta.com/blog/sleep-time-compute/), [paper](https://arxiv.org/html/2504.13171v1)) | none | budget-exceed forces consolidation; the sleep-time framing of our sweep |
| **Hindsight** | fact-level retain | write-time entity resolution + dedup ([consolidation blog](https://hindsight.vectorize.io/blog/2026/05/21/agent-memory-consolidation)) | none | "write time is the cheapest place to control quality" |
| **OpenClaw** | passive daily notes | dreaming phases promote on thresholds (score, recall count) | optional preview | the promotion gate: reinforcement before attention; silent decay |
| **Hermes** | agent sees memory in prompt, writes via tool | exact-dup rejection + hard char budgets | user edits files | bounded stores; "nothing to save" as expected outcome; frozen snapshot |
| **KlassenPilot** | disciplined chat capture → invisible ledger | deterministic write-time folding + gate + ONE strong-model consolidation call | **every durable write** | — |

Our distinctive position: everyone else consolidates *for* the user; we
consolidate *for review by* the user. That makes review-volume the scarce
resource, which is why we gate harder than any of them — and why the
consolidation call must produce few, correct, well-scoped proposals rather
than many plausible ones.

## 5. Priming block (for agents)

If you are an agent working on KlassenPilot memory, internalize this:

```text
KLASSENPILOT MEMORY — CORE APPROACH
- Durable memory = small curated markdown files with hard char budgets,
  injected into prompts. Everything else is staging.
- Never write durable memory directly. Chat emits review-only candidates;
  only /memory/apply and /memory/sweep/apply write, after teacher approval.
- Capture: teacher's words only; never memorialize agent output; silence is
  the normal outcome; teacher_explicit/high requires future-scoped wording
  or the backend downgrades it.
- Ledger (SQLite, invisible): insert_with_folding dedupes deterministically
  (section vocabulary; same-session exact dup = noise; cross-session
  exact/near dup = reinforcement, joins cluster; applied → already_covered;
  rejected → suppressed unless a fresh explicit ask).
- Gate: explicit asks always sweep-eligible; inferred needs ≥2 distinct
  sessions; stale singletons expire silently at ~42 days.
- Sweep: teacher-clicked; ONE call on OPENAI_SWEEP_MODEL (strong reasoning
  model, non-negotiable); input = claims + enumerated memory bullets with
  ephemeral ids + applied/rejected history + budgets + today; output =
  add/update(id)/delete(id)/none covering every claim id exactly once.
- Validation is structural only (coverage, id existence, verbatim quotes,
  no-op updates demoted to none). NEVER add lexical/semantic validators —
  V2 died of them. Teacher review is the semantic safety net.
- Failures collapse to one plain notice; internal reasons go to logs, never
  to teachers.
- Current-state facts (class_state) are temporal: newest supersedes oldest
  even with zero word overlap.
- Tests: contract goldens run offline on recorded beta fixtures
  (tests/fixtures/mem_v3/); behavior is pinned by live traces
  (scripts/trace_memory_mbb_executive_consolidation.py must report
  passed=True); production metric is memory_sweep_propose card/warning
  counts in telemetry.
ANTI-PATTERNS: capture from agent output; per-turn LLM memory calls;
partitioning consolidation input by unnormalized model output; token-overlap
semantic gates; per-candidate fallback cards; hardcoding regression labels
(MBB/McKinsey) into prompts; silently writing memory.
```

## 6. Pointers

- Capture discipline: `backend/app/teacher_agent/memory_capture.py`,
  policy text in `prompts.py` (`DURABLE_MEMORY_CANDIDATE_POLICY`)
- Folding: `backend/app/services/memory_candidate_ledger.py`
  (`insert_with_folding`, `NEAR_DUPLICATE_OVERLAP`)
- Gate/decay: `backend/app/services/memory_gate.py`
- Sweep: `backend/app/services/memory_sweep.py`
  (`propose_memory_sweep_review`, `validate_consolidation_ops`),
  prompt `MEMORY_SWEEP_CONSOLIDATION_SYSTEM`, agent call
  `AgentRunner.consolidate_memory_sweep`
- Budgets: `backend/app/teacher_agent/wiki/memory.py` (`MEMORY_PAGE_BUDGETS`)
- Brief UI: `frontend/src/lib/sweep-brief.ts`,
  `frontend/src/components/klassenpilot/memory-sweep-brief.tsx`
- History and evidence: `learnings.md` (post-mortem),
  `../agent_learning_guide.md` (V2 lessons + why the two-pass was retired)

Further reading: [Letta sleep-time compute](https://www.letta.com/blog/sleep-time-compute/) ·
[Hindsight on consolidation](https://hindsight.vectorize.io/blog/2026/05/21/agent-memory-consolidation) ·
[mem0 update-memory prompt](https://github.com/mem0ai/mem0/blob/main/mem0/configs/prompts.py) ·
[mem0 junk audit (97.8%)](https://github.com/mem0ai/mem0/issues/4573) ·
OpenClaw dreaming and Hermes memory docs in `ref_repos/`.
