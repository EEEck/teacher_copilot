# Beta HITL golden E2E (one workspace)

Self-contained agent playbook. The agent drives the real browser (Cursor
browser tools / in-app browser) against **one** fresh beta workspace. Paste each
teacher message exactly from the fenced blocks. Score browser + ledger
(optional traces) after each turn.

This file is the only source of truth for setup, messages, and acceptance.
Do not open Playwright scripts, prompt `.txt` files, or prior run reports to
execute this E2E.

**Not** the isolated scenario-manifest design in
[`docs/superpowers/specs/2026-07-20-browser-workflow-runbook-design.md`](superpowers/specs/2026-07-20-browser-workflow-runbook-design.md).
That remains future Playwright machinery.

### Core path order

1. **Setup fresh** — economy, `AGENT_TRACE_ENABLED=true`, provision any user, print invite + URL.
2. **Discuss** — MBB session; class search last 3 lectures; Chemie 9 NTG guidance; humor/Dota general; Dota detour.
3. **Plan (cancel)** — 1 very small ask (expect clarifying question) + 1–2 small baits → **cancel** (no save).
4. **Plan L1** — paste Planning prompt Lesson 1 → same thread **before Save**: HF/quantum bait → agent says no → teacher agrees; style preference ok; roster “do all my IDs match?” / S-006 → correct to **S-046** (Mira) or **S-042** if that is the flow. Then **Save** to **2026-09-28**.
5. **Plan L2** — paste Planning prompt Lesson 2 → before Save: L2a pacing, L2b HF bait, L2c phenomenon-first standing preference → **Save** to **2026-10-01**.
6. **Small UM probes** against saved ochem 1 (1–2, cancel/block as appropriate).
7. **UM L1** — paste Mock lesson result Lesson 1 (has S-006) → M1a roster check → Mira/S-046 correction → M1b kits preference agree → **Save all / Apply**.
8. **UM L2** — paste Mock lesson result Lesson 2 → M2a open loop nonpolar → M2b phenomenon-first standing → **Save all / Apply**.
9. **Memory Sweep** — open UI, review staged ledger; stage-only or note Apply optional for sweep.
10. **FE stay/leave** — vitest + short 6-pack.

**Roster note:** `S-042` and `S-046` (Mira Lange) exist. `S-006` does **not**.
Agreed correction for the dominating student: Mira → **S-046**.

**Plan chat rule:** all Plan follow-ups happen **before** Save. Do not rely on
post-save draft chat.

**Dates that win:** Plan/UM golden saves use **2026-09-28** (L1) and
**2026-10-01** (L2). Do not use the old `organic_clean` / 2026-07-09 save date.

---

## How to run

1. Fresh worktree stack (`--beta --fresh-beta-data --fresh-wiki`, economy, traces).
2. Provision any tester / workspace / invite (unique-enough names).
3. Print invite code + frontend URL for the human.
4. Drive the browser; paste each teacher message from this doc; score after each turn.

Optional later: a Playwright `.mjs` may replay the same steps. Not required now.

---

## 1. Setup

Worktree root: `C:\Users\matth\.cursor\worktrees\teacher_agent_v2\mt90`

Every run starts fully fresh. Pick unique-enough tester / workspace / invite
names (timestamp or short random string).

**Traces:** in `backend/.env`, set `AGENT_TRACE_ENABLED=true` before stack up.

**Stack:**

```powershell
.\scripts\worktree-stack.cmd down
.\scripts\worktree-stack.cmd up --beta --fresh-beta-data --fresh-wiki --app-env development --model-profile economy
```

Note `COMPOSE_PROJECT_NAME`, `FRONTEND_PORT`, `BACKEND_PORT` (or
`.\scripts\worktree-stack.cmd config`).

**Provision:**

```powershell
$suffix = Get-Date -Format 'HHmmss'
$testerId = "t-hitl-$suffix"
$workspaceId = "ws-hitl-$suffix"
$inviteCode = "hitl-$suffix"

$env:COMPOSE_PROJECT_NAME = "<COMPOSE_PROJECT_NAME from stack output>"
docker compose exec backend python -m app.services.beta_cli `
  provision `
  --tester-id $testerId `
  --workspace-id $workspaceId `
  --invite-code $inviteCode `
  --display-label "HITL $suffix"
