# Memory V4 Brainstorm — Stop Over-Sensitive Fast-Lane Writes

Status: **brainstorm for owner decision** (2026-07-16)  
Audience: product/owner + implementer  
Does **not** change the behavior contract until an implementation plan is approved.

---

## TL;DR (decision summary)

**Problem.** Memory V3 fixed the right lifecycle (stage → gate → sweep → teacher approve) but left a hole at the front door: one short teacher message can produce many `remember(...)` candidates that all get stamped `fast_lane=True` and flood Memory Sweep. Quote formatting alone does not fix this — the backend checks that the quote appears in the message, not that the *claim* matches the quote.

**Primary empirical input (2026-07-16 sandbox):** see [`empirical_inputs.md`](empirical_inputs.md) — 16 ledger rows (13 fast-lane), 14 Sweep cards (8 “explicit” prefs + 6 student summaries), vs a handful of short ochem mock chats. Smoking gun: plan session `40510c49…` staged **7** candidates from one pchem + “always 5 min review” message, several with contents **not in that message**, all sharing the whole message as quote passport.

**Do not** import Mem0 / OpenClaw / Hermes as a second memory product. KlassenPilot’s wiki + ledger + HITL sweep is the right shape.

**Do** steal a few small, proven admission rules from those repos and enforce them in our code:

1. Claim must match the quote (grounding).
2. Fast lane requires a real `speech_act` — not only the word “always” in the message.
3. Cap how many fast-lane notes one message may create.
4. Before creating a new note, check “already known / only rephrased?” and skip.
5. Keep “most turns remember nothing” as the default.

**Outcome to aim for.** A short standing-instruction message → 1–3 review cards that a teacher recognizes as things they said — not 10+ VIP cards that invent extra preferences. Goldens G1–G5 are listed in `empirical_inputs.md` §7.

---

## 0. Empirical inputs (this worktree)

Full write-up: **[`empirical_inputs.md`](empirical_inputs.md)**  
Raw dumps: [`_ledger_snapshot.json`](_ledger_snapshot.json), [`_sweep_cards.json`](_sweep_cards.json)

| Input | What it showed |
|---|---|
| Teacher mock prompts (Plan/Result L1+L2 + short plan chat) | Only a few true standing prefs; lots of wiki/student material |
| Ledger (16 rows, 13 FL) | Atomization + whole-message quote reuse on session `40510c49` |
| Sweep (8 explicit prefs + 6 students) | UI “explicit” = fast-lane stamp; students are a separate summary queue |
| Current `DURABLE_MEMORY_CANDIDATE_POLICY` + `remember` docstring | Already teach silence/SAVE/SKIP — still violated; no entailment/cap |

Section 1.4 below is a short recap; treat `empirical_inputs.md` as the authoritative evidence pack for owner decisions and test goldens.

---

## 1. Background — how we got here

### 1.1 Product model (unchanged and still correct)

KlassenPilot keeps durable teaching memory in curated markdown wiki pages. Chat never writes those pages silently. The intended life of a preference is:

```
teacher words
  → remember(...) stages a review-only candidate
  → SQLite ledger (invisible staging)
  → promotion gate
  → Memory Sweep (teacher review)
  → /memory/apply writes curated markdown
```

This is documented in `docs/mem_v3/approach.md` and `docs/agent_contracts.md`. V4 should **tighten admission into the ledger**, not replace the lifecycle.

### 1.2 What V2 proved (and broke)

