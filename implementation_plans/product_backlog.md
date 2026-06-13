# KlassenPilot Product Backlog

Living backlog for post-MVP releases. **v1** is the current shipped prototype
(see [`README.md`](../README.md) workflows).

Behavior contracts stay in [`docs/agent_contracts.md`](../docs/agent_contracts.md).
This file is product direction only - not an implementation spec. Product
vision and scope live in [`docs/product_vision.md`](../docs/product_vision.md).

---

## v1 (shipped)

- Class landing â†’ class home with timeline and memory snapshot
- **Update memory** â€” chat + diary draft â†’ teacher-approved wiki commit
- **Create lesson plan** â€” chat + plan draft, read-only wiki during planning
- Karpathy-style compiled wiki; unified `ArtifactSessionWorkspace` UI; compact class memory pages and deterministic wiki pathfinding
- In-memory sessions (draft survives refresh; server chat history does not)

---

## v1.1 â€” Teacher workflows

Primary source: [`README.md`](../README.md) â€œv1.1 (planned)â€ plus refactor follow-ons.

| Item | Notes |
|------|--------|
| **Test / exam generation** | New `ArtifactSpec` (seams exist in `artifact_spec.py`). Generate tests from taught sequence, misconceptions, and assessment readiness. |
| **Chat-driven wiki personalization** | Teacher edits `class_config.md` custom sections via memory chat; persisted through approved commit. Current implementation also includes compact class memory pages and deterministic query packs for planning and ingest. |
| **Student report artifact** | Optional second artifact type using existing session/commit patterns. |
| **Evidence / source panel (optional)** | Inline citations today; deferred API metadata for a UI source panel ([`docs/agent_contracts.md`](../docs/agent_contracts.md)). |
| **Wiki health check / lint** | `LINT_SYSTEM` prompt exists; expose as a bounded operator action, not silent background mutation. |
| **Lightweight plan review** | Post-generation sanity pass after browsing behavior is stable ([`docs/agent_architecture.md`](../docs/agent_architecture.md)). |
| **Playwright E2E** | Deferred in refactor; add smoke paths for ingest commit and plan save. |

**Not v1.1:** Postgres, multi-user accounts, Docling ingestion, grading.

---

## v1.2 â€” Deploy and reliability

Primary source: [`README.md`](../README.md) â€œv1.2 (planned)â€.

| Item | Notes |
|------|--------|
| **Caddy reverse proxy (Docker Option B)** | Single entry port, same-origin `/api`, SSE-friendly. |
| **Lean production images** | Next.js `standalone`, multi-stage slim Dockerfiles (non-dev CMD). |
| **`compose.prod.yaml`** | Production profile without bind mounts. |
| **Session persistence (optional)** | SQLite or similar when multi-worker or durable server-side chat history is needed. |
| **Generalized agent debug assemblies** | Extend the artifact prompt-assembly/debug pattern to one-shot/helper agents (`compile_diary`, `plan_lesson`, `lint_wiki`, memory compact, profile proposal, future grader/resource tools). Each agent call should expose a reusable assembly object with workflow name, instructions/user input, context sections, source paths, output type, and safe debug summaries. Add SDK trace metadata/custom-span summaries for class id, workflow, session/job id, and section sizes; keep full prompt/context text only in local debug bundles behind `PLAN_TRACE_ENABLED`. |
| **Typed index / search improvements** | If deterministic wiki retrieval reaches measurable limits ([`docs/agent_architecture.md`](../docs/agent_architecture.md)). |
| **Trusted online source search (optional)** | Add a bounded web-search/read tool for Wikipedia, PhET, official curriculum/news, and other approved sources; keep class wiki retrieval as the default memory path. |

---

## v1.3 â€” Proactive copilot (memo)

**Goal:** Shift from â€œpick a workflowâ€ to â€œthe copilot already looked.â€ Inspired by
**OpenClaw** (heartbeat/cron, startup brief, human-in-the-loop tool policy),
**Hermes** (persistent memory, scheduled check-ins, goal-style multi-step work), and
**Google Jules** (suggested tasks queue, plan-then-approve, check off â†’ next task).

### Product feel (voice examples)

On landing or class home, the teacher should see short, evidence-backed lines like:

- â€œI checked your last three lessons.â€
- â€œI noticed this open loop from Tuesday.â€
- â€œYour wiki has sparse memory for this class, so Iâ€™ll ask one question.â€
- â€œI found a good PhET simulation and a Wikipedia explanation; here is how I would adapt them.â€
- â€œAfter todayâ€™s update, I recommend updating timeline, misconceptions, and one student note. Here is the diff.â€
- â€œI found two stale open loops; should I close them?â€