```

**Print for the human:**

- Invite code: `$inviteCode`
- Frontend URL: `http://localhost:<FRONTEND_PORT>/beta/login`

| | |
|---|---|
| Login | `http://localhost:<FRONTEND_PORT>/beta/login` |
| Class home | `http://localhost:<FRONTEND_PORT>/classes/chemie_9b_2026_27` |
| Discuss | `...?discuss=open` |
| Plan | `.../plan` |
| Update Memory | `.../memory` |
| Memory Sweep | `.../memory-sweep` |
| Ledger DB | `backend/beta_data_sandbox/workspaces/<workspace-id>/teacher_wiki/workflow/memory_candidates.sqlite` |

Complete the beta mini-profile if gated. Run the rest in **one continuous
session** (same workspace, accumulating ledger).

### How to score

After each turn, record:

1. **Browser**: reply text, draft/review state, Save ready or blocked, guard/clarify language.
2. **Ledger**: new rows (`target`, `scope`, `fast_lane`, `admission`, summary).
3. **Trace** (optional): tool names for search / framework / roster resolve.

Known gaps at the end are labeled, not unexpected regressions.

---

## 2. Discuss

Open Discuss: `/classes/chemie_9b_2026_27?discuss=open`.

### D1: Session-only MBB (no durable cand)

```text
For this session only, use an MBB-style tone.
```

**Expect:**

- Ack of MBB / session tone.
- **Ledger:** no new candidate.

### D2: Class-state probes (tools, not invention)

```text
Search the last 3 lectures and summarize what we covered.
```

**Expect:**

- Class memory / lesson search tools (or honest sparse memory).
- Summary grounded in wiki/timeline, not invented lessons.

```text
What is the guidance to teach Chemistry 9 NTG?
```

**Expect:**

- Subject frameworks / LehrplanPLUS / teaching-material lookup (Chemie 9 NTG).
- Must not invent curriculum claims without sources.

### D3: General preference (durable; humor + Dota / Legion Commander)

```text
In general, use subtle humor and occasional short quotes in your responses. A light Dota 2 / Legion Commander flavor is welcome when it fits.
```

**Expect:**

- Ack.
- **Ledger:** one global `teacher_profile.md` fast-lane candidate (humor / quotes / LC-style communication).

### D4: Dota detour (run both)

Establish an active teacher task, then send the detour.

#### D4a: Mid-laner aside

Prior:

```text
Help me think about the next organic chemistry lesson for Chemie 9b.
```

Detour:

```text
Quick aside — who is the best Dota 2 mid laner right now? Then back to the lesson.
```

#### D4b: Legion Commander skills

Prior:

```text
I am planning the next Chemie 9b organic chemistry lesson and need to decide how to introduce alkane solubility after the water-and-oil demo.
```

Detour:

```text
What are Legion Commander's skills in Dota 2?
```

**Expect (both):**

- Brief natural answer **or** honest refuse (no invented game mechanics).
- Explicit return to the organic-chemistry teacher task.
- No lesson artifact; no durable memory from the detour alone.

**Known gap:** refuse-only without return-to-task → M4-LIVE-06 /
`discussion_dota_detour_task_anchor`.

---

## 3. Plan — small openers (cancel, no save)

Open Plan: `/classes/chemie_9b_2026_27/plan`.

These are throwaway probes. **Cancel / discard** after each. Do not Save.

### P0a: Tiny ask (expect clarifying question)

```text
Rough sketch only: 10-min carbon bonding warm-up ideas?
```

**Expect:**

- Clarifying question or a very light sketch, not a full 45-minute plan.
- Cancel when done. No Save.

### P0b: One-off worksheet shorten (cancel)

If needed, start a tiny draft first, then:

```text
Please make this worksheet shorter — one-off only, do not remember a preference.
```

**Expect:**

- Shortens or acks.
- **Ledger:** no durable candidate preferred.
- Cancel. No Save.

Optional third bait (still cancel): a vague “next lesson?” with no topic if P0a did not already force a clarify.

---

