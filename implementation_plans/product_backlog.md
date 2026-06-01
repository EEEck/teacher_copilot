# KlassenPilot Product Backlog

Living backlog for post-MVP releases. **v1** is the current shipped prototype (see
[`README.md`](../README.md) workflows and [`docs/REFACTOR_STATUS.md`](../docs/REFACTOR_STATUS.md)).

Behavior contracts stay in [`agent_contracts.md`](agent_contracts.md). This file is
product direction only — not an implementation spec.

---

## v1 (shipped)

- Class landing → class home with timeline and memory snapshot
- **Update memory** — chat + diary draft → teacher-approved wiki commit
- **Create lesson plan** — chat + plan draft, read-only wiki during planning
- Karpathy-style compiled wiki; unified `ArtifactSessionWorkspace` UI
- In-memory sessions (draft survives refresh; server chat history does not)

---

## v1.1 — Teacher workflows

Primary source: [`README.md`](../README.md) “v1.1 (planned)” plus refactor follow-ons.

| Item | Notes |
|------|--------|
| **Test / exam generation** | New `ArtifactSpec` (seams exist in `artifact_spec.py`). Lesson-to-exam workflow from [`initial_plan.md`](../initial_plan.md) Phase 3. |
| **Chat-driven wiki personalization** | Teacher edits `class_config.md` custom sections via memory chat; persisted through approved commit. |
| **Student report artifact** | Optional second artifact type using existing session/commit patterns. |
| **Evidence / source panel (optional)** | Inline citations today; deferred API metadata for a UI source panel ([`agent_contracts.md`](agent_contracts.md), [`teacher_wiki_browsing_plan.md`](teacher_wiki_browsing_plan.md)). |
| **Wiki health check / lint** | `LINT_SYSTEM` prompt exists; expose as a bounded operator action, not silent background mutation. |
| **Lightweight plan review** | Post-generation sanity pass after browsing behavior is stable ([`agent_design_plan.md`](agent_design_plan.md)). |
| **Playwright E2E** | Deferred in refactor; add smoke paths for ingest commit and plan save. |

**Not v1.1:** Postgres, multi-user accounts, Docling ingestion, grading — see [`initial_plan.md`](../initial_plan.md) Phases 2–4.

---

## v1.2 — Deploy and reliability

Primary source: [`README.md`](../README.md) “v1.2 (planned)”.

| Item | Notes |
|------|--------|
| **Caddy reverse proxy (Docker Option B)** | Single entry port, same-origin `/api`, SSE-friendly. |
| **Lean production images** | Next.js `standalone`, multi-stage slim Dockerfiles (non-dev CMD). |
| **`compose.prod.yaml`** | Production profile without bind mounts. |
| **Session persistence (optional)** | SQLite or similar when multi-worker or durable server-side chat history is needed ([`REFACTOR_STATUS.md`](../docs/REFACTOR_STATUS.md)). |
| **Typed index / search improvements** | If wiki size makes range/topic tools insufficient ([`agent_design_plan.md`](agent_design_plan.md)). |

---

## v1.3 — Proactive copilot (memo)

**Goal:** Shift from “pick a workflow” to “the copilot already looked.” Inspired by
**OpenClaw** (heartbeat/cron, startup brief, human-in-the-loop tool policy),
**Hermes** (persistent memory, scheduled check-ins, goal-style multi-step work), and
**Google Jules** (suggested tasks queue, plan-then-approve, check off → next task).

### Product feel (voice examples)

On landing or class home, the teacher should see short, evidence-backed lines like:

- “I checked your last three lessons.”
- “I noticed this open loop from Tuesday.”
- “Your wiki has sparse memory for this class, so I’ll ask one question.”
- “I found a good PhET simulation and a Wikipedia explanation; here is how I would adapt them.”
- “After today’s update, I recommend updating timeline, misconceptions, and one student note. Here is the diff.”
- “I found two stale open loops; should I close them?”

UX pattern (Jules-like): a **small task stack** — complete or dismiss one suggestion,
surface the next. Not a full project-management board.

### Scope (high level)

