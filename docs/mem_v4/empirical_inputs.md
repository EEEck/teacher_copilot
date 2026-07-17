# Memory V4 — Empirical Inputs (sandbox evidence)

Status: supporting evidence for [`brainstorm.md`](brainstorm.md)  
Captured: **2026-07-16** from worktree sandbox  
Class: `chemie_9b_2026_27`

Raw machine snapshots (same day):

- [`_ledger_snapshot.json`](_ledger_snapshot.json) — full `memory_candidates` rows  
- [`_sweep_cards.json`](_sweep_cards.json) — open Memory Sweep cards from the `ready` review  

These are **inputs to the V4 decision**, not production fixtures yet. Promote into `backend/tests/fixtures/mem_v4/` when implementation starts.

---

## 1. What we analyzed

Three layers were compared carefully:

1. **Teacher prompts** the user pasted (mock ochem Lesson 1/2 plan + results, plus a short mid-plan chat).  
2. **Ledger rows** in `backend/teacher_wiki_sandbox/workflow/memory_candidates.sqlite`.  
3. **Memory Sweep cards** in the open browser review (`memory_sweep_reviews.sqlite`, status `ready`).  
4. **Capture prompts / tool contract** currently injected into the agent (`DURABLE_MEMORY_CANDIDATE_POLICY` + `remember(...)`).

Owner observation (paraphrased): *few short chats produced many ledger items; Sweep showed them mostly under “explicitly requested,” which did not match the teacher’s intent; student observations also appeared in Sweep.*

---

## 2. Ledger snapshot (16 rows)

Source DB: `backend/teacher_wiki_sandbox/workflow/memory_candidates.sqlite`

| Metric | Value |
|---|---|
| Total rows | **16** |
| `fast_lane=1` | **13** |
| `source=teacher_explicit` | **13** |
| Status | applied 4 · captured 11 · already_covered 1 |
| Targets | `teacher_profile.md` 9 · `copilot_profile.md` 4 · `teaching_patterns.md` 2 · `planning_brief.md` 1 |

### 2.1 By workflow / session

| Session (short) | Workflow | Rows | Fast-lane | Notes |
|---|---|---|---|---|
| `5eeda0f5…` | plan | 2 | 2 | MBB + nervous-teacher plan style → later **applied** (fair) |
| `b36ce0e6…` | discuss | 2 | 2 | LC quote + careful mem-update check → **applied** (fair) |
| `eb24ae08…` | ingest | 3 | 1 | Lesson-1 style result: 1 fair FL orbital avoid; 2 inferred patterns/brief |
| `40510c49…` | plan | **7** | **7** | **Smoking gun** short pchem + “always 5 min review” message |
| `239f41c4…` | ingest | 2 | 1 | Lesson-2 style: fair FL phenomenon-first; 1 inferred teaching pattern |

### 2.2 Smoking-gun plan turn (`session 40510c49…`)

Teacher message (approx. verbatim from chat banner investigation):

> ok i like pchem so lets add some aspects of physics of solutbiliy and compar water vs different alkanes  
> and general lets always add a 5 min review what are most important aspects of the teaching block no ochem

Banner at the time: **“7 review-only memory candidates staged this session.”**

What landed in the ledger (all same `created_at`, all `fast_lane=1`, almost all sharing the **same whole-message quote**):

| id (short) | Target | Candidate content | Grounded in that message? |
|---|---|---|---|
| `cand_024560…` | `copilot_profile.md` | Always include a 5-minute review… | **Yes** (explicit “always”) |
| `cand_73eda8…` | `teacher_profile.md` | Include a 5-minute review… | **Yes** (duplicate of above, second target) |
| `cand_fdcc67…` | `teacher_profile.md` | Make solubility more physics/particle-oriented… | **Partial** (pchem/solubility ask — more this-lesson than standing rule) |
| `cand_b1a721…` | `teacher_profile.md` | Use visual/spatial and concrete examples. | **No** — not in this message |
| `cand_8a8bfd…` | `teacher_profile.md` | Keep hybridization intuitive, not abstract. | **No** — from earlier lesson context / plan brief, not this message |
| `cand_c46475…` | `teacher_profile.md` | Include a short demo or thought experiment. | **No** |
| `cand_d432fb…` | `teacher_profile.md` | Use pair work after board introduction. | **No** — folded `already_covered` (already in profile) |

