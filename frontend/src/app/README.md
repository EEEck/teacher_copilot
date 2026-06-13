# App Router Pages

Route files live here. Keep route components focused on data loading, page-level
state, and composing domain components.

## Main Routes

- `page.tsx` - landing/class selection.
- `classes/[classId]/page.tsx` - class home and memory/timeline entry point.
- `classes/[classId]/memory/page.tsx` - class memory overview.
- `classes/[classId]/lessons/[lessonDate]/page.tsx` - lesson detail.
- `classes/[classId]/plan/page.tsx` - lesson-planning artifact session.
- `classes/[classId]/wiki/view/page.tsx` - markdown wiki file viewer.

## Conventions

- Keep reusable UI in `../components/`.
- Keep API calls in `../lib/api.ts`.
- Preserve route params such as `classId` and `lessonDate` as the source of
  backend class/date scope.
