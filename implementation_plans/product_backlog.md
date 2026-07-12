# KlassenPilot Product Roadmap

Engineering-facing roadmap for post-MVP work. Product strategy, current product
state, north star, and prioritization principles live in
[`docs/pm_hub.md`](../docs/pm_hub.md). Behavior contracts stay in
[`docs/agent_contracts.md`](../docs/agent_contracts.md).

This file is not a detailed implementation spec. For each item, create a
focused implementation plan before making broad changes.

## Roadmap Rule

Prioritize work that increases weekly teacher time saved while preserving
teacher trust. Keep durable writes explicit and teacher-approved.

---

## v1 - Shipped Prototype: Prove The Core Memory Loop

**Theme:** Teach -> update memory -> plan next lesson.

**What it enables:** A teacher can log lessons into reviewed class memory and
create the next lesson plan from that memory.

Shipped:

- Class landing -> class home with timeline and memory snapshot.
- **Update memory**: chat + diary draft -> teacher-approved wiki commit.
- **Create lesson plan**: chat + plan draft -> save to a lesson date.
- **Beta tester mode**: invite-code login, workspace-scoped wiki copies, and
  local telemetry for app activity, visible conversations, draft snapshots, and
  approved wiki diffs.
- **Beta review tooling**: CLI Markdown reports over telemetry and wiki diffs,
  plus Memory Sweep review UX with card warnings, stepwise loading, clearer
  teacher-facing decisions, and seven-day deferral for uncertain signals.
- **Memory V3 backend and review loop**: explicit `remember(...)` capture,
  typed memory write/read contracts, ledger folding, promotion gate,
  single-call high-reasoning sweep, and the teacher-first Memory Sweep brief.
- **Model call-class routing**: production/economy profiles split chat,
  important consolidation, and utility calls; live agent evals default to the
  production profile unless the run explicitly compares models.
- Timeline/detail shortcuts for adding results to planned lessons or correcting
  taught lessons.
- Karpathy-style compiled wiki with compact class memory pages.
- Deterministic wiki pathfinding and class-scoped read tools.
- Shared `ArtifactSessionWorkspace` UI for diary and plan artifacts.
- Backend-owned workflow drafts and Memory Sweep review sessions under wiki
  `workflow/`; teachers can leave and resume without losing the turn or review.

Known PM gaps:

- Class home is useful but not yet proactive.
- Evidence is mostly embedded in agent output, not first-class UI metadata.
- Wiki viewer is functional but not a teacher-friendly memory explorer.
- Memory compaction/profile learning exists but is only partly productized.
- Wiki/input conflicts are detected only in eval scaffolding today; proactive
  roster/name mismatch clarification is the next trust gap.

---

## v1.1 - Make The Core Loop Trustworthy

**Theme:** The teacher can trust, inspect, and reuse generated work faster.

**What it enables:** The current memory/planning loop becomes reliable enough
for repeated weekly use and expands into one high-value adjacent workflow:
assessment generation.

Primary items:

| Item | Engineering notes |
|---|---|
| **Evidence/source panel** | Surface source metadata for class memory used in plans and memory updates. Start with class wiki sources and raw refs already captured by runtime state. |
| **Class-home briefing v1** | Add a compact class brief: recent lessons, open loops, sparse areas, and likely next move. Read-only; no suggested-task persistence yet. |
| **Plan quality review** | Lightweight post-generation sanity pass: duration, lesson phases, citations, open loops, misconceptions, and teacher constraints. |
| **Test / exam generation** | New artifact workflow using `ArtifactSpec`; ground in taught sequence, misconceptions, and assessment readiness. Include answer key/rubric where useful. |
| **Visible memory/profile suggestions** | Productize the existing profile-proposal/apply flow so the teacher sees "copilot learned this" suggestions after save. |
| **Input-vs-wiki reconciliation v1** | Treat the committed wiki as baseline. Start with deterministic roster/name mismatch detection, model-written clarification, explicit teacher confirmation for new/changed students, and removal-on-revise tombstone handling. |
| **Wiki health check / lint** | Expose `LINT_SYSTEM` as a bounded teacher/admin action. Report only; no silent mutation. |
| **Playwright smoke tests** | Cover ingest commit, plan save, and source/review UI paths. |
| **Session persistence decision** | Add SQLite/app-owned persistence only if real testing shows restart/session loss hurts usage. |
| **Hosted beta on AWS** | Move the current local beta shape to AWS without changing product scope: Amplify for frontend, ECS/Fargate + ALB for FastAPI, EFS for per-workspace wiki roots, Postgres/Aurora for telemetry and beta metadata, S3 for exports/backups. |
| **Operator beta runbook** | Daily report generation, wiki-diff review, tester feedback notes, backup/export, and retention cleanup. Keep this CLI/docs-first unless a dashboard becomes clearly necessary. |
| **Multi-worker / session hydrate docs** | Document single-worker-per-wiki assumption for local/HITL stacks; note that durable drafts + executive JSON survive restart, while in-memory session caches in `deps.py` are not multi-worker safe without sticky routing or always-hydrate-from-draft-store. |
| **Workflow-drafts page slim-down** | Finish the plan/memory page extraction onto the shared artifact-session shell: runtime adapter registry, shared discard/bootstrap helpers, thinner commit/review workspaces. Unblocks adding exam/status workflows without copying 400–800 LOC pages. |
| **Memory Sweep stale-diff hardening** | `memory_sweep_stale_reasons` field-diffs two snapshot dicts and was fragile: union of wiki-target keys + unsafe `previous_targets[target]` raised `KeyError: 'teaching_patterns.md'` when a target existed only in the live snapshot (HITL 2026-07-12; frontend surfaced it as “Cannot reach API”). Defensive `.get()` patched for launch. v1.1: prefer fingerprint-first stale gate (hash whole source snapshot); treat human-readable reasons as best-effort and never crash the review GET. Same pattern for student-summary keys. |

Non-goals:

- School SaaS accounts or role hierarchy.
- Voice/Telegram capture.
- Docling ingestion.
- Autonomous writes.

Validation:

- A teacher can update memory and save a grounded next plan with less manual
  source checking.
- A generated assessment cites the taught sequence and common misconceptions.
- The UI makes it clear what was used and what will be written.

---

## v1.2 - Make Onboarding And Memory Creation Easy

**Theme:** Useful on day one.

**What it enables:** A new class can get a usable wiki, preferences, and source
library without weeks of manual lesson logging.

Primary items:

| Item | Engineering notes |
|---|---|
| **Class wiki factory** | Guided class creation for subject, year, unit, curriculum direction, default lesson structure, and teacher preferences. |
| **Wiki personalization workflow** | Teacher edits `class_config.md` custom sections and compact profile pages through approved flows. |
| **Material upload library** | Store teacher-provided notes, prior plans, worksheets, and curriculum docs as source material with provenance. |
| **Docling/PDF ingestion spike** | Evaluate Docling for PDF/DOCX/PPTX extraction. Preserve source pages/sections for citations. |
| **Teacher-approved import to wiki** | Distinguish one-time planning context, source-library material, and durable class memory. |
| **Class concept map / curriculum graph** | Small class-scoped concept graph for one school year plus high-level prior-year foundations. Use plain wiki JSON plus backend validation: concepts, skills, vocabulary sets, misconceptions, prerequisites, and assessment targets. Agents propose source-backed graph patches; teacher approval writes them. |
| **New-class sparse memory handling** | Make sparse memory explicit; ask one targeted setup question at a time. |

Concept-map design notes from `ref_repos/AutoSci`:

- Borrow the graph contract discipline, not the research graph system. AutoSci
  keeps node schemas in `runtime/schema/entities.yaml`, edge types in
  `runtime/schema/edges.yaml`, slug/storage rules in
  `runtime/schema/conventions.yaml`, and declarative writer ownership in
  `runtime/policy/writers.yaml`.