Evidence pattern on the bad rows (important):

```text
Direct teacher quote: ok i like pchem so lets add some aspects of physics of
solutbiliy ... and general lets always add a 5 min review ...
| Teacher explicitly framed this as a durable preference: <same whole message>
```

So the backend accepted the **entire teacher message** as the quote passport, and several contents were **not entailed** by that text. The `| Teacher explicitly framed this as a durable preference:` suffix matches the typed-state repair path (`teacher_preference_candidate` / `durable_preference_candidates_from_state_values` in `memory_capture.py`), not a tight `remember(quote=specific sentence)`.

### 2.3 Fair explicit captures (contrast)

These look like true standing instructions and should remain allowed under a stricter gate:

| Claim | Quote gist | Target |
|---|---|---|
| Avoid overly abstract orbital explanations unless asked | “I want the copilot to avoid overly abstract orbital explanations…” | `copilot_profile.md` |
| Phenomenon-first for new ochem concepts | “For new organic chemistry concepts, I prefer a phenomenon-first structure…” | `copilot_profile.md` |
| Always 5-min review of teaching-block essentials | “general lets always add a 5 min review…” | `copilot_profile.md` (one row enough) |
| MBB communication + reassuring plan detail | earlier plan chat | `teacher_profile` + `copilot_profile` |
| Careful mem-update checks (multi-class mixups) | discuss chat | `teacher_profile.md` |

### 2.4 Correctly non-fast-lane (good discipline examples)

| Claim | Source / FL | Why OK |
|---|---|---|
| Class benefits from molecule kits before terminology | inferred / FL=0 | Lesson observation → should not VIP |
| Keep redox recap brief… | inferred / FL=0 | Planning note / open loop shape |
| Class responds better to phenomenon-first sequence | inferred / FL=0 | Pattern observation |

---

## 3. Memory Sweep cards (14 open)

Source: `memory_sweep_reviews.sqlite`, review `16d65ab6-…`, status `ready`, generated `2026-07-16T20:43:02Z`.

| Queue | Cards | Basis shown |
|---|---|---|
| **Teacher/Copilot Preferences** | **8** | all `basis=explicit` |
| **Student Memory** | **6** | all `basis=inferred` |

### 3.1 Preference queue (why everything looked “explicitly requested”)

Sweep pins / labels from the **gate’s fast-lane / explicit verdict**, not from a fresh human judgment of “did I ask to remember this forever?”

The 8 preference cards included both fair standing rules **and** the ungounded atomizations:

| Content (short) | Fair? |
|---|---|
| Avoid abstract orbital explanations unless asked | Yes |
| Include 5-minute review of teaching-block essentials | Yes |
| Phenomenon-first for new ochem concepts | Yes |
| Lesson structure includes 5-minute review (adjust) | Mostly (merge of 5-min rule) |
| Keep hybridization intuitive rather than abstract | **No** for this short chat |
| Prefer visual/spatial + concrete examples | **No** for this short chat |
| Include short demo / thought experiment | **No** for this short chat |
| Make solubility more physics/particle-oriented | Borderline / this-lesson |

**Teacher’s gut feeling was right:** not all of these were direct standing requests. The UI category followed `fast_lane` / `basis=explicit` stamped at capture time.

### 3.2 Student Memory queue (why students appear in Sweep)

This is a **separate channel** from preference `remember()`:

- Ingest writes dated observations onto student pages / lesson record (wiki path).  
- Sweep’s **Student Memory** queue proposes `## Student Summary` rollups (`operation=adjust`, `channel=student_memory`).  
- Cards for S-009, S-014, S-017, S-021, S-028, S-033 matched the mock lesson-result student notes.

So: **not a preference fast-lane bug.** It is the student-summary consolidation path. Docs/contracts intentionally keep lesson/student facts on the wiki commit path and summaries in Sweep — but the UX can feel like “more memory spam” next to the preference flood.

V4 preference work should not disable student summaries; it may want clearer UI separation (already two queues) and trust work tracked under mem_v3 input reconciliation.

---

## 4. Teacher prompts vs what should have been remembered

### 4.1 Four mock ochem prompts (abbreviated)