UX pattern (Jules-like): a **small task stack** â€” complete or dismiss one suggestion,
surface the next. Not a full project-management board.

### Scope (high level)

1. **Briefing pass (read-only)** â€” On app/class entry, fast model + wiki tools compile a
   `ClassBrief`: recent lessons, open loops, sparse areas, stale items, next calendar gap.
   No writes; cache per class with TTL (OpenClaw â€œheartbeatâ€ idiom, teacher-scoped).

2. **Honcho-style copilot memory (local, class-scoped)** â€” Add a bounded profile layer
   alongside the wiki that answers: â€œWhat should the copilot know about how this teacher
   and this class work?â€ Store compact teacher preferences, recurring goals,
   communication style, class learning profile, planning patterns that worked, and
   â€œavoid/watchâ€ rules. Prefer a local markdown implementation first
   (`wiki/classes/{id}/memory/copilot_profile.md`) rather than integrating the external
   Honcho service.

3. **Suggested tasks API + UI** â€” Structured cards: `{ id, kind, title, rationale, evidence_paths, action_href, priority }`.
   Kinds: `log_memory`, `plan_lesson`, `close_loop`, `review_commit`, `fill_gap`, `external_resource`.
   Dismiss / done states stored locally or in lightweight backend store.

4. **Resource suggestions (bounded)** â€” Optional trusted-source lookup for PhET,
   Wikipedia, official sources, news, etc.; output is **adaptation notes + links**,
   never auto-inserted into wiki.

5. **Post-commit follow-ups** â€” After ingest approve, enqueue 1â€“3 concrete next tasks
   (timeline, misconceptions, student note) with diff preview â€” extends current HITL commit UX.

6. **Stale-loop hygiene** â€” Detect open loops older than N weeks; suggest close or
   re-open in plan chat (teacher confirms).

### Honcho-style memory notes

Useful Hermes/Honcho concepts to adapt locally:

- `profile`: a compact teacher/class/copilot profile injected into base context.
- `conclusions`: small durable facts such as â€œpeer checking improves balancing accuracy
  in this classâ€ or â€œteacher prefers concise 45-minute plans.â€
- `search`: lookup over compact personal/class memory before falling back to broad wiki
  browsing.
- `context`: a small memory packet for plan/update workflows.
- `reasoning`: occasional LLM synthesis over compact memory, used sparingly for questions
  like â€œwhat has worked for this class before?â€

Do not port Hermesâ€™ provider/plugin machinery initially. Keep the LLM synthesis separate
from deterministic persistence: the model may propose profile updates, but backend code
validates class scope, size limits, and allowed paths before writing.

### Non-goals for v1.3

- Always-on messaging gateway (WhatsApp/Telegram) â€” out of product scope.
- Autonomous wiki writes â€” all mutations stay teacher-approved ([`AGENTS.md`](../AGENTS.md)).
- AutoSci graph, multi-agent review, or broad agent infrastructure.
- Hermes-style self-authored skills â€” prefer fixed task kinds + wiki evidence.
- External Honcho dependency in the first pass â€” use the pattern locally before adding
  another memory service.

### Success criterion

> A teacher opens the app, sees one accurate proactive sentence and one actionable
> task grounded in their wiki, completes it in â‰¤2 clicks, and gets a sensible next
> suggestion without starting a blank chat.

### Likely touchpoints

- Backend: briefing service, `GET /api/classes/{id}/brief`, `GET /api/classes/{id}/suggestions`
- Backend memory: local class profile helpers, compact-memory package builder, and an
  explicit compaction/update endpoint for `wiki/classes/{id}/memory/*.md`
- Frontend: extend [`frontend/src/app/page.tsx`](../frontend/src/app/page.tsx) and/or
  class home with `SuggestedTasks` component (reuse `Card`, checklist patterns)
- Wiki reads first: timeline, open_loops, course_state, snapshot, search, compact memory pages, and query packs; no autonomous writes

---

## Parking lot (unversioned)

Deferred contracts and older PRD ideas to revisit after v1.3 if teacher demand
is clear:

- Multiple classes polish, class calendar, lesson graph view
- Docling ingestion (PDF/DOCX/PPTX)
- Postgres + pgvector, object storage, user accounts
- Long-running jobs, memory approval queue, skill proposals
- Parent/admin communication drafts
- Grading: rubrics, answer ingestion, teacher-reviewed suggestions