V2 proved the lifecycle but produced a card wall. `docs/mem_v3/design.md` records beta evidence: one day of testing produced ~12 open ledger candidates that encoded ~4 distinct claims; the same preference was proposed and approved six times. Industry echo cited there: a Mem0 maintainer audit found **97.8% of 10,135 real entries were junk** ([mem0#4573](https://github.com/mem0ai/mem0/issues/4573)).

Root causes listed in V3 design included blind capture, exact-hash clustering, no promotion gate, and loose durable-preference markers.

### 1.3 What V3 shipped (and what it left open)

V3 added:

| Brake | Where |
|---|---|
| Teacher-words-only capture + `remember(...)` tool | `tools.py`, `memory_capture.py` |
| Backend-owned fast lane (speech_act + target + quote) | `discipline_memory_candidates` |
| Insert-time near-dup folding | `memory_candidate_ledger.insert_with_folding` |
| Promotion gate (explicit OR ≥2 occasions) | `memory_gate.py` |
| Single-call sweep + char budgets | `memory_sweep.py`, apply path |

`docs/mem_v3/learnings.md` Learning 8 is important for V4: a live capture eval found the model’s *judgment* of speech acts was sound, but **emission** was the bottleneck (under-capture). PR4 made capture an explicit tool so durable asks would not be forgotten.

That fix worked for emission — and created the current over-emission failure mode. V3’s own axiom was already: **“Silence is the normal outcome. Most chat turns produce zero memory candidates.”** (`docs/mem_v3/approach.md`). The prompts still say this (`DURABLE_MEMORY_CANDIDATE_POLICY` in `prompts.py`), but the backend does not enforce a per-turn creation budget or claim↔quote grounding.

### 1.4 Observed V4 symptom (sandbox / ochem chats)

Detailed tables, quote text, Sweep card list, and prompt excerpts: [`empirical_inputs.md`](empirical_inputs.md).

After a few plan / discuss / ingest turns about organic chemistry, the sandbox showed:

- **16** ledger rows, **13** with `fast_lane=1` / `teacher_explicit`
- Plan session `40510c49…`: **7** staged from one short message; several contents (visual/spatial, hybridization, demo, pair work) **not entailed** by that message; evidence used the **whole message** as `Direct teacher quote` plus typed-state “Teacher explicitly framed this as a durable preference”
- Open Sweep: **8** Teacher/Copilot cards all `basis=explicit`, plus **6** Student Memory summary cards (`basis=inferred`) — the latter are a separate wiki-rollup path, not the preference bug
- Fair standing rules *were* present (orbitals, phenomenon-first, 5‑min review) — buried in junk VIP volume

**Plain-language diagnosis:** we are letting too many notes into the waiting room, and stamping too many of them VIP (fast lane). Sweep then correctly shows VIP cards first — so the teacher sees a flood.

---

## 2. Code-verified root cause (KlassenPilot)

This section is grounded in the current worktree code under `backend/app/`.

### 2.1 The capture tool accepts any content if the quote exists

`remember(...)` is defined in `backend/app/teacher_agent/tools.py` (`create_remember_tool`). It calls `validate_remember_call(...)`.

`validate_remember_call` in `backend/app/teacher_agent/memory_capture.py` checks:

1. `content` non-empty  
2. `target` is an allowed fast-lane-capable target  
3. `quote` ≥ 10 characters  
4. `quote` appears **verbatim** (case-insensitive) inside the latest teacher message  

It then builds a candidate with:

- `source="teacher_explicit"`
- `basis="explicit"`
- `confidence="high"`
- `evidence="Direct teacher quote: …"`

**It does not check that `content` is supported by, entailed by, or even related to `quote`.**

Relevant code comment (intent):

> The three checks all ground in ground truth (a supported preference target; the teacher actually said the quote), never in a guess about intent — persist-time `discipline_memory_candidates` still makes the authoritative fast-lane decision.

So quote provenance answers “did the teacher say *these words*?” — not “is *this claim* what those words meant?”

### 2.2 Persist-time discipline can open the fast lane via message markers

`discipline_memory_candidates(...)` is the authoritative fast-lane stamp. For profile targets (`teacher_profile.md`, `copilot_profile.md`), `act_ok` is true when:

```text
speech_act in ("conduct_request", "store_request")
  OR  the whole teacher message contains a durable-scope marker
```

Markers include (among others): `"from now on"`, `"always"`, `"going forward"`, `"for all lesson"`, …

Comment in code says markers are fallback for legacy/empty speech_act — but the `or marker_scoped` branch currently applies even when speech_act is wrong/empty for profile targets.

Also: when the model quotes nothing verifiable but also does not fabricate, `_verified_quote` returns `""`, and the keeper path stamps the **entire teacher message** as the verified quote:

```text
verified = quote or clean_text(teacher_message)
```

So one message containing “always …” can authorize multiple profile candidates as fast lane, each with different `content`.

### 2.3 Folding only merges near-duplicate *content*, not shared quotes

`insert_with_folding` in `memory_candidate_ledger.py` folds when content tokens overlap ≥ `NEAR_DUPLICATE_OVERLAP` (0.55), or exact match / applied / rejected history.

Unrelated claims that share one quote **do not fold**. Each distinct `candidate_update` becomes its own cluster. Then `memory_gate.py` marks any cluster containing a fast-lane row as immediately Sweep-eligible:

```text
explicit OR distinct_occasions >= 2  → eligible
```

So false-positive fast-lane rows skip the “wait for two occasions” brake that protects inferred claims.

### 2.4 Prompt policy already asks for silence — but cannot enforce it

`DURABLE_MEMORY_CANDIDATE_POLICY` in `prompts.py` already says:

> Most turns produce NO memory candidates. Silence is the normal outcome…

and lists SAVE vs SKIP rules, speech_act definitions, and verbatim quote requirements.

The ochem symptom shows: **prompt + quote field ≠ admission control.** The model can still call `remember` many times; the backend accepts them.

### 2.5 Passive / typed-state repair paths still exist

`durable_preference_candidates_from_state_values` and `teacher_preference_candidate` can still mint `teacher_explicit` candidates from typed state when the message has durable-scope markers. V4 should treat these as second-class and subject to the same grounding/budget rules (or retire them once `remember` is trusted).

### 2.6 What is *not* the core bug

- Memory Sweep UI showing student-summary proposals for dated observations (by design for wiki rollups).
- Lesson facts landing in `lesson_results` / misconceptions / open loops via ingest commit.
- The two-occasion gate for truly inferred rows (that part works when fast_lane is false).

The core bug is **fast-lane false promotion of atomized / ungounded claims**.

---

## 3. Industry findings (2026) — plain language + sources

Across write-policy engineering and recent papers, the industry agrees on one slogan:

> **Every write is a tax on every future read.** Prefer missing a memory once over saving ten weak ones.

Key public sources reviewed for this brainstorm:

| Source | Useful idea for us |
|---|---|
| [Memory Write Policies (Jatin Bansal, 2026)](https://jatinbansal.com/ai-engineering/memory-write-policies/) | Four-stage write pipeline: triage → extract → dedupe → persist. Over-extraction is the default failure mode. Prefer false negatives at the write gate; backfill from a journal later. |
| [SAGE: A Novelty Gate… (arXiv 2605.30711)](https://arxiv.org/abs/2605.30711) | Score candidates for novelty; ADD / NOOP / uncertain→merge. Confirms write-side control is a first-class lever. **Too heavy for our hot path** if it requires extra embeddings/LLM every turn. |
| [GovMem — When Not to Write Memory (arXiv 2607.02579)](https://arxiv.org/html/2607.02579v1) | Repeated correlated traces are not independent votes; promote / reject / needs-review with dependency-aware support. Matches our “occasions” idea; warns against auto-promotion from same-session spam. |
| [Selective Memory… Write-Time Gating (arXiv 2603.15994)](https://arxiv.org/html/2603.15994v1) | Low-salience items go to archive, not active store; start conservative on the threshold. |
| Mem0 docs / blog | ADD / UPDATE / DELETE / NOOP decision shape; confidence + custom “what not to remember” instructions. OSS v3 has shifted toward ADD-only + later consolidation — still useful as a *decision vocabulary*, not as a product to adopt. |
| Hindsight blog on consolidation | Fact extraction as importance filter; entity resolution at write time; observations as beliefs with evidence. |

**Translation for KlassenPilot:** we already have journal (ledger) vs checkpoint (wiki). V4 is about making the **front-door triage** as strict as the industry’s Stage 1–3, without adding Mem0 as a dependency.

---

## 4. Deep study of `ref_repos` — what to steal, with exact quotes

Repos studied under `C:\Users\matth\teacher_agent_v2\ref_repos\`:

`assistant-ui`, `AutoSci`, `hermes-agent`, `hindsight`, `mem0`, `openclaw`, `Shiksha-Copilot`.

### 4.1 Mem0 + OpenClaw memory-triage skill (highest value policy text)

**File:** `ref_repos/mem0/integrations/openclaw/skills/memory-triage/SKILL.md`

Core question (exact):

> **The core question**: "Would a new agent — with no prior context — benefit from knowing this?" If no → do nothing. Most turns produce zero memory operations. That is correct and expected.

Four conjunctive gates (exact headings):

> Every candidate fact must pass ALL four gates:  
> **Gate 1 — FUTURE UTILITY** …  
> **Gate 2 — NOVELTY** …  
> **Gate 3 — FACTUAL** …  
> **Gate 4 — SAFE** …  
> All four gates must pass. If any fails → do nothing.

Material difference / NOOP (exact):

> **Material difference test**: Only UPDATE if new information adds real context, details, or changes meaning. Cosmetic differences (synonyms, rephrasing, punctuation) are NOT updates. "Loves daily walks" vs "enjoys daily walks" = no material change = SKIP.

Entity consolidation (exact):

> **Only create separate memories when information refers to genuinely different entities, concepts, or unrelated topics**

Batching (exact):

> **BATCH BY CATEGORY**: Group all same-category facts into one call. Different categories require separate calls. Most turns need zero or one call.

Never-store list (excerpt, exact bullets):

> - **One-time commands** — "stop the script", "continue where you left off", "run this"  
> - **Acknowledgments and emotional reactions** — "ok", "sure", "sounds good"…  
> - **Facts already in recalled memories that haven't materially changed**

**Take for V4:** port this as KlassenPilot’s admission checklist (teacher-adapted). Do **not** adopt Mem0 storage.

### 4.2 Mem0 OSS extractor prompt — what *not* to copy

**File:** `ref_repos/mem0/mem0/configs/prompts.py` (additive / v3-style extraction)

Exact anti-pattern for us:

> **When in doubt, extract.** A slightly redundant memory is far less costly than a missing one. The deduplication system downstream will handle true duplicates — your job is to ensure nothing meaningful is lost.

Also encourages extracting incidental facts and multiple dimensions per session. That philosophy matches V2’s over-capture and fights V3/V4’s silence default.

Legacy ADD/UPDATE/DELETE/NONE update prompt in the same file remains a useful **vocabulary** for Sweep (already borrowed in V3), not for hot-path capture.

### 4.3 Hermes agent memory tool — budgets + skip list

**File:** `ref_repos/hermes-agent/tools/memory_tool.py`

Design (module docstring, exact ideas):

- Two stores: `MEMORY.md` (agent notes) and `USER.md` (user prefs)
- Frozen snapshot injected at session start; mid-session writes do not rewrite the prompt mid-turn
- Character limits (defaults in code): `memory_char_limit: int = 2200`, `user_char_limit: int = 1375`
- Exact duplicate add → no-op success

Tool schema SKIP guidance (exact):

> Do NOT save task progress, session outcomes, completed-work logs, or temporary TODO state to memory…  
> SKIP: trivial/obvious info, things easily re-discovered, raw data dumps, and temporary task state.

Also (exact, more permissive than we want):

> WHEN TO SAVE (do this proactively, don't wait to be asked)

**Take for V4:** keep Hermes budgets (already in V3 apply path); steal SKIP wording; **do not** copy “save proactively” as the default for `remember`.

Docs note exact-dup rejection: `ref_repos/hermes-agent/website/docs/user-guide/features/memory.md`:

> The memory system automatically rejects exact duplicate entries. If you try to add content that already exists, it returns success with a "no duplicate added" message.

### 4.4 Hindsight — raw facts vs observations (journal vs belief)

**File:** `ref_repos/hindsight/skills/hindsight-docs/references/developer/observations.md`

Exact:

> After memories are retained, Hindsight automatically consolidates related facts into **observations** — deduplicated, evidence-grounded beliefs the bank has built up from multiple memories. Each observation tracks its supporting evidence (with exact quotes) and a proof count, and is refined rather than overwritten when new evidence arrives.

Near-dup reconciliation (exact):

> This is controlled by the `HINDSIGHT_API_CONSOLIDATION_DEDUP_THRESHOLD` setting: the cosine similarity at or above which two observations are reconciled. It is **enabled by default** (`0.97`)…

**Take for V4:** keep our ledger (raw staged claims) separate from curated wiki (beliefs). Fast lane should not invent beliefs. Reinforcing an open cluster (fold) is closer to “proof count++” than creating a new VIP card. Avoid auto-retain-every-turn patterns used in some Hermes↔Hindsight integrations.

### 4.5 OpenClaw core — session memory vs curated memory

OpenClaw’s bundled session-memory hooks (`ref_repos/openclaw/src/hooks/bundled/session-memory/`) mostly save transcript slices on `/new` or `/reset` — **journaling**, not preference extraction. Memory flush is gated by context pressure.

`docs/mem_v3/design.md` already borrowed promotion scoring inspiration from `ref_repos/openclaw/src/memory-host-sdk/dreaming.ts` (frequency/recency weights). Our `memory_gate.py` header cites this.

**Take for V4:** keep “earn attention before bothering the teacher.” Do not adopt transcript-dump-as-memory for curated profiles.

### 4.6 AutoSci — proposal / checkpoint discipline

AutoSci is research-wiki oriented, not conversational memory. The transferable product pattern (already in KlassenPilot) is: **candidates for human selection before durable graph/wiki mutation**. V4 strengthens the candidate filter; it does not need AutoSci’s graph engine.

### 4.7 Steal vs import decision matrix

| Option | Verdict | Why |
|---|---|---|
| Import Mem0 as runtime memory layer | **No** | Second brain vs wiki; wrong domain (generic user facts); OSS extract bias is permissive |
| Import OpenClaw memory host | **No** | Different product; session transcripts ≠ class memory |
| Import Hermes MemoryStore as primary | **No** | We already adapted budgets; Hermes writes durable files more directly than our HITL model |
| Import Hindsight bank | **No** | Heavy; auto-retain amplifies over-capture unless heavily constrained |
| Copy triage policy text + NOOP/material-diff + budgets + silence default | **Yes** | Small, license-friendly (MIT/Apache patterns already cited in mem_v3), fits our ledger |
| Add SAGE novelty embeddings on hot path | **Not yet** | Cost/complexity; Sweep already does expensive consolidation |

### 4.8 Exact functions and logic in the other codebases

This subsection is the implementation-level map: **which functions run, what they check, what is only prompt text**. Paths are under `C:\Users\matth\teacher_agent_v2\ref_repos\` unless noted.

---

#### A. Mem0 OSS — current write path (ADD-only)

**Primary file:** `mem0/mem0/memory/main.py`

| Symbol | Approx. lines | Role |
|---|---|---|
| `Memory.add` | ~717–829 | Public entry; normalizes messages; calls `_add_to_vector_store` |
| `Memory._add_to_vector_store` | ~831–1158 | All write admission for inferred and raw adds |
| `Memory._create_memory` | ~1886–1916 | Persist one memory + MD5 hash + history `ADD` |
| `Memory.update` / `_update_memory` | ~1767–1806 / ~1957–2021 | Explicit API only — **not** called by inferred add |
| `Memory.delete` / `_delete_memory` | ~1808–1827 / ~2023–2051 | Explicit API only |

**Prompt symbols** in `mem0/mem0/configs/prompts.py`:

| Symbol | Role today |
|---|---|
| `ADDITIVE_EXTRACTION_PROMPT` | **Active** system prompt for `infer=True` |
| `generate_additive_extraction_prompt(...)` | Builds user prompt with existing memories + new messages |
| `DEFAULT_UPDATE_MEMORY_PROMPT` | **Legacy** ADD/UPDATE/DELETE/NONE text — not wired into current `Memory.add` |
| `get_update_memory_messages(...)` | **Legacy** formatter for four-op decisions — no active call site in `main.py` |

**Logic of `_add_to_vector_store` (decisive branches):**

```text
if infer == False:
    for each message:
        skip invalid / role==system
        _create_memory(raw content)   # no extract, no semantic dedup
        return event ADD for each
else:  # infer == True
    existing = vector_store.search(query=parsed_messages, top_k=10, filters=scope)
    extracted = LLM(ADDITIVE_EXTRACTION_PROMPT + generate_additive_extraction_prompt(...))
    if empty / unparseable:
        save session messages; return []          # soft NOOP (no memory rows)
    for each extracted text:
        h = md5(text)
        if h in existing_hashes or h in batch_seen: skip   # exact-text only
        else queue _create_memory
    if nothing left: save messages; return []
```

**Code-enforced vs prompt-only:**

| Check | Enforced in Python? |
|---|---|
| Empty extraction → no write | Yes (`return []`) |
| Exact MD5 duplicate vs top-10 + batch | Yes |
| “Semantically equivalent → skip” | **Prompt only** (inside additive prompt) |
| ADD / UPDATE / DELETE / NOOP tool choice | **Not in current add path** (legacy prompt only) |
| “When in doubt, extract” | Prompt bias (permissive) |

**Decisive dedup snippet** (`main.py` ~957–975):

```python
mem_hash = hashlib.md5(text.encode()).hexdigest()
if mem_hash in existing_hashes or mem_hash in seen_hashes:
    logger.debug(f"Skipping duplicate memory (hash match): {text[:50]}")
    continue
```

**V4 lesson:** Mem0’s *code* gate is weak (exact hash + empty list). Semantic NOOP lives in the prompt. Our V4 grounding/budget must be **code**, not only prompt — same lesson Mem0’s junk-audit implies.

---

#### B. Mem0 OpenClaw plugin — triage skill vs executable tools

**Prompt-only policy (four gates):**  
`mem0/integrations/openclaw/skills/memory-triage/SKILL.md`  
Gates: FUTURE UTILITY → NOVELTY (material difference) → FACTUAL → SAFE.  
This file is **not executed**; the model is supposed to follow it before calling tools.

**Executable TypeScript (narrower):**

| File | Symbol | What it actually enforces |
|---|---|---|
| `integrations/openclaw/tools/memory-add.ts` | `createMemoryAddTool()` (~26–103) | Reject empty facts; strip noise fragments; block subagent sessions; in skills mode set `infer: false` and store facts as user messages |
| `integrations/openclaw/filtering.ts` | `filterMessagesForExtraction()` (~196–212) | Drop known noise / short generic assistant lines / truncate — **not** novelty/factuality |
| `integrations/openclaw/providers.ts` | provider `add` rewrite (~414–425) | When `infer=false` + `deduced_memories`, rewrite messages to fact strings so OSS stores the right text |
| `integrations/openclaw/tools/memory-update.ts` | `createMemoryUpdateTool()` | Requires memory id; blocks subagents — **no** material-difference check |
| `integrations/openclaw/tools/memory-delete.ts` | `createMemoryDeleteTool()` | Bulk needs `confirm:true`; query-delete auto-applies only if 1 hit or top score > `0.9` |
| `integrations/openclaw/index.ts` | legacy auto-capture (~1010–1054) | Needs ≥1 user message and ≥50 user chars; then `provider.add()` with default `infer=True` |
| `integrations/mem0-plugin/scripts/auto_capture.py` | `extract_recent_exchanges`, `store_exchange` | Skip <20 chars / tool-looking JSON; POST with `"infer": True` — decisions deferred to platform |
| `integrations/openclaw/dream-gate.ts` / pi `dream/index.ts` | `checkCheapGates`, `checkMemoryGate`, `acquireDreamLock` | Schedule/session/count/lock gates before consolidation — **not** per-fact semantic admission |

**V4 lesson:** The valuable “four gates” are **policy text**. Executable code only does shape/noise/session safety. KlassenPilot should encode the valuable gates in Python the way Hermes encodes char limits — not hope the model follows SKILL.md alone.

---

#### C. Hermes — `MemoryStore` write admission (code-hard)

**File:** `hermes-agent/tools/memory_tool.py`

| Symbol | Lines (approx.) | Logic |
|---|---|---|
| `_scan_memory_content` | 78–80 | `first_threat_message(content, scope="strict")` → reject string |
| `MemoryStore.__init__` | 124–130 | defaults `memory_char_limit=2200`, `user_char_limit=1375` |
| `MemoryStore.add` | 297–345 | see pseudocode below |
| `MemoryStore.replace` | 347–405 | substring match must be unique; re-check char budget |
| `MemoryStore.remove` | 407–441 | substring match must be unique |
| `MemoryStore._detect_external_drift` | 515–568 | refuse mutate if on-disk file won’t round-trip delimiter parsing |
| `memory_tool` | 602–640 | dispatch + argument validation |
| `MEMORY_SCHEMA` | 652–701 | tool description with WHEN TO SAVE / SKIP (prompt to model) |

**`MemoryStore.add` pseudocode (exact control flow):**

```text
content = strip(content)
if empty → error
if _scan_memory_content(content) → error          # injection/exfil
with file lock:
    reload from disk; if drift → error + .bak
    if content in entries → success, no write     # exact duplicate NOOP
    if join(entries+[content]) > char_limit → error (must replace/remove first)
    append + save_to_disk
```

Exact duplicate branch (real code):

```python
if content in entries:
    return self._success_response(target, "Entry already exists (no duplicate added).")
```

Budget failure returns `success: False` with current entries so the model can consolidate — same idea V3 borrowed for over-budget apply.

**V4 mapping:**

| Hermes | KlassenPilot analogue |
|---|---|
| exact `content in entries` | `insert_with_folding` exact / near-dup |
| char limit refuse | curated page budgets at apply |
| threat scan | output/stream safety (different layer) |
| SKIP list in `MEMORY_SCHEMA` | `DURABLE_MEMORY_CANDIDATE_POLICY` — still mostly prompt |

---

#### D. Hindsight — retain + observation dedup (code + LLM)

**HTTP / orchestration**

| Symbol | File | Role |
|---|---|---|
| `api_retain` | `hindsight-api-slim/hindsight_api/api/http.py` ~6705–6799 | HTTP retain entry |
| `retain_batch` | `.../engine/retain/orchestrator.py` ~557+ | extract facts → embed → persist; early return if **no facts** |

**Observation consolidation / near-dup**

| Symbol | File | Role |
|---|---|---|
| `DEFAULT_CONSOLIDATION_DEDUP_THRESHOLD = 0.97` | `hindsight_api/config.py` ~1003–1007 | cosine gate |
| `_dedup_active(config)` | `engine/consolidation/consolidator.py` ~117–127 | active iff threshold `< 1.0` and DB ≠ Oracle |
| `_dedup_adjudicate(...)` | same ~143–199 | retrieve nearest observation; if sim ≥ threshold, LLM `merge` vs `keep` |
| `_dedup_reconcile_create` | same ~202–245 | on create: skip create if merge |
| `_dedup_reconcile_update` | same ~248–316 | on update: fold or keep |
| write-action enforcement | same ~1574–1707 | reject update/delete whose target wasn’t in recall; drop exact normalized-text duplicate creates |

**`_dedup_adjudicate` logic (simplified):**

```text
threshold = config.consolidation_dedup_threshold   # default 0.97
embed(anchor_text) if needed
neighbors = retrieve_semantic_bm25_combined(..., types=["observation"], top_k=_DEDUP_TOP_K)
best = neighbor with max similarity among those with sim >= threshold
if no best → keep separate (should_merge=False)
else:
    decision = LLM(merge|keep) on (new, existing) texts
    if decision.action != "merge" → keep
    else → should_merge=True with merged_text
```

Docs mirror this in `skills/hindsight-docs/references/developer/observations.md` (proof counts, refine-not-overwrite, scope warning about per-session tags breaking dedup).

**V4 mapping:** Hindsight’s 0.97+LLM merge is a **consolidation-time** pattern (like our Sweep), not a hot-path `remember` gate. Steal: (1) early exit when extraction yields zero facts, (2) evidence/proof accumulation instead of new VIP rows, (3) never treat same-session correlated spam as independent proof (GovMem + our occasions).

---

#### E. OpenClaw core — session journal, flush gate, promotion scoring

**1) Session memory (journal, not preference extraction)**  
`openclaw/src/hooks/bundled/session-memory/handler.ts`

| Symbol | Role |
|---|---|
| `saveSessionToMemory` (~300–315) | Runs only on command action `"new"` or `"reset"` |
| `saveSessionMemoryNow` (~138–298) | Writes last N transcript messages (default **15**) to `memory/` dated file |

No content triage / score / threat scan — filename collision avoidance only.

**2) Memory flush under context pressure**  
`openclaw/src/auto-reply/reply/memory-flush.ts`

| Symbol | Role |
|---|---|
| `resolveMemoryFlushGateState` (~101–134) | Compute token threshold from context window − reserves |
| `shouldRunMemoryFlush` (~136–161) | Require session + tokens ≥ threshold; reject if already flushed for this `compactionCount` |
| `hasAlreadyFlushedForCurrentCompaction` (~185–191) | Once-per-compaction idempotency |

**3) Short-term → durable promotion (the numbers V3 cited)**  
Defaults live in two places:

`openclaw/src/memory-host-sdk/dreaming.ts` (deep dreaming defaults, approx. 31–50):

- `DEFAULT_MEMORY_DEEP_DREAMING_MIN_SCORE = 0.8`
- `DEFAULT_MEMORY_DEEP_DREAMING_MIN_RECALL_COUNT = 3`
- `DEFAULT_MEMORY_DEEP_DREAMING_MIN_UNIQUE_QUERIES = 3`
- `DEFAULT_MEMORY_DEEP_DREAMING_RECENCY_HALF_LIFE_DAYS = 14`
- `DEFAULT_MEMORY_DEEP_DREAMING_MAX_AGE_DAYS = 30`
- `DEFAULT_MEMORY_DEEP_DREAMING_LIMIT = 10`

Executable ranking/apply in `openclaw/extensions/memory-core/src/short-term-promotion.ts`:

| Symbol | Lines (approx.) | Role |
|---|---|---|
| `DEFAULT_PROMOTION_MIN_SCORE` | 47 | **0.75** (internal ranker default; deep config uses 0.8) |
| `DEFAULT_PROMOTION_MIN_RECALL_COUNT` | 48 | **3** |
| `DEFAULT_PROMOTION_MIN_UNIQUE_QUERIES` | 49 | **2** |
| `DEFAULT_PROMOTION_WEIGHTS` | 93–100 | frequency 0.24, relevance 0.30, diversity 0.15, recency 0.15, consolidation 0.10, conceptual 0.06 |
| `isContaminatedDreamingSnippet` | ~405–425 | Reject promotion of contaminated/dream-narrative snippets |
| `rankShortTermPromotionCandidates` | ~1770–1909 | Score + filter below minScore / recall / diversity / age |
| `applyShortTermPromotions` | ~2358–2515 | Re-check gates under lock; append to MEMORY.md; mark promoted |

**Promotion gate pseudocode:**

```text
candidates = short-term entries with positive signals
reject if contaminated / already promoted / stale / age > max
reject if recall_count < minRecall or unique_queries < minUnique
score = Σ weight_i * signal_i (+ phase boosts)
reject if score < minScore
take top `limit`
before write: repeat gates under lock; rehydrate source; marker reconcile
```

**V4 mapping:** Our `memory_gate.py` already ports a simplified version:

- `GATE_MIN_DISTINCT_OCCASIONS = 2` (vs OpenClaw recall_count ≥ 3)
- `FREQUENCY_WEIGHT = 0.6`, `RECENCY_WEIGHT = 0.4`, `RECENCY_HALF_LIFE_DAYS = 14`
- explicit/fast_lane bypasses the occasion wait (VIP path)

V4 does **not** need more OpenClaw promotion math. It needs fewer false VIP stamps *before* `gate_clusters`.

---

#### F. AutoSci — shortlist selection (pattern only)

**File:** `AutoSci/tools/init_discovery.py`

| Symbol | Role |
|---|---|
| `_dedupe_candidates` (~943–960) | Merge by arXiv id / normalized title |
| `_score_candidates` (~1051–1106) | Weighted score − exclusion penalty |
| `_select_shortlist` (~1131–1203) | Cap + diversity penalties |

Constants (~76–89): `SHORTLIST_TARGET = 12`, `FINAL_TARGET_RANGE = [8,10]`, `RANKING_WEIGHTS`, `EXCLUSION_PENALTY = 12`.

**V4 mapping:** “Score then hard-cap what reaches the human” — same spirit as per-turn `remember` budget + Sweep ordering. Not a library to import.

---

#### G. Side-by-side: their functions vs our functions

| Concern | External function(s) | KlassenPilot today | V4 should add |
|---|---|---|---|
| Tool entry | Hermes `memory_tool` / Mem0 OpenClaw `createMemoryAddTool` | `remember` in `tools.py` → `validate_remember_call` | grounding fail → structured error |
| Quote / provenance | Hindsight observation evidence quotes (consolidation) | `_verified_quote` + `DIRECT_TEACHER_QUOTE_PREFIX` | content entailed by quote |
| Explicit vs weak | OpenClaw triage Gate1+2 (prompt); Mem0 `infer` | `discipline_memory_candidates` + markers | require `speech_act`; no marker override |
| Exact dup | Hermes `content in entries`; Mem0 MD5 | `insert_with_folding` exact/`duplicate` | keep |
| Near dup | Hindsight `_dedup_adjudicate` @ 0.97+LLM; Mem0 prompt semantic skip | token overlap ≥ `NEAR_DUPLICATE_OVERLAP` 0.55 | + same-quote fold |
| Creation budget | Hermes char limits; AutoSci shortlist cap; OpenClaw `LIMIT=10` promotions | `candidates_cap` on merged list only | **per-message fast-lane cap** |
| Earn attention | OpenClaw `rankShortTermPromotionCandidates` minScore/recall | `gate_clusters` / `is_fast_lane_row` | leave gate; fix stamp honesty |
| Silence / zero writes | Mem0 empty extract `return []`; Hindsight retain early-exit | prompt “silence is normal” | budget + reject ungounded |
| Never-store list | OpenClaw SKILL.md + Hermes `MEMORY_SCHEMA` SKIP | partial in `DURABLE_MEMORY_CANDIDATE_POLICY` | strengthen + code reject patterns where cheap |

**KlassenPilot call chain today (for comparison):**

```text
remember(...)                         # tools.py
  → validate_remember_call(...)       # memory_capture.py  (target, quote⊂message, content nonempty)
  → runtime.memory_candidates.append
persist turn:
  → discipline_memory_candidates(...) # speech_act / markers / quote verify → fast_lane
  → insert_with_folding(...)          # already_covered / suppressed / duplicate / near fold
later sweep:
  → gate_clusters(...)                # memory_gate.py  (fast_lane OR occasions≥2)
  → memory_sweep propose/apply
```

**Missing vs external best practice:** a function between `validate_remember_call` and `discipline_memory_candidates` that answers Hermes/OpenClaw’s NOOP question in code — *“is this claim actually new and actually what the quote said?”* — plus a hard creation budget like AutoSci’s shortlist / Hermes’ char refuse.

### 4.9 Core system-prompt / instruction ideas — and multi-model design

How these repos teach the model what to remember, and how they stay usable across many LLMs. This matters for V4 because KlassenPilot already runs different model profiles (economy vs production) and learned in V3 that **capture quality is model-sensitive** (under-emission on weak models; over-atomization when the tool is too salient).

---

#### A. Where instructions live (layered pattern)

Every serious memory stack uses **more than one channel**. Relying on a long system prompt alone fails when the model is busy doing planning.

| Layer | What it carries | Mem0 / OpenClaw | Hermes | Hindsight | KlassenPilot today |
|---|---|---|---|---|---|
| **System / skill protocol** | Principles, gates, never-store, examples | Injected `memory-triage/SKILL.md` via `prependSystemContext` (`integrations/openclaw/index.ts`); compact form via `loadCompactTriagePrompt()` in `skill-loader.ts` | `MEMORY_GUIDANCE` in `agent/prompt_builder.py` + frozen USER/MEMORY snapshot in system prompt | Bank-agnostic extraction **system** prompt (cached); missions in **user** content | `DURABLE_MEMORY_CANDIDATE_POLICY` in `prompts.py`, assembled in `prompt_assembly.py` |
| **Tool schema / docstring** | When to call, args, SKIP list | `createMemoryAddTool()` schema (“save … proactively”) | `MEMORY_SCHEMA` in `memory_tool.py` (WHEN TO SAVE / SKIP / two targets) | N/A to chat agent — retain is a backend API | `remember(...)` docstring in `tools.py` |
| **Backend / second LLM** | Extraction independent of chat model | OSS `Memory.add(infer=True)` uses `ADDITIVE_EXTRACTION_PROMPT` | None for curated memory (agent writes directly) | `retain_batch` + `fact_extraction.py`; consolidation LLM separate | Capture is **same** chat model calling `remember`; Sweep uses a stronger consolidation model |
| **Deterministic code** | Hard refuse / stamp / budget | MD5 dedup, noise filters, dream schedule gates | char limits, exact dup, threat scan | cosine 0.97 gate + structural rejects | `validate_remember_call`, `discipline_memory_candidates`, `insert_with_folding`, `gate_clusters` |

**Shared idea:** put the *philosophy* in a stable prompt block; put the *affordance* in the tool; put the *truth checks* in code. V3 already aimed at this; V4 strengthens the code layer so weaker/stronger chat models cannot flood the ledger.

---

#### B. Core instruction ideas worth stealing (plain principles)

These recur across repos. Short form — the “constitution” of memory prompts:

1. **Would a future agent with no chat history need this?**  
   OpenClaw triage core question (`memory-triage/SKILL.md`). If no → do nothing.

2. **Silence is success.**  
   “Most turns produce zero memory operations.” (OpenClaw triage; Hermes background-review framing; our V3 axiom.)

3. **Conjunctive gates, not vibes.**  
   Future utility ∧ novelty ∧ factual ∧ safe (OpenClaw). All must pass.

4. **Material change or skip.**  
   Synonym rephrase ≠ update. (“Loves walks” vs “enjoys walks” = SKIP.)

5. **One self-contained fact per real topic; entity-group related bits.**  
   Don’t atomize one sentence into eight prefs; don’t use pronouns without names.

6. **Never-store list is mandatory.**  
   Secrets, raw tool dumps, one-off commands, acknowledgments, transient UI/status, already-known unchanged facts.

7. **Teacher/user words over assistant echo.**  
   Mem0 ROLE: don’t extract assistant restatements of user facts; our V3 “teacher-words-only.”

8. **Preserve the user’s phrasing for preferences.**  
   OpenClaw: keep exact preference wording rather than sanitizing into vague summaries.

9. **Third person / durable wording.**  
   “User prefers…” / “Teacher wants…” — not “I will remember…”

10. **Standing rules ≠ this-turn task.**  
    Hermes + our speech_act: “make this shorter” is not memory; “from now on always start with a 5‑min review” is.

11. **Dream/consolidate is a different prompt.**  
    OpenClaw `memory-dream/SKILL.md`: first orient with no writes; then DELETE / MERGE / REWRITE; quality bar 15–50 words, dated, no secrets. Maps to our Sweep, not to `remember`.

12. **Separate “what to extract” from “what lasting belief looks like.”**  
    Hindsight: `retain_mission` vs `observations_mission`; extraction mode `concise` | `verbose` | `custom`. Concise asks roughly “useful in six months?”

**Anti-pattern to reject for V4 prompts:** Mem0 additive ROLE line *“When in doubt, extract”* (`mem0/configs/prompts.py`). That is the opposite of a teacher-copilot write gate.

---

#### C. How they structure prompts for many models

##### 1) Provider adapters, not prompt forks per vendor

- **Mem0:** `mem0/utils/factory.py` registers many LLM adapters (OpenAI, Anthropic, Gemini, Ollama, Bedrock, LiteLLM, Groq, DeepSeek, LM Studio, vLLM, …). Claim in skills docs: “Works with any LLM provider” = *wiring*, not equal quality.
- **Hindsight:** `create_llm_provider()` (`engine/llm_wrapper.py`) + `MultiLLMProvider` failover / weighted round-robin (`engine/multi_llm.py`). Separate `retain_llm_provider` vs `consolidation_llm_provider` so extraction and merge can use different models.
- **OpenClaw Mem0 plugin:** `Mem0Provider` interface + `createProvider()` platform vs OSS (`integrations/openclaw/providers.ts`); OSS wizard offers OpenAI / Ollama / Anthropic.
- **Hermes:** memory tool is provider-neutral; prompt builder adds *small* family-specific operational guidance (`TOOL_USE_ENFORCEMENT_MODELS`, Google/OpenAI execution hints in `prompt_builder.py`) without rewriting the memory policy.

**V4 takeaway:** Keep one `DURABLE_MEMORY_CANDIDATE_POLICY` + one `remember` schema. Don’t maintain Claude-vs-GPT memory constitutions. Optional thin “tool-use enforcement” overlays are fine (Hermes style).

##### 2) Stable system prefix + variable user payload (cache-friendly)

- **Hindsight:** invariant extraction rules stay in a bank-agnostic **system** prompt; `retain_mission` / `observations_mission` go in **user** content via `_retain_mission_preamble()` so one cached prefix serves many banks.
- **Hermes:** `format_for_system_prompt()` freezes USER.md / MEMORY.md at **session start**; mid-session `MemoryStore.add` updates disk but **does not** rewrite the system prompt (prefix-cache preservation). Live state is read via the tool.
- **OpenClaw skills:** skill catalog is snapshotted per session with a character budget and compact fallback (`skills/loading/workspace.ts`).

**V4 takeaway:** Keep durable-memory policy in the stable prompt assembly. Put “open ledger claims / current profile bullets” in a **bounded, per-turn** block (volatile), not by rewriting the whole constitution each turn. Matches deferred V3 “capture sees what it knows.”

##### 3) Structured contracts beat prose for weak models

| Technique | Who | Why it helps many models |
|---|---|---|
| JSON `response_format` + `ensure_json_instruction()` | Mem0 extraction (`memory/main.py`, `memory/utils.py`) | Models that ignore prose still emit parseable facts; embedded-JSON recovery if fences appear |
| Tool calls with required fields | Hermes `memory`, OpenClaw `memory_add`, our `remember` | Salient affordance; schema constrains args |
| Enum-like speech acts / categories | OpenClaw categories; our `conduct_request` / `store_request` / `observation` | Narrower decision than free text |
| Character budgets not token budgets | Hermes `memory_char_limit` / `user_char_limit` | Tokenizers differ by model; chars are model-independent |
| Substring `old_text` replace instead of IDs | Hermes `replace`/`remove` | Avoids brittle ID formats some models invent |
| Exact dup → success no-op | Hermes `add` | Weak models can “retry save” safely |
| Reasoning-model param filtering | Mem0 `llms/base.py` drops incompatible sampling fields | Same code path works for o-series / thinking models |
| Compact vs full skill prompt | OpenClaw `loadCompactTriagePrompt` vs full SKILL.md | Smaller models get shorter critical rules; large models can take examples |
| Fail closed on LLM errors vs “no facts” | Mem0 raises `LLMError` distinct from empty extract | Empty ≠ outage; avoids silent data loss or retry storms |
| Narrative/dream model fallback | OpenClaw `dreaming-narrative.ts`: retry default model, then generic text | Optional creative path never blocks durable promotion |

##### 4) Split “chat model” from “memory maintenance model”

Industry pattern:

| Job | Typical model choice | Who |
|---|---|---|
| Interactive agent (plan/discuss) | User-selected / mid | Hermes, OpenClaw, us |
| Hot-path fact extract (if any) | Often **mini/cheap** (Mem0 OSS default `gpt-5-mini`) | Mem0 `infer=True` |
| Consolidation / dream / sweep | Stronger / slower, async or teacher-clicked | OpenClaw dream; Hindsight consolidation LLM; **our Sweep** |
| Durable promotion scoring | **No LLM** — thresholds on recalls | OpenClaw `rankShortTermPromotionCandidates` |

**Critical nuance for us:** KlassenPilot’s capture is **not** a separate mini extractor. The same planning/discuss model must call `remember`. That is why:

- V3 Learning 8: weak models **under-emitted** until `remember` became a tool and capture moved off the mini tier.
- Current ochem symptom: a capable model with a salient tool **over-emits** when code gates are loose.

So multi-model support for KP ≠ “run Mem0 extract on gpt-5-mini.” It means:

1. **Code gates identical** across economy/production (grounding, speech_act, caps).  
2. **Prompt short enough** that economy models still see SAVE/SKIP/silence.  
3. **Sweep stays on a strong model** (already V3).  
4. **Evals measure emission and precision separately** per model profile (Learning 8).

##### 5) Skills mode vs automatic infer (OpenClaw/Mem0)

OpenClaw skills path (important):

```text
Agent (any chat model) follows triage skill
  → calls memory_add(facts=[...])
  → plugin stores with infer=false + deduced_memories
  → Mem0 does NOT re-extract / re-judge
```

Automatic / platform path often uses `infer=True`, so a **second** model (Mem0’s configured LLM) re-decides what to store — quality then depends on that extractor’s prompt (including “when in doubt, extract”).

**V4 takeaway:** We already resemble **skills mode**: chat model proposes via `remember`, backend validates, no second permissive extractor. Keep it that way. Do **not** add a Mem0-style blind `infer=True` pass on every teacher turn.

##### 6) What they do *not* promise

None of these repos honestly promise “same memory quality on every model.” They promise:

- same **API / tool contract**
- same **provider wiring**
- degradations handled (compact prompts, JSON recovery, failover, narrative fallback)

Quality still tracks model strength for judgment tasks. Hence **code-enforced admission** is the portable quality floor.

---

#### D. Concrete prompt/instruction recommendations for KlassenPilot V4

Keep one shared policy block; make it look more like OpenClaw’s compact triage + Hermes SKIP; keep examples in the tool docstring.

**1) Compact “constitution” bullets to keep at the top of `DURABLE_MEMORY_CANDIDATE_POLICY`:**

```text
Core question: would a future lesson plan, with no this-chat context, need this?
Most turns: call remember ZERO times.
All of these must be true: standing scope (not this document only),
novel vs open/applied memory, concrete, grounded in a verbatim teacher quote,
and content restates that quote (no extra invented prefs).
Never store: one-off task wording, thanks/ok, your own plan ideas,
lesson observations (those go through Update Memory / wiki), secrets.
Cap: at most 2 remember calls per teacher message unless they clearly
state two distinct standing rules.
```

**2) Tool schema carries the procedural detail** (targets, speech_act enums, overlap examples) — Hermes/OpenClaw pattern. Keep retry errors short and actionable (already started in `validate_remember_call`).

**3) Optional compact vs full policy by `MODEL_PROFILE`:**  
economy → compact constitution only; production → constitution + short worked examples. Mirror OpenClaw `loadCompactTriagePrompt` vs full SKILL.md. Same code gates either way.

**4) Do not ask the chat model to run ADD/UPDATE/DELETE/NOOP at capture time.**  
That is Sweep’s job (Mem0 legacy update prompt / OpenClaw dream). Capture only stages; code does NOOP/fold.

**5) Hindsight-style mission split (optional later):**  
- Capture policy = “standing instructions to the copilot” (`retain_mission` analogue).  
- Sweep policy = “how to edit curated bullets” (`observations_mission` analogue).  
Keep them in different prompt files so capture never inherits “exhaustive extract.”

**6) Multi-model eval matrix (ship with V4):**  
For the same golden teacher messages, run economy + production and assert:

| Metric | Floor |
|---|---|
| True standing instruction emitted | ≥1 remember (no V2 under-emission regression) |
| Ungounded extra prefs | 0 fast_lane |
| Max fast_lane per message | ≤ cap (2) |

---

#### E. Side-by-side: instruction “home” for the same idea

| Idea | Best external home | KP V4 home |
|---|---|---|
| Silence default | OpenClaw SKILL + compact prompt | Top of `DURABLE_MEMORY_CANDIDATE_POLICY` |
| Four gates / material NOOP | OpenClaw SKILL (prompt) + our code | Prompt summary + **code** grounding/budget |
| When to call tool | Hermes `MEMORY_SCHEMA` / OpenClaw tool desc | `remember` docstring |
| Never-store list | OpenClaw SKILL § What NEVER to Store | Policy + cheap regex rejects if useful |
| Frozen memory in prompt | Hermes snapshot | Existing context packs (profiles); don’t inject ledger |
| Exhaustive extract | Mem0 additive ROLE — **avoid** | Not used |
| Consolidation instructions | OpenClaw dream skill / Mem0 update prompt | Sweep prompts only |
| Works across models | Adapters + JSON/tools + char budgets + code gates | Same; add compact policy for economy |

---

## 5. Recommended Memory V4 improvements (concrete)

### Design stance (locked proposal for discussion)

1. Keep lifecycle and HITL.  
2. Prefer false negatives at **fast-lane admission**. Missed prefs can be restated; junk VIP cards poison trust.  
3. Hot path stays **no extra LLM** if possible. Use deterministic gates first; optional tiny judge only if grounding proves too hard with heuristics.  
4. Sweep remains the place for expensive semantic merge.  
5. No new pip dependency for memory substrate.

### 5.1 Change A — Claim↔quote grounding gate (highest leverage)

**Where:** `validate_remember_call` and/or `discipline_memory_candidates` in `memory_capture.py`.

**What today:** quote must appear in teacher message; content unchecked.

**What to change:**

Before accepting / fast-laning a candidate, require that `content` is a reasonable paraphrase of `quote` (or of an explicit contiguous span of the teacher message).

Concrete deterministic v1 (ship first):

1. Tokenize quote and content (reuse ledger stemming helpers or share a small util).  
2. Require overlap coefficient ≥ threshold (start ~0.35–0.45 calibrated on goldens — lower than near-dup 0.55 because paraphrase is shorter/longer).  
3. Additionally require at least one “anchor” content word from the quote (noun/verb length ≥4) appears in content.  
4. If fail → return tool error:  
   `Not saved. The content must restate the quoted teacher sentence; do not add extra preferences.`  
   Model may retry with tighter content — or skip.

Optional v1.1 (only if evals show too many false rejects):

- Small structured judge call **only for borderline overlaps**, not for every remember. Still prefer reject on clear fails.

**Acceptance examples:**

| Quote | Content | Result |
|---|---|---|
| “always do a 5-minute review” | “Always start lessons with a 5-minute review.” | accept |
| “always do a 5-minute review” | “Prefer pair work for hybridization demos.” | reject |
| “avoid abstract orbital explanations” | “Do not open with abstract orbitals; use concrete models first.” | accept |
| whole multi-clause message quoted | three separate contents each matching one clause | accept each (budget permitting) |
| same quote reused for unrelated claim | reject |

### 5.2 Change B — Fast lane requires real speech_act (kill marker override)

**Where:** `discipline_memory_candidates` (`memory_capture.py`).

**What today:**

```text
act_ok = (
  speech_act == "store_request" if policy == "store_request"
  else speech_act in ("conduct_request", "store_request") or marker_scoped
)
```

**What to change:**

For tool-originated candidates (`remember` path):

- Require `speech_act` ∈ allowed set for the target policy.  
- Use `marker_scoped` **only** as corroboration when speech_act is empty **and** source is a legacy typed-state repair path — never to override a missing/wrong act on new tool candidates.

Also: do not stamp `fast_lane=True` when verified quote fell back to the **entire message** unless speech_act is valid **and** grounding passes against a specific span. Prefer requiring a non-empty model quote for fast lane.

**Acceptance:**

- Message contains “always” + model emits observation-flavored content with empty speech_act → **not** fast lane (inferred/low or rejected).  
- Message contains “always” + `conduct_request` + grounded content → fast lane.

### 5.3 Change C — Per-turn creation budget

**Where:**

- `validate_remember_call` / tool return in `tools.py` (soft refuse after N)  
- and/or `merge_memory_candidates` / persist in `artifact_session_service._persist_memory_candidates`  
- config knob next to context limits (e.g. `remember_fast_lane_cap_per_turn = 2`)

**Policy proposal:**

| Kind | Cap per teacher message |
|---|---|
| Fast-lane accepts | **2** (default) |
| Total `remember` accepts (incl. inferred downgrades) | **4** |
| Beyond cap | tool error: merge into fewer facts or skip |

Align prompt examples: the electricity-block “capture twice” overlap example in `prompts.py` / `tools.py` should stay allowed (2 targets) but not become a license for 8 profile atomizations.

**Also revisit** the prompt line that encourages splitting into multiple remembers for overlapping targets — keep for *true* dual-purpose facts; add “never atomize one sentence into many profile prefs.”

### 5.4 Change D — Merge-first / NOOP before new open row

**Where:** `insert_with_folding` callers + optional pre-check in `discipline_memory_candidates`.

**What today:** near-dup fold exists at 0.55 overlap against open/applied/rejected; unrelated claims still create new clusters.

**What to add:**

1. When a new candidate is grounded but near-dup to open cluster → fold (already).  
2. When near-dup to applied → `already_covered` (already).  
3. **New:** if same `(target)` + same verified quote span already has an open fast-lane row this session → fold into that cluster or reject as duplicate, even if content wording differs slightly.  
4. **New tool response vocabulary** (model-facing):  
   - `Saved for review…`  
   - `Already noted (same as open claim)…`  
   - `Not saved (duplicate of applied memory)…`  
   so the model stops retry-spamming equivalents.

Steal OpenClaw triage wording for material difference in prompts; enforce with folding + quote-span key.

### 5.5 Change E — Tighten SAVE/SKIP prompt + tool docstring (secondary)

**Where:** `DURABLE_MEMORY_CANDIDATE_POLICY` in `prompts.py`; `remember` docstring in `tools.py`.  
**Detail:** see §4.9 D for the compact constitution text and multi-model notes.

Add an explicit never-store / one-message budget block adapted from OpenClaw triage + Hermes SKIP — teacher-domain examples:

- SKIP: “make this lesson shorter”, “use MBB on this plan”, “thanks”, acceptance of agent suggestions without standing scope  
- SKIP: lesson observations → ingest/wiki path  
- SAVE at most the distinct standing instructions actually stated  
- FORBIDDEN: invent prefs not in the quote (pair work, demo format, etc.)

Optional: compact policy for economy `MODEL_PROFILE`, full examples for production (OpenClaw compact vs full skill pattern).

**Important:** treat prompt changes as **supporting** Changes A–D, not as the fix. Code gates must be identical across model profiles.

### 5.6 Change F — Capture context visibility (finish deferred V3 item)

`docs/mem_v3/design.md` / `implementation_plan.md` asked for capture context to include current memory excerpts + open ledger claims so the model can skip known claims. Still incomplete for the tool path.

**Concrete:**

- When building plan/ingest/discuss prompts, inject a short “Open memory candidates + current profile bullets (truncated)” block for allowed targets.  
- Tool errors can mention “already covered: …”.

This reduces emission of known prefs; grounding/budget still required for unknown ones.

### 5.7 Change G — Telemetry and evals (ship with A–C)

Add / extend:

1. Offline fixtures from the ochem over-capture ledger (like V3’s `tests/fixtures/mem_v3/organic_chemistry_ledger.json`).  
2. Unit tests for `discipline_memory_candidates` / `validate_remember_call`:  
   - same quote + unrelated content → reject  
   - marker-only without speech_act on tool candidate → no fast lane  
   - third remember in one message → budget error  
3. Live judge eval: measure **emission count** and **grounding precision** separately (Learning 8 lesson).  
4. Product metric: median open fast-lane cards per class per day; target << current sandbox flood (owner-set number, e.g. ≤3 VIP cards per short standing-instruction turn).

### 5.8 Explicitly out of scope for V4

- Replacing Sweep with Mem0 Dream  
- Embeddings / SAGE on every turn  
- Auto-apply of fast-lane without teacher review  
- Changing student-summary / lesson commit pipelines (separate trust work; see `docs/mem_v3/input_reconciliation.md`)  
- PR5 agent skills fanout from `next_implementation.md` until write admission is trusted

---

## 6. Proposed implementation sequence

| PR | Scope | Risk | Depends |
|---|---|---|---|
| **V4-PR1** | Change B (speech_act required) + Change A (deterministic grounding) + unit tests | Low–med | — |
| **V4-PR2** | Change C (per-turn caps) + prompt/tool docstring tightening (E) | Low | PR1 preferred |
| **V4-PR3** | Change D (same-quote / merge-first responses) + Change F (open-claim visibility) | Med | PR1 |
| **V4-PR4** | Eval harness + sandbox regression fixtures + telemetry counters | Low | PR1–2 |

Suggested acceptance bar for “V4 done”:

1. Goldens **G1–G5** from [`empirical_inputs.md`](empirical_inputs.md) §7 (smoking-gun plan message ≤2 FL; orbital / phenomenon-first still emit once; no ungounded visual/hybridization/demo junk).  
2. Live: standing-instruction turns still emit *at least one* remember when clearly warranted (do not reintroduce V2 under-emission).  
3. No Mem0/OpenClaw runtime dependency added.  
4. `docs/agent_contracts.md` updated in the same PR as behavior changes.

---

## 7. Exact file touch list (implementation map)

| File | Change |
|---|---|
| `backend/app/teacher_agent/memory_capture.py` | grounding helper; speech_act-strict fast lane; optional quote-span key; stop whole-message quote fallback for fast lane |
| `backend/app/teacher_agent/tools.py` | per-turn counter / clearer tool errors; docstring budget + never-invent rules |
| `backend/app/teacher_agent/prompts.py` | `DURABLE_MEMORY_CANDIDATE_POLICY` silence + never-store + no atomization |
| `backend/app/services/artifact_session_service.py` | persist-time budget enforce; pass teacher message consistently into discipline |
| `backend/app/services/memory_candidate_ledger.py` | same-quote cluster fold; richer duplicate statuses if needed |
| `backend/app/services/memory_gate.py` | probably unchanged if fast_lane stamp becomes honest |
| `backend/app/config.py` / `context_limits.py` | caps tunables |
| `backend/tests/…` | unit + fixture regression; extend live capture eval |
| `docs/agent_contracts.md` | write-admission contract |
| `docs/mem_v4/` | this brainstorm → later `design.md` / `implementation_plan.md` once approved |

---

## 8. Mapping V3 axioms → V4 enforcement

| V3 axiom (`approach.md`) | Enforced today? | V4 action |
|---|---|---|
| Teacher-words-only | Partial (quote exists) | Ground content to quote |
| Silence is normal | Prompt only | Per-turn budget |
| Backend-owned fast lane | Partial (marker hole) | Require speech_act; no marker override on tools |
| Attention must be earned | Yes for inferred; bypassed by false fast lane | Fix fast-lane stamp |
| Deterministic structure / model meaning | Yes at sweep | Keep; don’t add hot-path LLM unless needed |
| Rare consolidation = strong model | Yes | Unchanged |

---

## 9. Open questions for the owner

1. **Cap numbers:** Is `fast_lane ≤ 2` per teacher message the right default, or `1`?  
2. **Grounding strictness:** Prefer more missed memories (stricter overlap) or more teacher review of borderline paraphrases?  
3. **Dual-target examples:** Keep encouraging teaching_patterns + planning_brief doubles, or only allow doubles when teacher explicitly says “remember for the block / remember how the class learns”?  
4. **Passive typed-state preference repair:** Delete once `remember` is stable, or keep as safety net under the same gates?  
5. **Discuss vs Plan vs Ingest:** Same caps everywhere, or stricter on Plan (where ochem flood was seen)?  
6. **Should V4 bump the live capture model tier further**, or is admission code enough?

---

## 10. Appendix A — Plain-language glossary

| Term | Meaning |
|---|---|
| **Ledger** | Waiting list of proposed memory notes (SQLite). Teacher doesn’t edit it directly. |
| **Fast lane** | VIP stamp: “teacher clearly asked for this standing rule” → show in Sweep sooner. |
| **Inferred** | “Maybe this matters” — must show up more than once before bothering the teacher. |
| **Quote provenance** | Proof the teacher typed the cited sentence. |
| **Grounding** | Proof the saved note is about that sentence (the missing piece). |
| **Folding** | Merging a repeat/rephrase into an existing waiting-list claim instead of a new card. |
| **Sweep** | Teacher review UI that turns waiting-list claims into wiki edits. |
| **Journal vs checkpoint** | Rough evidence log vs clean lasting notebook. Ledger ≈ journal; wiki ≈ checkpoint. |

---

## 11. Appendix B — Key KlassenPilot quotes (current code/docs)

From `docs/mem_v3/approach.md`:

> Silence is the normal outcome. Most chat turns produce zero memory candidates. A system biased to notice things drowns; one biased to silence stays legible.

From `docs/mem_v3/design.md`:

> Backend-owned fast lane for direct teacher speech acts, not marker heuristics. The model supplies `speech_act`; deterministic code verifies target policy and quote provenance.

From `docs/mem_v3/learnings.md` (Learning 8):

> …the model's *judgment is sound* — all negatives … correctly stayed out of the fast lane — but the *emission rate is the bottleneck*…

From `prompts.py` `DURABLE_MEMORY_CANDIDATE_POLICY`:

> Most turns produce NO memory candidates. Silence is the normal outcome; capture only when something genuinely new and durable appears.

From `memory_gate.py` module docstring:

> explicit teacher asks are eligible only via the verified fast-lane verdict… inferred claims need captures on >= 2 distinct OCCASIONS…

---

## 12. Appendix C — Key external quotes (ref_repos)

**OpenClaw Mem0 triage** (`mem0/integrations/openclaw/skills/memory-triage/SKILL.md`):

> Most turns produce zero memory operations. That is correct and expected.

> All four gates must pass. If any fails → do nothing.

**Mem0 additive extractor** (`mem0/mem0/configs/prompts.py`) — do *not* adopt:

> When in doubt, extract.

**Hermes** (`hermes-agent/tools/memory_tool.py`):

> SKIP: trivial/obvious info, things easily re-discovered, raw data dumps, and temporary task state.

**Hindsight** (`hindsight/.../observations.md`):

> Each observation tracks its supporting evidence (with exact quotes) and a proof count, and is refined rather than overwritten when new evidence arrives.

---

## 13. Recommended owner decision

Approve V4 direction as:

> **Admission control for `remember` / fast lane — not a new memory product.**

Then authorize V4-PR1 (grounding + speech_act) as the first code change. Defer any discussion of importing Mem0/OpenClaw unless PR1–PR3 fail to bring Sweep VIP volume under the acceptance bar.

---

*End of brainstorm. Next doc after approval: `docs/mem_v4/implementation_plan.md` with tests-first goldens.*