Full text was provided by the owner in chat (2026-07-16). Essence:

1. **Plan L1** — first ochem lesson, redox bridge, carbon bonding, intuitive hybridization; asks for full lesson plan artifacts.  
2. **Result L1** — kits > abstract hybridization; **explicit preference:** avoid overly abstract orbitals unless asked; student notes; suggests wiki updates (class_state / open loop / teaching pattern).  
3. **Plan L2** — alkanes, polarity, solubility; mentions prior visual/spatial need and keep hybridization intuitive **as planning context**, not necessarily “store forever.”  
4. **Result L2** — phenomenon-first worked; **explicit preference:** phenomenon-first structure for new ochem; misconceptions; student notes; wiki-oriented suggestions.

### 4.2 Intended durable prefs (owner-aligned)

From those prompts, a strict admission policy should keep roughly:

1. Avoid abstract orbitals unless asked → `copilot_profile`  
2. Phenomenon-first for new ochem → `copilot_profile`  
3. Always 5-min block review (from the short plan chat) → `copilot_profile` (single card)  
4. Optional: pchem/solubility physics angle — either this-lesson plan note or one scoped preference, **not** five profile micro-facts  

Should **not** VIP-capture from planning context alone:

- “use visual/spatial” (already in L2 plan brief as consideration)  
- “hybridization intuitive” (planning constraint / earlier lesson learning)  
- “short demo” (L2 plan already asked for a demo in the artifact)  
- “pair work” (not in the short message; already in profile)

Should go to **wiki / ingest**, not preference ledger:

- redox→ochem unit transition, open loops, misconceptions  
- dated student observations → student pages; summaries later via Student Memory queue  

### 4.3 Prompt→ledger mismatch summary

| Teacher intent | What happened |
|---|---|
| 1–2 standing style rules across a few chats | 13 fast-lane rows; 8 explicit Sweep preference cards |
| Quote as grounding | Whole-message quote reused as passport for unrelated contents |
| “always 5 min review” | Correctly captured — and also duplicated / surrounded by junk FL rows |
| Lesson observations & student notes | Partly inferred (good) + student summary cards (by design) |
| Silence default in policy | Violated hard on session `40510c49` (7 staged in one turn) |

---

## 5. Current agent prompts / tool instructions (as of this analysis)

### 5.1 `DURABLE_MEMORY_CANDIDATE_POLICY`

File: `backend/app/teacher_agent/prompts.py`  
Injected via `prompt_assembly.py` into plan / ingest / discuss.

**Already says the right things (and still got violated):**

- Call `remember(...)` for durable standing instructions.  
- “Most turns produce NO memory candidates. Silence is the normal outcome.”  
- Ground in teacher words; never memorialize agent-generated plan text.  
- SAVE vs SKIP lists (standing vs one-off).  
- Target routing + overlap examples (including **call remember twice** for dual-purpose facts).  
- `speech_act`: `conduct_request` / `store_request` / `observation`.  
- Quote must be verbatim; backend verifies.  
- Observations → weak/inferred, not remember.

**Ways the policy may have contributed to over-capture:**

1. **Overlap rules encourage multiple remembers** (“call remember twice…”) — correct for true dual-purpose facts; easy to over-generalize into atomization.  
2. **SAVE list includes broad triggers** (“durable preferences…”, “repeated class-learning patterns”) without a hard numeric cap.  
3. **No explicit “content must restate the quote only”** rule — quote provenance is required, entailment is not.  
4. **Ambiguous examples are long and teach splitting** more than silence.  
5. Policy cannot override the typed-state repair path that stamps whole-message preference evidence.

### 5.2 `remember(...)` tool docstring

File: `backend/app/teacher_agent/tools.py` — `create_remember_tool`

Key instructions to the model:

- Call when teacher gives a standing preference / behavior rule not bounded to this document.  
- Do **not** call for one-off plan/diary tasks or “what happened in class.”  
- Args: `target`, `content` (concise own words), `speech_act`, `quote` (verbatim), `routing_reason`.  
- Includes the same dual-target overlap examples as the policy.  
- “Nothing is written to memory now — it goes to the teacher's review.”

**Gap vs empirical failure:** docstring never says “at most N calls per message” or “reject content that adds facts not present in quote.”