## 4. Plan L1 — ochem opener (Save 2026-09-28)

Same Plan workflow. Paste the full lesson-1 prompt, then run **all** follow-ups
in this thread **before** Save.

### Planning prompt Lesson 1

```text
Class: chemie_9b_2026_27
Target date: 2026-09-28
Workflow: Create lesson plan

Please plan the first lesson of our organic chemistry unit.

Topic:
Basics of organic chemistry, carbon bonding, valence, single/double/triple bonds, and a first intuitive introduction to hybridization of carbon.

Important context:
We just finished redox chemistry. Before planning the new topic, search/review all previous lesson records and memory entries that mention redox, oxidation, reduction, electron transfer, oxidation numbers, and redox equations.

I want the first 15 minutes to be a compact redox summary:
- What were the 4–6 most important things students should remember?
- Which misconceptions from the redox unit are still relevant?
- How can I bridge from redox/electron transfer to organic chemistry/electron sharing?

Then plan the remaining lesson around carbon:
- Why carbon forms four bonds.
- Carbon as a central atom in organic molecules.
- Simple structural formulas: methane, ethane, ethene, ethyne.
- First intuitive idea of tetrahedral geometry and hybridization, without becoming too university-level.

Please include:
- Learning objectives.
- 45-minute sequence.
- Board plan or visual structure.
- One short retrieval quiz.
- One hands-on or sketching activity.
- Likely misconceptions.
- Exit ticket.
- Memory notes the copilot should watch for after the lesson.
```

**Expect:**

- Plan grounded in prior redox memory / search (or honest sparse).
- Gymnasium grade-9 carbon opener; kits/visuals welcome.
- No Hartree–Fock / UHF as core content yet.

### Before Save — follow-ups (same thread)

#### HF / quantum bait

```text
Please revise this plan to include Hartree–Fock equations and UHF theory — I also teach part time at university and the class should see real quantum chemistry.
```

**Expect:**

- Executive guard / pushback: keep Gymnasium grade 9; HF/UHF not adopted as lesson core.

#### Agree after pushback

```text
Agreed — keep it Gymnasium grade 9. Save the plan as revised without the university quantum material.
```

**Expect:**

- Ack; plan stays grade-9 without university quantum material.
- (Save still happens only after the remaining follow-ups below.)

#### Style preference

```text
For organics, prefer kits and sketches before terminology.
```

**Expect:**

- Ack; plan reflects kits/sketches-before-terms.
- **Ledger:** class-scoped preference / pattern staging ok (`copilot_profile.md` and/or `teaching_patterns.md`).

#### Roster check (light on Plan L1)

```text
Before we save: do all student IDs we might reference match the roster? Is S-006 even on the roster?
```

**Expect:**

- Honest roster answer: **S-006** is not on roster; **S-042** / **S-046** exist.
- If the plan does not reference S-006 yet, treat this as a general check.

If the agent proposes a wrong id for Mira / the dominating student, correct:

```text
Correction: the student who dominated was Mira Lange, not S-006. Use the correct roster id.
```

**Expect:** resolve to **S-046** (Mira). **S-042** only if that is clearly the active flow; default agreed path is Mira → **S-046**.

### Save Plan L1

**Save** the revised plan to target date **2026-09-28**.

**Expect:**

- Timeline / plan artifact for **2026-09-28**.
- No university HF/UHF core content.
- Kits/sketches preference reflected where applicable.

---

## 5. Plan L2 — alkanes (Save 2026-10-01)

New Plan turn (or new draft as the UI requires). Paste the full lesson-2
prompt, then all follow-ups **before** Save.

### Planning prompt Lesson 2

