# Plan Context tab / session materials — browser HITL

Teacher-facing checks for the plan **Preview | Edit | Context** tab: remaining
PDFs as a set, Remove, class-memory toggles, and off-subject upload reject.
Drive the real browser against Chemie 9b. Paste nothing fancy — attach the
fixture PDFs and click the UI.

This is the materials Context playbook. The MO embed chat path stays in
[`plan_materials_mo_e2e_prompts.md`](plan_materials_mo_e2e_prompts.md). The
beta golden (Discuss → Plan L1/L2 → UM) stays in
[`docs/beta_hitl_golden_e2e.md`](../docs/beta_hitl_golden_e2e.md).

## When to run

After Context-tab, materials inventory, or subject-reject changes. Before
merge of that work.

## Stack

Local uvicorn + Next (ports from your worktree / `restart-dev`). Default HITL:

- Frontend: `http://localhost:3000/classes/chemie_9b_2026_27/plan`
- Backend: `http://localhost:8011`
- Wiki: sandbox (`WIKI_ROOT=backend/teacher_wiki_sandbox`) so seed wiki stays clean
- Backend process must be the **current** code (`class_core` on GET draft,
  `DELETE …/materials/{id}`, `PATCH …/context`). If those 404, restart uvicorn
  without a leftover `--reload` twin on 8011.

## Fixtures

| File | Use |
|---|---|
| `backend/tests/fixtures/materials/esl_textbook_sample_pages_9_to_11.pdf` | Off-subject ESL extract (English / home & family) |
| On-subject Chemie PDF (e.g. *Aufbau von Molekülen* extract) | Keep in session; do **not** live-OCR the 30 MB book in CI |

## Deterministic (CI, no live OCR)

```powershell
cd backend
.\.venv\Scripts\python -m pytest `
  tests\test_materials_plan_api.py `
  tests\test_materials_subject.py `
  tests\test_wiki_context_packs.py `
  tests\test_prompts.py `
  tests\test_wiki_tools.py -q

cd ..\frontend
npx vitest run `
  src/components/klassenpilot/plan-context-panel.test.ts `
  src/components/klassenpilot/markdown-editor-panel.test.ts
```

| Check | Test |
|---|---|
| Two on-subject PDFs both in TOC/prompt; DELETE one | `test_two_on_subject_pdfs_both_injected_then_delete_one` |
| Tight TOC cap never drops a later `material_id` | `test_materials_toc_keeps_both_ids_under_tight_char_cap` |
| ESL annotation on Chemie → 422, scratch deleted | `test_esl_pdf_rejected_on_chemie_class` |
| PATCH `excluded_core_keys` drops Planning brief from core text | `test_patch_context_excludes_planning_brief` |
| Subject alias / mismatch helpers | `tests/test_materials_subject.py` |
| Context tab categories + Preview/Edit/Context wiring | frontend vitest files above |

## Browser steps (Chemie 9b)

Discard the draft first if you need a clean thread. Composer tiles vanish after
Send; **Context** is the inventory.

### C1: Context tab layout

1. Open Plan. Right pane: **Preview | Edit | Context**. Diary must **not** have Context.
2. Open **Context**.

**Expect three groups, in order:**

1. **Uploaded materials** — Textbook then Personal (not mixed into wiki).
2. **Class memory** — switches (Top misconceptions, Recent lessons, Planning brief, Teaching patterns, Class copilot profile, Session summaries). Caption: tools can still read a page you turn off.
3. **Always in context** — Class identity, Teacher profile, Subject guidance, each locked **On** (no switch).

### C2: Two PDFs stay in context

1. Attach the ESL fixture (Textbook), wait for OCR, Send a short “summarize this pdf”.
2. Attach the Chemie extract, wait for OCR. Do **not** need another Send to list it.
3. Open **Context**.

**Expect:**

- Both titles under **Textbook**, each with **Remove**.
- Footer: **2 materials will be kept with this lesson on save.**
- Vague “this PDF” / “the upload” in chat covers **all remaining** uploads unless the teacher names one title or `material_id`.

### C3: Remove the mistaken PDF

1. **Remove** on the ESL / *It’s fun at home* row.

**Expect:**

- Only the Chemie title remains.
- Footer: **1 material will be kept…**
- Next “summarize this pdf” must not treat the ESL extract as still uploaded.

### C4: Class-memory toggle

1. Turn **Planning brief** off. Reload Context if needed.

**Expect:**

- Switch stays off after the PATCH settles.
- Other class-memory switches unchanged.
- Always-in-context rows still On / not clickable.

### C5: Live off-subject re-upload (Mistral)

Needs `MISTRAL_API_KEY`. Prefer a **new** attach of the ESL fixture after C3
(Chemie PDF still on the session).

**Expect:**

- Upload fails (**422**). Composer tile errors. Message like:
  `This PDF looks like English, not Chemie` (wording may use ESL / Englisch).
- Context inventory **unchanged** (Chemie PDF still there; ESL not added).
- Scratch for the rejected package is gone.

API helper (same assertion, no browser):

```powershell
.\backend\.venv\Scripts\python .\scripts\run_plan_context_materials_e2e.py
```

Opt-in pytest (TestClient + live Mistral, isolated scratch):

```powershell
cd backend
$env:RUN_LIVE_MISTRAL_OCR="1"
.\.venv\Scripts\python -m pytest tests\test_materials_ocr_live.py -q
```

## Agent gotcha

Cursor browser automation injects `data-cursor-ref` on links. Next.js dev may
show a hydration overlay that blocks clicks. Dismiss the overlay (or close the
**1 Issue** badge) before **Remove**. That mismatch is not an app regression.

## Acceptance

| Step | Pass |
|---|---|
| C1 | Preview/Edit/Context on plan only; three Context groups |
| C2 | Both PDFs listed; footer 2; set semantics in chat |
| C3 | Remove ESL; footer 1; Chemie remains |
| C4 | Planning brief off; locked always-on rows |
| C5 | Live ESL 422; inventory unchanged |
| CI | pytest + vitest commands above green |
| Skill | `test_materials_use_skill_treats_remaining_uploads_as_a_set` |