### 5.3 Backend validation vs what the prompts promise

| Promise in prompt | Code reality (`memory_capture.py`) |
|---|---|
| Verbatim quote required | Yes — `validate_remember_call` substring check |
| Content grounded in teacher words | **Only via quote presence**, not content↔quote match |
| speech_act distinguishes conduct/store/observation | Model-supplied; fast lane can still open via **message markers** (`always`, …) for profile targets |
| Silence is normal | **Not enforced** (no per-turn cap) |
| Observations shouldn’t be remembered | Partly — discipline can downgrade; smoking-gun rows were still `teacher_explicit`/`fast_lane` |

---

## 6. Prompt vs ledger vs Sweep — one diagram

```text
Teacher short message
  "pchem solubility… + always 5 min review"
        │
        ▼
remember() × many  +  typed-state preference repair
        │
        ├─ quote = ENTIRE message (passport)
        ├─ contents = 5‑min review + pchem + visual + hybridization + demo + pair work
        └─ markers ("always") ⇒ act_ok for profiles
        │
        ▼
discipline_memory_candidates → fast_lane=True (13/16 rows overall)
        │
        ▼
insert_with_folding → only pair-work near-dup became already_covered
        │
        ▼
memory_gate → explicit clusters immediately eligible
        │
        ▼
Memory Sweep UI
  Teacher/Copilot Preferences: 8 cards, basis=explicit  ← looks like "I asked for all of these"
  Student Memory: 6 summary cards, basis=inferred       ← separate wiki rollup path
```

---

## 7. Acceptance goldens derived from this evidence

Use these as V4 offline tests (promote into fixtures):

**G1 — Smoking-gun plan message**  
Input: the pchem + always-5-min message alone.  
Expect: ≤2 fast-lane accepts (5-min review; optional single solubility/pchem scoped note).  
Expect: **0** accepts for visual/spatial, hybridization, demo, pair-work from that quote alone.

**G2 — Lesson result preference paragraph**  
Input: L1 “Possible teacher preference update” orbital sentence.  
Expect: 1 fast-lane `copilot_profile` avoid-abstract-orbitals.  
Expect: teaching-pattern observation not fast-laned (inferred or skip).

**G3 — Lesson result phenomenon-first paragraph**  
Input: L2 preference paragraph.  
Expect: 1 fast-lane phenomenon-first conduct/store.  

**G4 — Student notes in ingest**  
Expect: no `teacher_profile` fast-lane from student bullets; student summary may appear later in Student Memory queue (out of scope for preference admission tests).

**G5 — Prompt regression**  
Economy + production profiles: G1 must not reintroduce 7 FL rows; G2/G3 must not under-emit to zero.

---

## 8. Implications for V4 (tied to brainstorm changes)

| Evidence finding | Maps to brainstorm change |
|---|---|
| Same whole-message quote → many unrelated contents | **A** claim↔quote grounding |
| `always` in message + profile targets → FL even for junk | **B** require real `speech_act`; no marker override |
| 7 staged in one turn | **C** per-turn cap |
| Only pair-work folded; others became new FL clusters | **D** same-quote / merge-first |
| Policy already said silence; still flooded | **E** prompt tighten is secondary; code first |
| Student cards confused the narrative | Document separately; don’t “fix” by deleting Student Memory queue |
| Typed-state “Teacher explicitly framed…” suffix on bad rows | Revisit/disable `durable_preference_candidates_from_state_values` under same gates |

---

## 9. Pointers back to code/docs

- Capture policy: `backend/app/teacher_agent/prompts.py` (`DURABLE_MEMORY_CANDIDATE_POLICY`)  
- Tool: `backend/app/teacher_agent/tools.py` (`remember`)  
- Gates: `backend/app/teacher_agent/memory_capture.py` (`validate_remember_call`, `discipline_memory_candidates`)  
- Folding: `backend/app/services/memory_candidate_ledger.py` (`insert_with_folding`)  
- Promotion: `backend/app/services/memory_gate.py` (`gate_clusters`)  
- Contracts: `docs/agent_contracts.md` (memory vs wiki write separation)  
- Prior V3 beta card-wall story: `docs/mem_v3/design.md` §1  

---

*End of empirical inputs. Decision narrative continues in `brainstorm.md`.*