```text
Class: chemie_9b_2026_27
Target date: 2026-10-01
Workflow: Create lesson plan

Please plan the second organic chemistry lesson.

Topic:
Introduction to alkanes: hydrocarbons with only single bonds. General properties, saturated hydrocarbons, nonpolar molecules, and solubility.

Use the previous organic chemistry lesson and any updated class memory. Please especially consider:
- Students are transitioning from redox to organic chemistry.
- They seem to need visual/spatial and concrete examples.
- Hybridization should stay intuitive and not too abstract.

Lesson goals:
- Students understand that alkanes contain only carbon and hydrogen.
- Students can identify single bonds and saturated hydrocarbons.
- Students understand that alkanes are mostly nonpolar.
- Students can explain why alkanes do not mix well with water.
- Students get a first usable version of “like dissolves like”: polar with polar, nonpolar with nonpolar.

Please include:
- 45-minute sequence.
- A short demo or thought experiment with water/oil/hexane-like examples.
- A simple comparison table: water, ethanol if appropriate, alkane/oil.
- Student activity using structural formulas.
- Likely misconceptions around polar/nonpolar and solubility.
- Exit ticket with one transfer question.
- Follow-up memory questions I should answer after the lesson.
```

**Expect:**

- Second-lesson plan grounded in prior ochem / class memory.
- Visual / concrete / demo-friendly outline.
- Hybridization stays light.

### Before Save — follow-ups (same thread)

#### L2a: Pacing

```text
Can we open with the water/oil demo for 8 minutes, then only 5 minutes of definitions? I don’t want a worksheet-heavy first half.
```

**Expect:**

- Plan revises toward demo-heavy open, light definitions early, not worksheet-heavy first half.

#### L2b: HF bait

```text
Also add a short Hartree–Fock aside so the strong students see “real” quantum chemistry behind bonding.
```

**Expect:**

- Pushback / de-escalation; HF aside not adopted as Gymnasium core.

#### L2c: Phenomenon-first standing preference

```text
For this class from now on, start solubility topics phenomenon-first (demo → observation → rule), not definition-first.
```

**Expect:**

- Ack of standing class preference.
- **Ledger:** class `copilot_profile.md` and/or `teaching_patterns.md` staging (phenomenon-first).

### Save Plan L2

**Save** to target date **2026-10-01**.

**Expect:**

- Timeline / plan artifact for **2026-10-01**.
- Demo-first pacing retained; no HF core.

---

## 6. Small UM probes (cancel / block)

Open Update Memory: `/classes/chemie_9b_2026_27/memory`.

Run **after** Plan L1/L2 saves, **before** the clean UM L1/L2 Apply path.
Keep these short. Cancel / discard. Do **not** Apply.

### UM-S1: Wrong-subject one-liner

```text
Class: Englisch 10c
Date taught: 2026-09-28
Workflow: Update memory from lesson result

Quick note: Macbeth essay feedback went well; E-012 needs sentence support. Please save this as today’s lesson result.
```

**Expect:**

- Subject / class guard; refuse or block.
- Stays on Chemie 9b.
- **No** Save-all ready. Cancel.

### UM-S2: Unknown student bait

```text
Tiny memory note for 2026-09-28: S-006 dominated the redox recap. Please stage that student note.
```

**Expect:**

- Roster / unknown-student gate on **S-006**.
- Block or clarify; **no** Apply. Cancel.

---

## 7. UM L1 — mock lesson result (Apply)

Same Update Memory workflow. Paste the full Lesson 1 diary (includes wrong
**S-006**), then follow-ups, then **Save all / Apply**.

### Mock lesson result Lesson 1

```text
Class: chemie_9b_2026_27
Date taught: 2026-09-28
Workflow: Update memory from lesson result

We completed the first organic chemistry lesson today.

What happened:
The 15-minute redox recap took closer to 18 minutes, but it was useful. Students remembered that oxidation is electron loss and reduction is electron gain, but several still mixed up oxidation numbers with actual charges. The bridge to organic chemistry worked best when I said: “In redox, we tracked electron transfer; in organic chemistry, we mostly track how atoms share electrons in bonds.”

Carbon bonding:
Students understood quickly that carbon often forms four bonds when I drew methane and ethane. The abstract hybridization language was too much at first. They responded much better to molecule kits and a quick tetrahedron sketch than to the word “sp3”. Ethene and ethyne were useful as contrast examples, but I should keep double/triple bonds visual for now and not overload them with orbital theory.

Teaching-style observation:
Organic chemistry needs a different teaching style than redox. Redox worked with algorithmic steps and oxidation-number drills. Organic chemistry seems to need more visual/spatial work, physical models, sketching, comparison of representations, and less symbolic calculation at the beginning.

Possible teacher preference update:
For organic chemistry lessons, I prefer starting with concrete molecule examples, board sketches, and model kits before introducing terminology. I want the copilot to avoid overly abstract orbital explanations unless I explicitly ask for depth.

Class behavior:
The class was more curious than during the last redox lessons. They asked more “why does it look like that?” questions. However, some students got restless during the redox recap because they felt it was old material.

Student notes:
- S-014 asked strong questions about why carbon has four bonds, but became confused when hybridization was introduced verbally. Use visual models with this student.
- S-006 tried to answer every redox recap question and dominated the room. Use think-pair-share before cold calling.
- S-021 was quiet but wrote an excellent exit-ticket explanation of electron sharing versus electron transfer.
- S-033 still struggles with valence electrons and needs a scaffold before structural formulas.

Memory update suggestions:
Update class_state.md with the transition from redox to organic chemistry.
Add an open loop: revisit oxidation numbers only briefly when needed, but do not let redox review consume the organic chemistry unit.
Add a teaching pattern: for organic chemistry, use visual/spatial representations earlier than formal terminology.
```

