# Memory V3 — Key Learnings

Status: post-implementation write-up, 2026-07-05
Scope: what the first beta round taught us about agent memory, what V3
changed because of it, and which lessons generalize beyond memory.

## The headline

One day of beta testing produced **~12 candidate rows encoding ~4 distinct
claims**, which the V2 sweep turned into **6+ review cards plus 4 raw
warnings**, several unresolvable. After V3, the same recorded ledger yields
**3 clean cards with zero warnings**, and the MBB/executive merge trace
passes end to end (`full_merge_cards=1`, correct `add`). The teacher-facing
metric is review time: a card wall a teacher rubber-stamps is worse than a
brief a teacher actually reads.

## Learning 1 — Over-capture is the default failure mode of agent memory

The V2 capture bug ("MBB preference understood but never persisted") was
fixed by making capture aggressive: per-turn emission plus typed-state
repair. That fix had a gas pedal and no brake — every session re-captured
the same claims with new wording, and the agent memorialized content *it had
generated itself* (its own plan text became "class learning patterns").
Industry echo: a mem0 maintainer audit found 97.8% of 10,134 real entries
were junk.

V3 brakes, in order of leverage:
- **Teacher-words-only grounding** (mem0's rule): candidates come from what
  the teacher said, never from the agent's own artifact output. Self-sourced
  memories compound — the agent plans from memory, memorizes its plan, and
  the loop reinforces itself.
- **Silence is the normal outcome** (hermes framing): most turns save
  nothing, and the prompt says so explicitly.
- **Explicit status must be earned**: `teacher_explicit/high` requires
  clearly future-scoped wording ("from now on", "for all briefs"); the
  backend downgrades anything else to a weak inferred signal
  (`discipline_memory_candidates`). A one-off "organize this in mbb style"
  is a formatting request, not a durable preference.

## Learning 2 — Deduplicate at write time, deterministically

Hindsight's phrase held up: write time is the cheapest place to control
memory quality. `insert_with_folding` needs no LLM:
- sections normalize onto a fixed per-target vocabulary (free-form LLM
  section names had fragmented one claim across three cluster keys);
- same-session exact duplicates are noise (`duplicate`);
- **cross-session exact or near duplicates fold into the matched cluster as
  reinforcement** — an identical re-statement in a new session is the
  strongest signal there is (we almost discarded these; catching that was a
  test-migration find);
- re-captures of applied content become `already_covered`; re-captures of
  rejected content are `suppressed` unless the teacher explicitly asks again
  — **rejections must have teeth**, or the teacher re-reviews the same
  suggestion forever (the beta MBB preference was approved six times).

Calibration matters and needs real data: raw Jaccard on content words could
not separate rephrasings (0.13–0.57) from distinct claims. Stemmed tokens +
the **overlap coefficient** (robust to length differences) separated them
cleanly (same claim 0.56–1.00, different claims 0.10–0.25; threshold 0.55).
The recorded beta ledger is the calibration fixture, checked into
`tests/fixtures/mem_v3/`.

## Learning 3 — A dedup LLM can only merge what it sees together

V2's alignment pass was correctly designed and structurally unable to work:
packets were partitioned by the same free-form `section` field the capture
LLM invented, so the four rephrasings of one claim went into four isolated
LLM calls. No prompt fixes that. The unit of consolidation must be the unit
of duplication (the target file), and partitioning keys must never come from
unnormalized model output.

## Learning 4 — Validate structure deterministically; never second-guess semantics lexically

V2's validators enforced ≥2-token overlap between a group's labels and an
existing bullet before accepting `adjust`/`already_covered`, and rejected
`merge` when overlap existed. Class-state transitions ("from redox to
organic chemistry") made both decisions rejectable — live traces show the
model flip-flopping between two answers that were each refused. This was the
exact anti-pattern the learning guide warned about, rebuilt as a hard gate.

V3's split: **structural checks are deterministic and strict** (every claim
accounted for exactly once, referenced memory ids must exist in the
enumerated index, updates quote their bullet verbatim, no-change updates are
demoted to `none` mechanically); **semantic judgment belongs to the model**,
with teacher review as the safety net. The mem0 ID-referencing contract is
what makes this possible: enumerate current bullets with ephemeral ids at
call time, and "reference input ids only" turns semantic validation into
mechanical validation.

## Learning 5 — Price the actual call frequency before designing for tokens

Packets, per-section chunking, and the two-pass split all existed for token
control — for a consolidation that runs roughly weekly on a teacher click.
Once the owner priced that honestly ("context is cheap, writes are rare, use
the expensive model"), most of the architecture dissolved: one call sees all
gate-passing claims, all in-scope memory files, applied/rejected history,
budget usage, and today's date. Complexity that exists to save tokens should
cite the call frequency it is saving them at.

## Learning 6 — Model strength is part of the contract

Both V2 sweep passes had quietly been running on the fast model. Control
tests on the live MBB trace: **gpt-5.4-mini repurposes an unrelated bullet
("planning language: English") as the thing to "update" with a style
preference — even after prompt tightening; gpt-5.4 passes cleanly** and even
flags in-batch duplicates unprompted. Consolidation quality is bounded by
the model, not just the prompt. `OPENAI_SWEEP_MODEL` is now explicit config
with the rationale documented in the README.

## Learning 7 — Failures must collapse, not multiply

V2 turned one over-constrained validation failure into N per-candidate
`needs_decision` cards with raw internal ids in teacher-facing text. V3
degrades a failed run to one plain-language notice ("the sweep could not
consolidate N suggestions — nothing was lost"), raw reasons to logs. The
teacher-visible cost of a backend failure should be constant, not
proportional to the batch size.

## Learning 8 — Offline tests pin contracts; only live runs pin behavior

The offline suite (fixtures from the recorded beta ledger, goldens written
before implementation) caught contract regressions throughout. Two defects
appeared **only against the real model**: unrelated-bullet repurposing and
no-change student-summary updates. Each produced both a deterministic guard
(the no-op demotion) and a prompt rule (same-section ≠ same-claim). The
loop that works: recorded real data as offline fixtures → contract goldens
→ live traces as the behavior bar → telemetry (`memory_sweep_propose`
card/warning counts) as the production metric.

## Learning 9 — Reinforcement needs visible gates, invisible staging

OpenClaw's promotion thresholds translated well: explicit teacher asks are
always sweep-eligible (pinned first in the brief), inferred claims need two
distinct sessions, stale singletons expire silently after ~6 weeks. The
ledger stays invisible; HITL applies to *writes*, not to *staging*. Known
accepted limitation: we gate on capture frequency, not usage frequency
(OpenClaw's recall counts) — revisit if curated memory grows.

## What carried over from V2 unchanged

- The lifecycle: observe → stage → consolidate → HITL apply → curated
  markdown memory.
- Deterministic apply with exact-replacement semantics.
- Hermes-style page budgets (`MEMORY_PAGE_BUDGETS` predated V3; V3 only fed
  the pressure into the consolidation call).
- The MBB/executive scenario as a regression trace rather than a prompt
  example — and "teach the contract, not the benchmark" for prompt examples.

## The one-line summary

> Deterministic code owns structure, budgets, and history. The model owns
> meaning — given one context that actually contains everything it must
> reconcile, and enough model to reconcile it. The teacher owns the writes.
