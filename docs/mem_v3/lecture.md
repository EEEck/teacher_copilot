# Agent Memory Design — A Lecture

Status: living lecture notes, 2026-07-05
Audience: engineers and agents who want to *design* memory systems, not just
use ours. `approach.md` teaches the KlassenPilot approach; this document
teaches the field — four systems dissected from their actual code and docs
(all cloned under `ref_repos/`), the design dimensions they occupy, and how
to choose. Read time ~30 minutes.

---

## Part I — The problem, properly stated

An agent memory system decides, continuously: **what is worth keeping, in
what form, reconciled how, surfaced when, and forgotten when?** Retrieval —
the part everyone benchmarks — is the easy half. The 2026 benchmark
landscape ([LoCoMo, LongMemEval](https://mem0.ai/blog/ai-memory-benchmarks-in-2026))
grades whether a system can *find* facts in long histories; almost nothing
grades the write side — "deciding what is worth keeping out of a
conversation that is mostly noise is barely measured"
([Hindsight's benchmark manifesto](https://hindsight.vectorize.io/blog/2026/03/23/agent-memory-benchmark)).
Our beta confirmed where systems actually die: not failing to recall, but
drowning in what they kept. mem0's own maintainers audited 10,134 real
entries and found [97.8% junk](https://github.com/mem0ai/mem0/issues/4573).

Every memory system is a position on eight design dimensions. Hold these in
mind through the case studies:

| # | Dimension | The question |
|---|---|---|
| D1 | **Write trigger** | What causes a memory write attempt? (every turn / session end / explicit tool call / background job) |
| D2 | **Representation** | What is stored? (raw turns / extracted facts / consolidated beliefs / prose files / graph) |
| D3 | **Dedup point** | Where are duplicates caught? (at write, deterministically / at write, by LLM / at consolidation / at retrieval / never) |
| D4 | **Consolidation cadence & compute** | When does the expensive reconciliation run, on what model, seeing how much? |
| D5 | **Forgetting** | How does anything ever leave? (budgets / decay / supersession / eviction / never) |
| D6 | **Conflict & time** | What happens when new information contradicts old? |
| D7 | **Trust boundary** | Who approves durable writes? (nobody / the agent / the user) |
| D8 | **Injection** | What enters the prompt, when, and under what size discipline? |

One vocabulary note that recurs everywhere: the lifecycle
**observe → normalize → stage → consolidate → inject**. Systems differ
mainly in *which stage they invest in*.

---

## Part II — Case studies from the source

### Case study 1: mem0 — extraction-first vector memory

*Source: `ref_repos/mem0` (Apache-2.0), core pipeline in
`mem0/memory/main.py::_add_to_vector_store`, prompts in
`mem0/configs/prompts.py`.*

**Mechanics (the v3 pipeline, read from code).** Every `add()` call runs a
phased batch: (0) gather session scope + last 10 messages; (1) embed the
incoming messages and vector-search the **top-10 most similar existing
memories**; (2) map their UUIDs to small integer ids — the code comments
this *"anti-hallucination"* — and run **one extraction call** whose prompt
contains both the existing memories and the new messages; (3) batch-embed
and insert what comes back. Extraction rules live in
`ADDITIVE_EXTRACTION_PROMPT`: capture fact *and* surrounding context in one
self-contained statement, facts from **user messages only**, never from
assistant output.

**The v2→v3 story is the deepest lesson here.** mem0 v2 ran a *second* LLM
pass per add — the famous `DEFAULT_UPDATE_MEMORY_PROMPT` contract: compare
each extracted fact against retrieved existing memories and choose
`ADD / UPDATE(id) / DELETE(id) / NONE`, ids copied from input only. v3
**dropped the reconcile pass**: one call, add-only, contradictions coexist
and retrieval sorts them out later. Why? Cost — the reconcile pass ran on
*every* add, and adds are frequent. This is D4 discipline: reconciliation
you cannot afford at your write frequency gets cut, and quality moves to
retrieval.

**What to steal.** The ID-referencing contract (we did — it is the heart of
our sweep's structural validation); showing existing memories *inside* the
extraction call so the model self-dedups; user-words-only grounding.
**What to avoid.** Add-only with no forgetting produced the 97.8% junk
audit. Without budgets, decay, or consolidation, a memory store becomes a
write-only log wearing a memory costume.

**Dimension profile:** D1 every add · D2 extracted facts + vectors ·
D3 at write, by LLM (v3: weakly) · D4 per-add, cheap model · D5 none by
default · D6 coexist, retrieval decides · D7 nobody · D8 top-k retrieval.

### Case study 2: Hindsight — facts become observations

*Source: `ref_repos/hindsight` (MIT; engine ships as a package — mechanics
from `hindsight-docs/blog/2026-02-09-resolving-memory-conflicts.md`,
`docs/developer/observations.mdx`, and the
["Hindsight is 20/20" paper](https://arxiv.org/pdf/2512.12818).*

**The core distinction: raw facts vs consolidated knowledge.** `retain()`
stores facts; a **background consolidation job** then merges related facts
into **observations** — deduplicated, evidence-grounded beliefs, each
carrying a *proof count* and exact supporting quotes. "Alice prefers
Python" + "Alice dislikes verbose code" + "Alice recommends type hints"
becomes one observation about Alice's development values, backed by all
three.

**Mechanics.** New fact arrives → `_find_related_observations` uses the
*full recall system* (semantic similarity, a token budget
`consolidation_max_tokens` bounding the comparison scope, strict tag
matching as a security boundary) → `_consolidate_with_llm` makes **one LLM
call** seeing existing observations with proof counts and source memories
**ordered chronologically as a time series**. Three merge strategies come
back:
- **Redundant** → refine the existing observation (one cleaner sentence);
- **Direct contradiction** → *preserve both states with temporal markers*,
  writing a narrative ("progressed from prospect in January to $150K
  customer in September") — never overwrite; if no narrative explains it,
  newest wins;
- **State update** → capture the transition explicitly ("changed from X to
  Y").

Every observation keeps temporal metadata (`occurred_start`/`occurred_end`/
`mentioned_at`) and an append-only change history (previous text, reason,
source memory id) — the system can *explain how it knows things*. A final
discipline: **durable knowledge vs ephemeral state** ("Acme is in Room 105"
is memory; "user is currently in Room 105" is not) — which eliminates most
false conflicts before they exist.

**What to steal.** Write-time consolidation as "the cheapest place to
control quality"; the temporal-narrative answer to contradictions (our
class-state supersession is the one-bullet version); proof counts as
reinforcement made explicit; the audit trail. Their benchmark result —
94.6% vs 67.6% (mem0) on multi-session reasoning — is attributed to
consolidation policy, not retrieval.

**Dimension profile:** D1 retain + background job · D2 facts AND
observations (two tiers) · D3 at consolidation, by LLM · D4 background,
after every retain, token-budgeted scope · D5 supersession + history ·
D6 temporal narrative · D7 nobody · D8 recall over both tiers.

### Case study 3: OpenClaw — markdown dreaming with earned promotion

*Source: `ref_repos/openclaw` (MIT):
`docs/concepts/dreaming.md`, `src/memory-host-sdk/dreaming.ts`,
`extensions/memory-core/src/{dreaming-markdown,memory-budget,flush-plan}.ts`.*

**Everything is markdown the user can read**: `MEMORY.md` (durable,
budgeted), `memory/YYYY-MM-DD.md` daily notes, `DREAMS.md` narrative
reports. Capture is *passive and cheap* — sessions leave notes; nothing
asks for attention.

**Consolidation is staged like sleep** ("dreaming"): a **light phase**
(~6-hourly) ingests recent signals, dedupes, and *stages candidates* —
writing no durable memory; a **deep phase** (nightly) ranks candidates and
**promotes only those passing hard gates**: score ≥ 0.8 on weighted signals
(frequency 0.24, relevance 0.30, query-diversity 0.15, recency 0.15 with a
14-day half-life, consolidation 0.10, richness 0.06), **recalled ≥ 3 times
across ≥ 3 distinct queries**, snippets capped at 160 tokens; a weekly
**REM phase** writes reflections — explicitly *excluded* as a promotion
source (the system may not memorize its own dreams; compare our
teacher-words-only rule). `MEMORY.md` has a ~10KB budget whose compaction
**drops oldest auto-promoted content but never user-authored lines**.
Before context compaction, a silent *flush turn* saves anything durable to
the daily file — bootstrap files are read-only during the flush.

**The philosophy:** attention is earned. A fact must prove itself *useful
in retrieval* (recall counts — usage-based reinforcement, stronger than our
capture-count gate) before it may occupy durable space. The user never
reviews a card wall because singletons never surface.

**What to steal.** Promotion thresholds (our gate is a direct port);
staged candidates invisible until reinforced; budgets that respect
human-authored content; human-legible consolidation reports.
**Trade-off:** no HITL on writes — the thresholds *are* the trust
mechanism. Fine for a personal assistant; not for a system of record about
schoolchildren.

**Dimension profile:** D1 passive notes + cron phases · D2 markdown files ·
D3 light phase dedup · D4 nightly, thresholded, capped · D5 budgets +
recency decay + earned promotion · D6 newest-wins in compaction ·
D7 the thresholds (optional preview) · D8 MEMORY.md bootstraps every
session.

### Case study 4: Hermes — bounded stores and the discipline of scarcity

*Source: `ref_repos/hermes-agent` (MIT): `tools/memory_tool.py`,
`agent/background_review.py`, `agent/memory_manager.py`,
`website/docs/user-guide/features/memory.md`.*

**Two tiny files are the whole durable memory**: `MEMORY.md` (~2,200 chars,
agent's notes) and `USER.md` (~1,375 chars, user profile). The
`MemoryStore` keeps a **frozen snapshot** injected at session start (prefix
cache stays stable; mid-session writes go to disk and appear next session)
and a live state mutated by tool calls. Writes are guarded in code: exact
duplicates rejected ("Entry already exists"), every entry scanned for
prompt-injection and credential patterns, and — the signature move — an
over-budget add **fails with an error**: *"Memory at 2,150/2,200 chars…
Replace or remove existing entries first."* Budget pressure is converted
into consolidation work at the exact moment the agent is motivated to do
it.

**Capture is a fork, not a pipeline.** After a turn, a daemon-thread fork of
the agent replays the conversation with a memory/skill tool whitelist and
the prompt: focus on what the user revealed about themselves and how they
want you to behave; *"If nothing is worth saving, just say 'Nothing to
save.' and stop."* The fork runs with `skip_memory=True` so the review
harness cannot leak its own prompt into the user's memory namespace —
a subtle self-contamination guard (compare OpenClaw excluding dreams, and
our agent-output exclusion: every mature system ends up defending against
the agent memorizing itself).

**Scarcity does the curating.** 2,200 characters ≈ 10–15 entries. The agent
must consolidate ("replace 3 entries with 1 denser one") because it
physically cannot hoard. Deep history lives elsewhere — an unbounded SQLite
FTS5 session search answers "did we discuss X?" without touching the
budget. Two memory classes, two mechanisms.

**What to steal.** Budgets as *errors*, not silent trims; the frozen
snapshot; "silence is the normal outcome"; self-contamination guards; the
bounded-store + unbounded-search split. **Trade-off:** with the agent as
sole curator, quality is bounded by the agent's judgment each turn — no
reinforcement evidence accumulates.

**Dimension profile:** D1 per-turn background fork · D2 prose entries in
two files · D3 at write, exact-match + agent judgment · D4 continuous,
small · D5 hard budgets force replacement · D6 agent rewrites entries ·
D7 the agent (user can edit files) · D8 whole files, frozen per session.

### Briefly: two more positions worth knowing

- **Letta (MemGPT lineage)** — memory blocks with hard limits inside the
  context window; exceeding a block *throws*, prompting the agent to
  consolidate; **sleep-time agents** run consolidation asynchronously
  between conversations ([blog](https://www.letta.com/blog/sleep-time-compute/),
  [paper](https://arxiv.org/html/2504.13171v1)). Our teacher-triggered
  sweep is sleep-time compute with a human at the wake boundary.
- **Zep / Graphiti** — a temporal knowledge graph where facts carry
  validity intervals; contradiction closes the old interval and opens a new
  one. The graph-shaped generalization of Hindsight's temporal narrative
  and our class-state supersession.
- **TiMem** ([paper](https://arxiv.org/pdf/2601.02845)) — temporal-
  hierarchical consolidation for long-horizon conversational agents; the
  academic frontier is converging on the same shape: hierarchy + time +
  consolidation as first-class.

---

## Part III — Synthesis: what the field agrees on

Reading four codebases side by side, the convergences are striking —
independent teams keep landing on the same five moves:

1. **One LLM call comparing new against retrieved-existing, with stable
   small ids.** mem0's integer mapping, Hindsight's observation ids, our
   ephemeral bullet ids — everyone learned that models hallucinate
   references unless you enumerate the referents, and that dedup requires
   the duplicates to be *in the same context window*.
2. **Consolidation moves off the hot path.** Hindsight's background job,
   OpenClaw's nightly deep phase, Letta's sleep-time agents, our
   teacher-clicked sweep. Per-turn writes stay cheap and dumb; intelligence
   runs rarely with full context. (mem0 v3 is the counterexample that
   proves the rule: they couldn't afford reconciliation per-add, so they
   cut it — and pushed the problem to retrieval.)
3. **Budgets are the only forgetting that reliably ships.** Decay and
   relevance scoring are tunable and fragile; a hard character/token limit
   with a defined eviction rule (hermes: error; openclaw: drop oldest
   auto-promoted; letta: throw) is what actually keeps stores small.
4. **Time beats truth-maintenance.** Nobody runs belief revision.
   Contradictions are handled temporally: validity intervals (Zep),
   transition narratives (Hindsight), newest-wins supersession (ours).
   State changes are the *normal case*, not conflicts.
5. **Every mature system guards against self-contamination.** The agent
   must not memorize its own output: OpenClaw excludes dream reports from
   promotion, Hermes isolates its review fork, mem0 extracts from user
   messages only, we forbid capture from artifacts. This rule appears
   independently everywhere because the failure loop (plan from memory →
   memorize the plan → reinforce the memory) is universal.

And one real divergence, which is a *values* choice, not an engineering
one: **who approves writes** (D7). The spectrum runs from nobody (mem0,
Hindsight) through algorithmic thresholds (OpenClaw) and agent-as-curator
(Hermes) to user-approves-everything (us). Your position on D7 determines
what the scarce resource is — compute, storage, or human attention — and
that in turn determines where to spend your engineering.

## Part IV — KlassenPilot V3 as a worked example

Our constraint: a system of record about real classrooms, so **D7 =
teacher approves every durable write**. That makes *review attention* the
scarce resource, and the whole design follows: gate harder than OpenClaw
(their thresholds protect storage; ours protect a human's minutes),
consolidate in one strong-model call (D4: weekly cadence makes tokens
cheap — the mini model demonstrably fails the add-vs-adjust judgment),
dedup deterministically at write (D3: calibrated overlap-coefficient
folding on recorded beta data), forget silently below the gate (D5:
unreinforced singletons expire; the wiki artifacts remain the ground
truth), and handle time by supersession (D6: class state is temporal).
The V2 failure maps cleanly onto the dimensions: duplicates fragmented
across contexts (violated convergence #1), lexical validators second-
guessing semantics (a D3/D6 confusion), failure amplification (a D7 tax —
every zombie card spent teacher attention). Full evidence: `learnings.md`.

## Part V — Design exercises

Test yourself (or the next agent) against the material:

1. Your agent's memory store doubled in a month and retrieval quality is
   dropping. Which dimension failed, and which two mechanisms from Part II
   would you add first?
2. mem0 v3 removed write-time reconciliation; Hindsight doubled down on it.
   Both are defensible. State the workload parameter that decides who is
   right for a given system.
3. A user tells your agent "actually, format everything as tables from now
   on." A week later they say "stop using tables." Show how Hindsight,
   Zep, and KlassenPilot each represent the end state.
4. Your consolidation LLM keeps "updating" bullets that are merely in the
   same topic area as a new claim. You may not add lexical similarity
   gates. Name three remedies from this lecture and their costs.
   *(We hit exactly this — see `learnings.md` §4 and §6.)*
5. Design the memory system for a hospital shift-handover agent. Walk the
   eight dimensions and justify each position. Which of the four case
   studies is your closest starting point, and why is it probably not
   mem0?

## Reading list

- Code: `ref_repos/mem0`, `ref_repos/hindsight`, `ref_repos/openclaw`,
  `ref_repos/hermes-agent` (all permissively licensed)
- Ours: `approach.md` (the taught approach), `design.md`, `learnings.md`
- Papers: [Hindsight is 20/20](https://arxiv.org/pdf/2512.12818) ·
  [Sleep-time Compute](https://arxiv.org/html/2504.13171v1) ·
  [TiMem](https://arxiv.org/pdf/2601.02845)
- Field surveys & benchmarks:
  [AI memory benchmarks 2026](https://mem0.ai/blog/ai-memory-benchmarks-in-2026) ·
  [Hindsight benchmark manifesto](https://hindsight.vectorize.io/blog/2026/03/23/agent-memory-benchmark) ·
  [memory frameworks compared](https://vectorize.io/articles/best-ai-agent-memory-systems)
- Deep dives: [Hindsight on memory conflicts](https://hindsight.vectorize.io/blog/2026/02/09/resolving-memory-conflicts) ·
  [Letta sleep-time compute](https://www.letta.com/blog/sleep-time-compute/) ·
  [mem0 junk audit](https://github.com/mem0ai/mem0/issues/4573)