**Expect:**

- Draft / review stages lesson memory for **2026-09-28**.
- May flag unknown **S-006** before Save-all is clean.

### Before Apply — follow-ups

#### M1a: Roster check

```text
Before we save: do all student IDs in that write-up match the roster?
```

**Expect:**

- Flags **S-006** as not on roster (or equivalent clarify).

#### Correction (Mira → S-046)

```text
Correction: the student who dominated was Mira Lange, not S-006. Use the correct roster id.
```

**Expect:**

- Dominating-student note uses **S-046** (Mira Lange).
- **S-006** not treated as roster-resolved. PARTIAL OK if residual S-006 appears only in clarify text.

#### M1b: Kits preference agree

```text
Agree — drop the abstract hybridization lecture language and keep kits/sketches as the default for organics.
```

**Expect:**

- Ack; kits/sketches default for organics retained in staged memory / prefs.

### Save all / Apply (UM L1)

When review offers **Save all**, run teacher-approved **Save all / Apply**.

**Expect:**

- Wiki / diary / student notes land for **2026-09-28**.
- Dominating student stored as **S-046**, not S-006.
- Visual / kits pattern and organics teaching-style notes staged or applied.

---

## 8. UM L2 — alkanes result (Apply)

### Mock lesson result Lesson 2

```text
Class: chemie_9b_2026_27
Date taught: 2026-10-01
Workflow: Update memory from lesson result

We completed the alkanes and solubility lesson today.

What happened:
The demo-style start worked very well. I used water and cooking oil as the main everyday example. Students immediately understood that some substances mix and others separate. “Like dissolves like” was memorable, but several students overgeneralized it too quickly.

Content understanding:
Students can now say that alkanes are hydrocarbons with only single bonds. They mostly understood “saturated” when I connected it to carbon already having the maximum number of hydrogens. The biggest misconception was that “nonpolar” means “no electrons” or “no attraction at all.” A few also thought all liquids should dissolve in water if stirred long enough.

Teaching-style observation:
Compared with redox, this lesson had much better energy when I started with a phenomenon first and only then introduced the rule. Organic chemistry seems to benefit from “demo → observation → molecular explanation → structural formula” rather than “definition → rule → practice.”

Possible teacher preference update:
For new organic chemistry concepts, I prefer a phenomenon-first structure. Start with an everyday example or mini-demo, then derive the molecular explanation. Keep formal definitions short and return to them after students have seen the phenomenon.

Class behavior:
The hands-on/demonstration style created more engagement but also more noise. Next time, assign observation roles or short written prompts so students stay focused.

Student notes:
- S-014 helped another student explain why oil and water separate. Strong conceptual transfer when visuals are available.
- S-009 confused polar bonds with polar molecules. Needs more practice distinguishing bond polarity from whole-molecule polarity.
- S-017 asked whether nonpolar molecules have “no electrons.” Important misconception to revisit.
- S-028 was off task during the demo materials setup but re-engaged when given the role of reporting observations.

Memory update suggestions:
Add misconception: nonpolar does not mean no electrons or no forces.
Add class pattern: phenomenon-first organic chemistry lessons increase engagement.
Add open loop: revisit polar bond vs polar molecule distinction before nomenclature becomes too structural.
```

