# Plan materials MO embed — browser / API E2E prompts

Exact teacher messages from the Chemie 9b plan chat (typos preserved).
Use after a textbook PDF is on the plan session (upload or seeded package).

## Setup

1. Class: `chemie_9b_2026_27`
2. Optional cleanup: delete lesson `2026-08-09` (and its promoted materials) so save can reuse the date.
3. Open Plan, discard any stale draft if you need a clean thread.
4. Attach textbook PDF (e.g. `backend/tests/fixtures/materials/chemie_10sg_pages_5_to_14.pdf`) **or** seed `mini_bonding_package` via API helper.

## Teacher messages (paste in order)

### Turn 1

```text
can you summarize the texbook content i have uploaded to help me decide how to plan the lesson? i want to focus on the core idea of bonding like molecualr disscoo curve etc, can you also port images from the textbook into the md file
```

### Turn 2

```text
lets focus on mo theory and also the dissociton curve lets use the images from the textbook, we have the rights to use for the classroom
```

## Acceptance

- Draft `plan_markdown` contains at least one `assets/img-…` markdown image.
- Preview image loads (`naturalWidth > 0`) via  
  `GET /api/classes/{classId}/plan/sessions/{sessionId}/materials/{materialId}/assets/{filename}`.
- Prefer textbook cutouts for MO / dissociation when present (not only “original” diagrams).

## Helpers

- API (seed + both turns): `python scripts/run_plan_materials_mo_e2e.py`
- Live golden (single-turn seed):  
  `RUN_LIVE_AGENT_EVALS=1 pytest tests/evals/test_klassenpilot_chat_live.py -k 9b_plan_materials_embed_mo_asset`