- The useful code pattern is `tools/research_wiki.py::add_edge`: validate edge
  type, node ids, confidence/evidence fields, symmetry, and dedupe before
  writing. For KlassenPilot, mirror this with a small backend graph-patch
  validator instead of letting chat mutate graph files directly.
- AutoSci's `tools/visualize.py` shows useful read-side behavior: load graph
  rows, build focused subgraphs with BFS, and render derived views. For
  KlassenPilot v1.2, keep this as optional inspiration for a later teacher
  concept-map view, not a dependency.
- Initial non-goals: no NetworkX requirement, no SQLite graph storage, no graph
  database, no broad AutoSci runtime/schema port, and no autonomous concept-map
  writes.

Non-goals:

- "All textbooks" as a default corpus before licensing/source constraints are
  solved.
- Vector database as the default retrieval path unless deterministic retrieval
  shows measured limits.
- Autonomous conversion of uploaded materials into durable wiki facts.
- Dedicated graph database or general-purpose graph analytics layer.

Validation:

- A teacher can create a class and get a useful first plan in under 15 minutes.
- Uploaded material can be cited in a plan and reviewed separately from class
  memory.
- A generated plan or assessment can name the prerequisite concepts,
  vocabulary sets, or prior-year foundations it relies on, with source-backed
  graph evidence.

---

## v1.3 - Expand The Agent's Knowledge Safely

**Theme:** Trusted external knowledge, not generic web browsing.

**What it enables:** The copilot can enrich class-grounded plans with reputable
resources and subject teaching practices while keeping sources inspectable.

Primary items:

| Item | Engineering notes |
|---|---|
| **Trusted search tool** | Bounded search/read over allowlisted sources: PhET, Wikipedia, official curriculum pages, reputable education sites, and approved news/source categories. |
| **Resource adaptation workflow** | Return adaptation notes, links, risks, and classroom fit; never auto-insert external facts into wiki memory. |
| **Source cards** | Show external source, class memory, and uploaded-material provenance in one evidence UI. |
| **Subject teaching-practice library v1** | Start narrow with chemistry: common misconceptions, diagnostic questions, safe experiments, activity formats, and assessment templates. |
| **Search/tool guardrails** | Keep class wiki retrieval as the default memory path; external search is task-specific. |
| **Agent safety hardening v1** | Extend the minimal teacher-agent security layer before adding trusted search or other higher-risk tools: SDK input/output guardrails for prompt leakage, PII-like leakage, hidden write requests, and high-stakes student decisions; full streamed-event redaction/sanitization, trace endpoint access control and retention, source-card UI instead of raw tool output, transactional rollback for blocked turns, stronger real-data privacy/anonymization, and broader adversarial eval coverage. |
| **OWASP ASI red-team pass** | Add optional DeepTeam/manual red-team runs for ASI-style risks, starting with goal hijack, tool misuse, memory/context poisoning, and human-agent trust exploitation. Promote useful findings into deterministic DeepEval goldens. |
| **Retire legacy broad wiki tools** | Replace or fence the broader `create_wiki_tools()` read path before the agent has external search or more sensitive data. Main chat tools should remain class-scoped and purpose-specific. |
| **EU/Germany launch boundary note** | Keep this lightweight unless launch plans become concrete: document that KlassenPilot is a teacher copilot, not an automated grading/placement/diagnosis/discipline system; identify which future features would trigger legal review. |

Non-goals:

- Broad open web browsing by default.
- External source claims without citations.
- Automatic wiki writes from trusted search.
- High-stakes student decisions such as grading, placement, diagnosis,
  admission, or discipline.
- Full compliance certification before a real launch path exists.

Validation:

- Teacher can add a reputable resource to a plan and inspect why it was chosen.
- The copilot distinguishes "class memory says" from "external source says."
- Safety evals catch prompt/trace leakage, hidden write claims, and high-stakes
  decision attempts before trusted external tools are enabled.

---

## v1.4 - Become Proactive

**Theme:** The copilot already looked.

**What it enables:** The class home shifts from a dashboard to a small executive
assistant surface with evidence-backed next actions.

