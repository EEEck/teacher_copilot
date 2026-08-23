# A2 Task 5 — Reviewed Chemie 8/9 Seed Files

> Promoted from `.superpowers/sdd/2026-08-18-course-network-foundation/task-5-brief.md` on 2026-08-22. Completed; retained as the task-level contract.

## Goal and files

Provide route-specific reviewed Chemie Grade 8 and 9 course-network seeds:

```text
backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/08/course_network_seed.json
backend/teacher_wiki/wiki/subjects/chemie/teaching_frameworks/09/course_network_seed.json
backend/app/course_network/seeds.py
backend/tests/test_course_network_seeds.py
```

`load_seed_for_class(wiki, class_id)` rebinds the requested class ID, starts at
revision 1, and marks every node `proposed`. Route loading must be schema-driven
rather than hardcoded to the Grade 8 route.

## Content requirements

Grade 8 is the first acceptance route. It has at least 12 nodes, curriculum
references on every node, and only `builds_on` / `related_to` relationships.
It reflects the teacher's Miro-aligned spine, including Massenerhaltung,
Reaktionsgleichungen, Energieprofile, Aktivierungsenergie, Katalyse,
Avogadro-Hypothese, Stoffmenge, molare Masse/molaren Volumen, and
Stöchiometrie.

Every Grade 8 reference points to an actual
`by-lehrplanplus-chemie-8-ntg` section. The Miro screenshot alone is never a
source. Grade 9 follows the same canonical schema.

## Boundaries and verification

Only seed data, loader, and tests belong in this task. It changes neither APIs
nor adoption/LLM behavior, frontend, material ingestion, planner context, or
class provisioning. The two seed files are the explicit exception to the
baseline-wiki mutation rule.

The completed verification covered route/provenance, trusted sources, and
subject framework profiles, with scoped Ruff/format and diff checks.
