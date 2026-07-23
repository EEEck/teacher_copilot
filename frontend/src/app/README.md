# App Router Pages

Route files live here. Keep route components focused on data loading, page-level
state, and composing domain components.

## Main Routes

- `page.tsx` - marketing home (`HomeLanding`) plus quiet gray “Coming soon”
  class list from `GET /api/classes`.
- `beta/login/page.tsx` - invite-code beta login; backend sets the
  HTTP-only beta session cookie.
- `beta/feedback/page.tsx` - beta-only teacher feedback form
  (`POST /api/beta/feedback` → `beta.sqlite3`).
- `classes/[classId]/page.tsx` - class home and memory/timeline entry point.
  Surfaces a short Memory Sweep badge from the backend saved-review status.
- `classes/[classId]/memory/page.tsx` - update-memory artifact session. Reads
  optional `lessonDate`, `lessonTitle`, `intent`, and `targetKind` query params
  and sends them as a typed backend start hint. Bootstraps a workflow draft via
  `features/workflow-drafts/`.
- `classes/[classId]/memory-sweep/page.tsx` - Memory Sweep saved-review UI.
  Opens/resumes `POST/GET /memory/sweep/review`, appears in Running jobs while
  generating (`GET /api/workflow/active`), and uses Simple / Detailed view modes.
- `classes/[classId]/lessons/[lessonDate]/page.tsx` - lesson detail.
- `classes/[classId]/plan/page.tsx` - lesson-planning artifact session
  (same workflow-draft path as Update Memory).
- `classes/[classId]/wiki/view/page.tsx` - markdown wiki file viewer.
- `docs/page.tsx` and `docs/[slug]/page.tsx` - in-app beta docs.

## Conventions

- Keep reusable UI in `../components/`.
- Keep cross-route draft/job ownership in `../features/` and `../lib/`.
- Keep API calls in `../lib/api.ts`.
- Preserve route params such as `classId` and `lessonDate` as the source of
  backend class/date scope.
- Treat query params for Update Memory as hints only. The memory page should
  display backend `memory_state` so the teacher can see whether the target was
  confirmed or still needs confirmation.
- Memory Sweep pages follow the saved-review contract in
  `../../../docs/agent_contracts.md` (Memory Sweep) and `../../../docs/mem_v4/`.