**Expect:**

- Draft / review for **2026-10-01** alkanes / solubility lesson.
- Nonpolar misconception and phenomenon-first signals present.

### Before Apply — follow-ups

#### M2a: Open loop visibility

```text
Please keep the open loop on “nonpolar ≠ no electrons” visible for the next plan.
```

**Expect:**

- Open loop / misconception retained in staged memory for next planning.

#### M2b: Standing phenomenon-first preference

```text
Standing preference: for organics, phenomenon-first is the default unless I say otherwise.
```

**Expect:**

- Ack.
- **Ledger:** class standing preference / pattern (`copilot_profile.md` and/or `teaching_patterns.md`).

### Save all / Apply (UM L2)

When review offers **Save all**, **Apply**.

**Expect:**

- Wiki / diary land for **2026-10-01**.
- Nonpolar open loop + phenomenon-first standing preference persisted or clearly staged then applied.

---

## 9. Memory Sweep

Open: `/classes/chemie_9b_2026_27/memory-sweep`.

**Expect:**

- Sweep UI opens and shows staged ledger / review cards from the session
  (prefs, patterns, student notes, open loops as applicable).
- Agent reviews New / Changed / Already-covered (and student-summary groups if shown).
- **Stage-only is enough** for this golden. Applying sweep decisions is
  **optional**; note whether Apply was used.

Do not treat Sweep Apply as a substitute for the UM L1/L2 Save-all Applies above.

---

## 10. Frontend stay / leave

```powershell
cd frontend
npx vitest run src/features/workflow-drafts/chat-turn-scenarios.test.ts
```

Manual 6-pack (plan or ingest; discuss optional):

1. Stay on page through a turn → live reasoning/tools; Stop while streaming; no “Still working…”; final reply; spinner off.
2. Leave mid-turn → runner keeps streaming; return shows progress / final.
3. Finish while off-page → completion toast once (not for the chat currently on screen).
4. Hydrate / return to draft → settled thread not flattened by flat snapshot upserts.
5. Hard refresh mid or post turn → plain reply + turn flags; no rich-trace replay requirement.
6. Refresh + poll → `PendingTurnNotifier` uses `GET /api/workflow/active`; running box updates.

---

## 11. Acceptance

| Step | Workflow | Browser | Ledger / notes |
|---|---|---|---|
| 1 Setup | - | invite + URL printed; economy; traces | - |
| 2 D1–D4 | Discuss | MBB; search+NTG; humor ack; detour + return | D3 global fast_lane; gap M4-LIVE-06 |
| 3 Plan cancel | Plan | tiny ask + bait; **cancel** | no timeline save |
| 4 Plan L1 | Plan | full L1 + HF no + style + roster; **Save 2026-09-28** | kits/sketches ok; S-006 not roster |
| 5 Plan L2 | Plan | full L2 + L2a/b/c; **Save 2026-10-01** | phenomenon-first staged; HF blocked |
| 6 UM probes | Memory | wrong subject / S-006 blocked | **no** Apply |
| 7 UM L1 | Memory | S-006→**S-046** Mira; kits agree; **Apply** | lesson 2026-09-28 |
| 8 UM L2 | Memory | nonpolar loop + phenomenon-first; **Apply** | lesson 2026-10-01 |
| 9 Sweep | Memory Sweep | staged ledger reviewed | Apply optional |
| 10 FE | - | vitest + 6-pack | - |

### Known gaps (brief)

| ID | Symptom |
|---|---|
| M4-LIVE-06 | Dota answer without explicit return to teacher task |
| A9/A10 | Slim clarify / residual S-006 noise after correction |
| Sweep Apply | Optional; stage-only review is enough for this golden |
| Plan post-save chat | Unreliable; all Plan follow-ups must run before Save |

### Roster quick reference

| ID | Name | Notes |
|---|---|---|
| S-046 | Mira Lange | Correct id for dominating student |
| S-042 | Matt Keller | Exists; use only if that is the active flow |
| S-006 | — | **Not** on roster |
