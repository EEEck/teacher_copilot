# Memory V3 Design

Status: approved direction, implementation starting
Date: 2026-07-05
Owner decision log: beta round-2 discussion (July 2026)

## 1. Why V3 — the beta evidence

The first beta round (demo workspace `w_demo_chem9b`) exercised the full V2
loop and exposed a volume problem, not a lifecycle problem:

- One day of testing (four sessions about the same organic-chemistry lesson)
  produced **~12 open ledger candidates that encode ~4 distinct claims** —
  three wordings of "class transitioned to organic chemistry", three of "use
  molecule kits / visual supports", two of "avoid abstract orbital
  explanations".
- The teacher-triggered Memory Sweep turned those into **6+ review cards plus
  4 raw internal warnings** in one queue alone; several cards were
  unresolvable (`needs_decision`, no Add button) with `sweep_card_…` ids
  leaking into teacher-facing text.
- Earlier, the same "MBB-style communication" preference was proposed and
  approved **six times** across review batches.
- Industry echo: a mem0 maintainer audit found **97.8% of 10,134 real
  entries were junk** ([issue #4573](https://github.com/mem0ai/mem0/issues/4573)).
  Unthrottled capture is the default failure mode of agent memory.

A teacher must be able to clear the sweep in 1–2 minutes. V2's architecture
could not get there by UI alone: the backend proposes too many cards to
begin with.

## 2. What V2 got right (kept in V3)

- **The lifecycle**: observe → stage (ledger) → consolidate (sweep) → HITL
  apply → curated markdown memory. This mirrors Hermes/OpenClaw and remains
  correct.
- **Strict HITL**: teacher-triggered sweep, deterministic apply, no silent
  durable writes. V3 does not relax this anywhere — explicit teacher asks are
  *pinned first in the sweep briefing*, never fast-written.
- **The candidate ledger** (SQLite, invisible, cross-session) as the staging
  layer.
- **Typed capture contract** with shared mechanics between plan and
  update-memory runtimes (`memory_capture.py`), born from the V2 MBB capture
  bug (`../mem_v2/candidate_capture_bug.md`).
- **The eval intent**: the MBB/executive merge trace as a regression
  scenario.

## 3. What went wrong in V2 — root causes (all code-verified)

| # | Root cause | Where | Effect |
|---|---|---|---|
| 1 | Capture is blind: no view of current memory or open ledger claims; per-session re-emission; also memorizes claims from the agent's own artifact output | `memory_capture.py` | same claim captured 3–4× across sessions |
| 2 | Exact-hash clustering: `cluster_key = scope+target+section+sha256(text)`; rephrasings never merge | `memory_candidate_ledger.py:_cluster_key` | 12 rows for 4 claims |
| 3 | Free-form LLM section names are part of the cluster key AND the packet key | capture + `memory_sweep.py:build_sweep_packets` | same claim fragments across `avoid_rules` / `explanation_depth` / `structuring_lessons` |
| 4 | Packets keyed by `(queue, target, section)` → the alignment LLM never sees duplicates together; validator forbids section changes | `memory_sweep.py` | dedup-by-LLM is structurally impossible |
| 5 | Lexical token-overlap validators (≥2 shared tokens) reject correct semantic judgments; class_state transitions can satisfy neither `merge` nor `adjust` | `validate_alignment_output` | flip-flop rejections → unresolvable cards |
| 6 | Failure amplification: a failed packet emits one `needs_decision` card **per candidate** with raw internal warning text | `unresolved_cards_from_packet` | one validation failure → N zombie cards |
| 7 | No promotion gate: every captured singleton becomes a card | sweep propose | card wall |
| 8 | No dedup against applied/rejected history | ledger listing | MBB preference re-proposed 6× |
| 9 | Loose durable-preference markers ("future", "general communication") | `memory_capture.py:_DURABLE_PREFERENCE_MARKERS` | one-off "organize this in mbb style" became a global rule |
| 10 | No budgets on curated files | apply path | memory grows without compaction pressure |
| 11 | Frontend fires `memorySweepPropose` twice per queue per page open (StrictMode) | `memory-sweep/page.tsx` | 2× LLM cost per visit |

Historical note: cause 1/9 are the over-correction of the V2 capture bug —
the June fix ensured signals are never *lost*, but added no brake against
capturing too *much*.

## 4. V3 architecture — three lanes, one expensive call

Design stance (owner decision): context is cheap and consolidation runs
roughly weekly on a teacher click, so the sweep may use an expensive
high-reasoning model with large context. The hot path gets **no** additional
LLM calls.

### Lane 1 — Capture (hot path, cheap, silent by default)

- **Teacher-words-only rule** (mem0): candidates must be grounded in what
  the teacher said. The agent never memorializes its own plan/diary output —
  that content lives in the saved artifacts.
- **Sees what it knows**: the capture context includes current memory
  excerpts + open ledger claims for its targets, so it can skip known claims
  (hermes frozen-snapshot effect).
- **Silence is normal** (hermes background-review framing): most turns emit
  zero candidates.
- **`explicit_ask` tag** for genuinely future-scoped teacher statements
  ("from now on", "always", "for all lessons/briefs"). Tightened markers;
  one-off task requests never qualify.
- **Deterministic insert** (no LLM): exact normalized dup → rejected;
  content-word overlap ≥ ~0.6 with an open claim in the same target → folds
  into that claim's cluster (`signal_count`++ via shared cluster_key);
  sections normalized onto a fixed per-target vocabulary.

### Lane 2 — Ledger (invisible staging with a promotion gate)

- OpenClaw-style gate decides sweep eligibility:
  - `explicit_ask` → always eligible, surfaced in the pinned
    **"Explicitly requested changes"** section of the sweep briefing.
  - inferred → needs captures in **≥2 distinct sessions**, recency-weighted
    (OpenClaw's weights — frequency 0.24 / relevance 0.30 / recency 0.15 — as
    the tunable starting point).
  - clusters matching **applied** content → auto `already_covered`.
  - clusters matching **rejected** content → suppressed; resurfacing requires
    a fresh `explicit_ask` (teacher rejections have teeth).
- **Silent decay**: singletons never reinforced expire after ~6 weeks
  (status `expired`, unreviewed). Wiki artifacts remain the durable
  evidence, so nothing real is lost.
- Known, accepted limitation: the gate uses capture frequency, not usage
  frequency (OpenClaw's recall counts). Revisit if curated memory grows.

### Lane 3 — Sweep (teacher-triggered, one call, mem0 ID contract)

- One high-reasoning call receives: current memory files with bullets
  **enumerated with ephemeral IDs** (assigned at call time; no file format
  change), all gate-passing claims (with signal counts, dates, session
  counts), recently applied + rejected texts per target, and today's date.
- Output: per-claim operation, mem0-style —
  `ADD` / `UPDATE(id, new_text)` / `DELETE(id)` / `NONE(id|reason)` — with
  the hard rule "reference input IDs only; never invent IDs".
- **Structural validation only** (restores the 2sweep spec §7): every input
  claim accounted for exactly once; referenced IDs must exist; UPDATE must
  quote the referenced bullet; targets from the allowlist. One retry with the
  error. Lexical token-overlap semantic gates are removed.
- **Failure degrades to one notice**, not N cards: "The sweep could not
  consolidate these N suggestions — review later", raw reasons to logs only.
- `class_state` transitions are temporal supersession (Zep pattern): newest
  claim UPDATEs the current-unit bullet; no semantic-conflict machinery.
- Operations map 1:1 to the teacher brief (M1b): ADD → "what is new",
  UPDATE → "what changes (old → new)", DELETE → "removed/compacted",
  NONE → invisible.

### Apply — budgets that force compaction

- Hard character budgets on curated files (hermes ~2,200 / letta 2,000 per
  block as reference sizes): `teacher_profile.md`, `copilot_profile.md`,
  class compact memory pages.
- An over-budget apply **fails deterministically**; the failure feeds back
  into the sweep call as a compaction requirement (the model must propose
  UPDATEs/DELETEs to fit — letta's error-on-exceed mechanism).
- Teacher hand-edits to memory files remain first-class: the sweep always
  reads current file state.

## 5. What is NEW in V3 vs V2 (summary diff)

| Area | V2 | V3 |
|---|---|---|
| Capture grounding | any signal, incl. agent's own output | teacher's words only |
| Capture context | blind | sees current memory + open claims |
| Capture default | "notice durable signals" | "silence is normal" |
| Explicit vs inferred | markers loose, both → explicit/high | tightened markers → `explicit_ask`; rest inferred/low |
| Insert dedup | exact text hash, same session | exact reject + near-dup fold (cluster reuse, signal_count++) + section vocabulary |
| Promotion | everything open → cards | gate: explicit always; inferred ≥2 sessions, recency-weighted; rejected suppressed; stale expire |
| Sweep passes | two LLM passes over per-section packets | one high-reasoning call over full target context |
| Merge mechanism | alignment groups + lexical validators | ID-referenced ADD/UPDATE/DELETE/NONE (mem0 contract) |
| Validation | structural + token-overlap semantic gates | structural only |
| Failure mode | N needs_decision cards + raw warnings | one plain-language notice |
| Budgets | none | hard char budgets + compaction feedback |
| Review UI | card wall | brief: explicit-first, new/changed/removed (M1b) |

## 6. Borrowed code and patterns

| Source | License | What we take | Form |
|---|---|---|---|
| `ref_repos/hermes-agent/tools/memory_tool.py` (Nous Research) | MIT | `MemoryStore` budget enforcement, exact-duplicate rejection, entry model | adapt code into apply path |
| `ref_repos/hermes-agent/agent/background_review.py` | MIT | "If nothing is worth saving… stop" capture framing | prompt text |
| `ref_repos/openclaw/src/memory-host-sdk/dreaming.ts` | MIT | promotion gate constants (MIN_SCORE 0.8, MIN_RECALL 3) and scoring weights | port arithmetic to Python |
| mem0 `mem0/configs/prompts.py` ([repo](https://github.com/mem0ai/mem0)) | Apache-2.0 | ID-based ADD/UPDATE/DELETE/NONE update contract; "facts from user messages only" extraction rule | adapt prompt text |
| letta ([docs](https://docs.letta.com/concepts/memory-management/)) | Apache-2.0 | budget-exceed-throws → forced consolidation; 2k block sizing | pattern |
| hindsight ([repo](https://github.com/vectorize-io/hindsight)) | MIT | policy ideas: write-time consolidation, recency supersession (optional tertiary reference clone) | pattern |

No new runtime pip/npm dependencies. DeepEval (already a dev dependency)
powers the eval harness.

## 7. Assumptions (owner-confirmed)

1. Sweep is teacher-clicked, roughly weekly; no scheduled runs.
2. No memory write bypasses the sweep briefing; explicit asks are pinned
   first, not fast-written.
3. Ledger invisible; decay fully silent.
4. Hot path gains no LLM calls; insert-time dedup is deterministic.
5. Sweep uses an expensive reasoning model (sweep-specific model config);
   token efficiency is a non-goal there.
6. First scope: teacher/copilot/class-memory targets. Wiki-lint and
   student-summary queues keep V2 behavior until this settles.
7. Two-pass alignment machinery is retired; its eval intent survives as
   ledger-replay goldens (test-driven, written before the refactor).
8. M1a (save-review brief) is unchanged; M1b (sweep brief) consumes the new
   card model.