Primary items:

| Item | Engineering notes |
|---|---|
| **Class brief service** | Read-only class brief on entry: recent lessons, open loops, stale items, sparse areas, and next calendar gap. Cache with TTL. |
| **Suggested task API + UI** | Structured cards: `{ id, kind, title, rationale, evidence_paths, action_href, priority }`. Keep the stack small. |
| **Post-commit follow-ups** | After memory save, suggest 1-3 concrete next actions: close loop, plan next lesson, review student note, update profile. |
| **Stale-loop hygiene** | Detect old open loops and suggest close/reopen actions with teacher confirmation. |
| **Local Honcho-style profile polish** | Continue using local markdown profile pages before considering an external memory service. |

Task kinds:

- `log_memory`
- `plan_lesson`
- `generate_assessment`
- `close_loop`
- `review_commit`
- `fill_gap`
- `external_resource`

Non-goals:

- Always-on messaging gateway.
- Full AutoSci graph or broad multi-agent orchestration.
- Autonomous writes.
- Hermes-style self-authored skills.

Validation:

- A teacher opens a class, sees one accurate proactive sentence and one
  actionable task, completes or dismisses it in two clicks, and gets a sensible
  next suggestion.

---

## v1.5 - Add Low-Friction Capture

**Theme:** Capture class memory in the moment.

**What it enables:** Teachers can send a quick voice memo or chat message after
class and have KlassenPilot draft memory updates or follow-ups for review.

Primary items:

| Item | Engineering notes |
|---|---|
| **Voice memo ingestion** | Transcribe teacher voice notes into draft lesson memory or admin notes. |
| **Telegram or similar capture channel** | Treat messaging as an input/capture layer, not the primary product surface. |
| **Transcript review** | Show transcript, inferred target lesson, and diary draft before proposing wiki writes. |
| **Quick follow-up capture** | Extract reminders, open loops, and student observations into reviewable suggestions. |
| **Security/privacy review** | Confirm storage, retention, and channel trust before real teacher use. |

Non-goals:

- Messaging as a replacement for the reviewed web workflow.
- Automatic durable writes from voice.
- Multi-user school deployment unless already validated.

Validation:

- A teacher can send a 60-second post-lesson memo and get a useful reviewed
  memory draft with less effort than typing.

---

## v1.6 - Broaden Into Teaching Logistics

**Theme:** Reduce more operational work around class teaching.

**What it enables:** KlassenPilot becomes the operational home for class
teaching work, not just memory and planning.

Candidate workflows:

- homework/follow-up tracking
- assessment calendar
- report-comment drafts
- parent/admin communication drafts
- class content organization
- multi-week lesson sequence planning
- recurring reminders and check-ins

Non-goals until demand is proven:

- grading automation without teacher review
- real student names
- school-admin platform workflows
- broad always-on external messaging

Validation:

- Teachers use KlassenPilot for recurring weekly class operations beyond lesson
  memory and planning.

---

## v2 - Student Learning Copilot

**Theme:** Extend the class-memory foundation into student-facing formative
learning.

**What it enables:** Students can use a strict student-visible lens over class
memory and materials to repair wrong answers, prepare for exams, and build
spaced practice without accessing teacher-private wiki memory.

Primary items:

| Item | Engineering notes |
|---|---|
| **Student-visible class wiki lens** | Derived, read-only view over teacher-approved class memory, lecture materials, worksheets, concept scope, and source cards. Never expose teacher-private notes, raw diary data, other students, or traces. |
| **Per-student learning memory** | Separate class-scoped and global student memory for attempts, misconception repairs, concept mastery signals, feedback history, and review schedules. |
| **Pset repair workflow** | Student uploads returned work or marks wrong answers; the copilot diagnoses concepts, guides retries, gives formative feedback, and schedules review. Not official grading. |
| **Exam-prep workflow** | Generate a practice pathway from taught scope, materials, student weaknesses, and upcoming assessment scope. |
| **Spaced repetition / active recall** | Evaluate FSRS/Anki-style scheduling and retrieval-practice patterns for concepts, mistake types, and problem templates. |
| **Learning best-practices library** | Productize retrieval practice, distributed practice, feedback quality, interleaving, and knowledge-tracing ideas as tutor policies. |
| **Teacher controls and analytics** | Start with publish/withhold controls and aggregate misconception signals. Individual progress visibility needs a separate privacy decision. |