1. **Briefing pass (read-only)** — On app/class entry, fast model + wiki tools compile a
   `ClassBrief`: recent lessons, open loops, sparse areas, stale items, next calendar gap.
   No writes; cache per class with TTL (OpenClaw “heartbeat” idiom, teacher-scoped).

2. **Honcho-style copilot memory (local, class-scoped)** — Add a bounded profile layer
   alongside the wiki that answers: “What should the copilot know about how this teacher
   and this class work?” Store compact teacher preferences, recurring goals,
   communication style, class learning profile, planning patterns that worked, and
   “avoid/watch” rules. Prefer a local markdown implementation first
   (`wiki/classes/{id}/memory/copilot_profile.md`) rather than integrating the external
   Honcho service.

3. **Suggested tasks API + UI** — Structured cards: `{ id, kind, title, rationale, evidence_paths, action_href, priority }`.
   Kinds: `log_memory`, `plan_lesson`, `close_loop`, `review_commit`, `fill_gap`, `external_resource`.
   Dismiss / done states stored locally or in lightweight backend store.

4. **Resource suggestions (bounded)** — Optional web lookup for PhET, Wikipedia, etc.;
   output is **adaptation notes + links**, never auto-inserted into wiki.

5. **Post-commit follow-ups** — After ingest approve, enqueue 1–3 concrete next tasks
   (timeline, misconceptions, student note) with diff preview — extends current HITL commit UX.

6. **Stale-loop hygiene** — Detect open loops older than N weeks; suggest close or
   re-open in plan chat (teacher confirms).

### Honcho-style memory notes

Useful Hermes/Honcho concepts to adapt locally:

- `profile`: a compact teacher/class/copilot profile injected into base context.
- `conclusions`: small durable facts such as “peer checking improves balancing accuracy
  in this class” or “teacher prefers concise 45-minute plans.”
- `search`: lookup over compact personal/class memory before falling back to broad wiki
  browsing.
- `context`: a small memory packet for plan/update workflows.
- `reasoning`: occasional LLM synthesis over compact memory, used sparingly for questions
  like “what has worked for this class before?”

Do not port Hermes’ provider/plugin machinery initially. Keep the LLM synthesis separate
from deterministic persistence: the model may propose profile updates, but backend code
validates class scope, size limits, and allowed paths before writing.

### Non-goals for v1.3

- Always-on messaging gateway (WhatsApp/Telegram) — out of product scope.
- Autonomous wiki writes — all mutations stay teacher-approved ([`AGENTS.md`](../AGENTS.md)).
- AutoSci graph, multi-agent review, or broad agent infrastructure.
- Hermes-style self-authored skills — prefer fixed task kinds + wiki evidence.
- External Honcho dependency in the first pass — use the pattern locally before adding
  another memory service.

### Success criterion

> A teacher opens the app, sees one accurate proactive sentence and one actionable
> task grounded in their wiki, completes it in ≤2 clicks, and gets a sensible next
> suggestion without starting a blank chat.

### Likely touchpoints

- Backend: briefing service, `GET /api/classes/{id}/brief`, `GET /api/classes/{id}/suggestions`
- Backend memory: local class profile helpers, compact-memory package builder, and an
  explicit compaction/update endpoint for `wiki/classes/{id}/memory/*.md`
- Frontend: extend [`frontend/src/app/page.tsx`](../frontend/src/app/page.tsx) and/or
  class home with `SuggestedTasks` component (reuse `Card`, checklist patterns)
- Wiki reads first: timeline, open_loops, course_state, snapshot, search, compact memory
  pages; no autonomous writes

---

## Parking lot (unversioned)

From [`initial_plan.md`](../initial_plan.md) and deferred contracts — revisit after v1.3
if teacher demand is clear:

- Multiple classes polish, class calendar, lesson graph view
- Docling ingestion (PDF/DOCX/PPTX)
- Postgres + pgvector, object storage, user accounts
- Long-running jobs, memory approval queue, skill proposals
- Parent/admin communication drafts
- Grading: rubrics, answer ingestion, teacher-reviewed suggestions