Non-goals:

- official grading or grade recommendations
- exposing teacher-private wiki memory
- letting students mutate teacher/class wiki
- cross-student memory sharing
- unsupported broad tutoring outside course scope
- high-stakes decisions such as placement, diagnosis, discipline, admission, or
  accommodations

Validation:

- A student can work through returned wrong answers, explain the corrected
  concept, solve a related problem, and receive a scheduled follow-up review.
- The system can generate an exam-prep pathway grounded in taught class scope
  and the student's own mistake history.
- The teacher can trust that student activity does not mutate or leak teacher
  memory.

Research and product note: [`docs/student_learning_copilot_v2.md`](../docs/student_learning_copilot_v2.md).

---

## Cross-Cutting Platform Track

These can land alongside product versions when needed, but should not displace
teacher-value work without a concrete blocker.

| Item | When to prioritize |
|---|---|
| **Caddy reverse proxy** | When deployment needs one entry port, same-origin `/api`, or simpler SSE handling. |
| **Lean production images** | Before non-dev deployments. |
| **`compose.prod.yaml`** | Before repeatable production-like installs. |
| **SQLite/app session persistence** | When real users hit restart/history loss or multi-worker deploys. |
| **AWS beta hosting** | Next platform step before external testers: persistent `BETA_DATA_ROOT`, HTTPS, Secrets Manager, CloudWatch logs, backups, and restart-safe wiki/telemetry storage. See `implementation_plans/beta_push.md`. |
| **Replace beta identity provider** | After tester validation: keep `RequestIdentity(tester_id, workspace_id, role)` and swap the invite-code resolver for Cognito, Auth.js, Clerk, Auth0, or equivalent OAuth-backed auth. The API and wiki-store access should continue consuming `RequestIdentity`, not provider-specific user objects. |
| **Production auth/account model** | When moving beyond invited testers: introduce durable user/account/workspace tables, OAuth login, account recovery, secure cookie/session rotation, and explicit workspace membership. Avoid school/team roles until there is pull. |
| **Generalized trace assemblies** | Before adding several more artifact/helper agents. |
| **Typed index/search improvements** | When deterministic retrieval has measured failures. |
| **Real-data privacy/security hardening** | Before real teacher/student data or non-local deployment: stronger pseudonymization/redaction, retention rules, access control for traces, output sanitization review, and EU/Germany legal checklist. |
| **Postgres/object storage/accounts** | Postgres is justified for hosted beta telemetry; broader account/product data should wait until multi-user demand is clear. |

---

## Parking Lot

- **Names-first student display (beta UX), IDs stay the internal key.** Surface
  student *names* on all teacher-facing surfaces (chat, diary, student pages)
  while wiki entities stay `students/S-###.md` keyed — a display/render layer
  (inverse of `_pseudonymize_known_students`), reversible for real students.
  Held 2026-07-07 (owner testing on IDs first). For beta the name↔ID handling
  stays prompt-based. Design + decisions:
  [`docs/mem_v3/input_reconciliation.md`](../docs/mem_v3/input_reconciliation.md).
- **Input↔wiki reconciliation** — deterministic roster-membership check
  (names + IDs, fuzzy), clarify-then-confirm, removal-on-revise tombstone fix.
  Eval scaffold + design landed; validate UX with real teachers before
  hardening. Same doc.
- Multiple classes polish, class calendar, lesson graph view.
- Long-running jobs and background queues.
- Memory approval queue.
- Private textbook/source integrations where licensing is solved.
- Rubrics, answer ingestion, and teacher-reviewed grading suggestions.
- School/team collaboration features.
