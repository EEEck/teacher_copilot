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

## v1.0 - Ship The Trusted Teach → Memory → Plan Loop

**Theme:** A teacher can teach, log reviewed class memory, discuss the class,
and generate a grounded next lesson — with verification and inspectable sources.

**What it enables:** The full weekly loop (update memory → plan) plus free-form
class discussion, all grounded in a compiled wiki and gated by teacher approval
and executive write-verification. Running as a private Railway beta.

Shipped:

- Class landing -> class home with timeline and memory snapshot.
- **Update memory**: chat + diary draft -> teacher-approved wiki commit.
- **Create lesson plan**: chat + plan draft -> save to a lesson date.
- **Discuss**: free-form class discussion workflow on the shared chat stack,
  grounded in class memory and trusted sources.
- **Executive write-verification**: one shared `ExecutiveRuntime` with advisory
  findings plus a blocking write gate. Shipped packs: Plan scope/provenance
  review and Update Memory roster/target integrity (malformed/unknown `S-###`,
  name-style labels, confirmed target-date mismatch). Roster observation
  subjects resolve to ids at the write boundary (advisory, never hard-block).
- **MemV4 memory contract**: explicit `remember(...)` capture -> candidate
  ledger -> bounded semantic Memory Sweep -> teacher-approved durable writes;
  typed memory write/read skills; claim↔quote capture grounding.
- **Trusted-source pilot (Bavaria Chemie)**: class allow-list, compact source
  TOC/profile, progressive list/search/read tools, provenance capture, and seed
  extracts (LehrplanPLUS NTG 8/9, Fachprofil, KMK AHR). Not open-web search.
- **Class brief service**: read-only class-home brief (recent lessons, open
  loops, sparse areas) with refresh endpoint.
- **Beta tester mode**: invite-code login, workspace-scoped wiki copies, and
  local telemetry for app activity, visible conversations, draft snapshots, and
  approved wiki diffs.
- **Beta review tooling**: CLI Markdown reports over telemetry and wiki diffs,
  plus Memory Sweep review UX with card warnings, stepwise loading, clearer
  teacher-facing decisions, and seven-day deferral for uncertain signals.
- **Model call-class routing**: production/economy profiles split chat,
  important consolidation, and utility calls; live agent evals default to the
  production profile unless the run explicitly compares models.
- **Railway beta deployment**: hosted invite login, per-workspace wiki roots,
  telemetry, configurable SameSite session cookies, and provisioning scripts.
- Timeline/detail shortcuts for adding results to planned lessons or correcting
  taught lessons.
- Karpathy-style compiled wiki with compact class memory pages.
- Deterministic wiki pathfinding and class-scoped read tools.
- Shared `ArtifactSessionWorkspace` UI for diary and plan artifacts.
- Backend-owned workflow drafts and Memory Sweep review sessions under wiki
  `workflow/`; teachers can leave and resume without losing the turn or review.

Known PM gaps (carried into later versions):

- Class home is useful but not yet proactive (see v1.5).
- **Discuss task-anchor discipline:** Discuss may briefly engage a personal
  aside when it helps rapport or reveals a preference, but must answer concisely
  and return to the class/lesson task; avoid open-ended topic drift. Keep
  focused trace/eval cases for aside -> one-sentence response -> task-return.
- Evidence is grounded in agent output and backend citations, but there is no
  first-class teacher-facing evidence/source panel yet (see v1.1).
- Wiki viewer is functional but not a teacher-friendly memory explorer.
- Memory compaction/profile learning exists but is only partly productized.
- Roster name→id resolution ships at the write boundary, but proactive
  clarify-then-confirm and removal-on-revise handling are still open (see v1.1).

---

## v1.1 - Make The Core Loop Trustworthy

**Theme:** The teacher can trust, inspect, and reuse generated work faster.

**What it enables:** The shipped memory/planning/discuss loop becomes reliable
enough for repeated weekly beta use. This section is now scoped to the
*remaining open* hardening work; the loop itself shipped in v1.0.

### Open work queue

Keep each item as a separate implementation slice; they are intentionally not a
reason to expand the product surface.

| Priority | Task | Scope and acceptance |
|---|---|---|
| P0 | **Chat-turn resilience** | Close the remaining frontend notifier/hydration race: a backend-complete turn must always clear the local pending state and merge the final reply. Add focused notifier integration coverage. Use the [browser workflow runbook](../docs/superpowers/specs/2026-07-20-browser-workflow-runbook-design.md) for a fresh-sandbox Plan, Discuss, and Update Memory acceptance pass. |
| P0 | **Input-to-wiki reconciliation (finish)** | Roster name→id resolution ships; complete the trust loop: when a diary changes or removes an unknown/mismatched student, retain the conflict for explicit teacher correction rather than silently normalizing, with model-written clarification and removal-on-revise tombstone handling. Cover roster mismatch -> correction -> recovery. |
| P0 | **Date awareness** | Add the current date and the planned-versus-taught rule to the compact teacher context used by Plan, Update Memory, and Sweep. Freeze time in prompt-assembly tests. |
| P1 | **MemV4 capture admission/routing** | Turn the live-eval ledger's known gaps M4-LIVE-02 through M4-LIVE-05 into behavior: scoped Chemistry preferences, instruction/evidence decomposition, no accidental global preference leakage, and no uncertain durable candidates. Own this as one backend slice because the cases share capture/routing policy. |
| P1 | **Offline plan-quality calibration** | Run an adapted Bavaria Chemie 9 NTG P/R/O/M rubric over retained beta plan artifacts using DeepEval/LLM-as-judge. Store operator-only results; do not add user latency, hidden rewriting, or a new live save gate. |
| P1 | **Generic plan empty state** | Replace the legacy pre-filled `Lesson Plan — Next lesson` shell with a class-agnostic empty state that explains a plan package appears after a teacher request and never implies generic phases/goals were generated. |
| P1 | **Frontend evidence/source panel** | Backend citation/provenance exists; surface source metadata for class memory and trusted sources used in plans and memory updates as first-class UI, starting with class wiki sources and captured raw refs. |
| P2 | **Reopen saved plan** | Implement the already-scoped `lessonDate` session-start hint so a saved plan can be refined in chat instead of regenerated. |
| P2 | **Editable lesson timeline (manual date edits)** | Let the teacher edit the class timeline directly: reschedule a saved lesson to a different date and correct/adjust lesson dates without regenerating. Since the lesson date is the folder/identity key stamped at save (`normalize_plan_target_date`), a reschedule must move the `lessons/<date>/` artifacts and update `timeline.md` atomically, keep the plan text's `Target date:` in sync, and reject/merge collisions with an existing lesson on the target date. Small UI affordance on the class-home timeline + a backend move/rename that reuses the save gate. |
| P2 | **Visible memory/profile suggestions** | Productize the existing profile-proposal/apply flow so the teacher sees "copilot learned this" suggestions after save. |
| P2 | **Wiki health check / lint** | Expose `LINT_SYSTEM` as a bounded teacher/admin action. Report only; no silent mutation. |
| P2 | **Remaining executive packs** | Keep the shared `ExecutiveRuntime`. Add advisory Discuss grounding and operational Class Brief freshness packs. `scope_unverified` stays advisory-only: generate and save, but ask the teacher to confirm an intentional curriculum extension. No topic-specific rules; no raw source/prompt bodies. |
| P2 | **Workflow-drafts page slim-down** | Finish the plan/memory page extraction onto the shared artifact-session shell: runtime adapter registry, shared discard/bootstrap helpers, thinner commit/review workspaces. Overlaps F6/F7. Unblocks adding exam/status workflows without copying 400–800 LOC pages. |
| P2 | **Playwright smoke tests** | Cover ingest commit, plan save, and source/review UI paths. |
| P2 | **Operator beta runbook + hydrate docs** | Daily report generation, wiki-diff review, tester feedback, backup/export, retention cleanup (CLI/docs-first). Document the single-worker-per-wiki assumption: durable drafts + executive JSON survive restart, but in-memory `deps.py` session caches are not multi-worker safe without sticky routing or always-hydrate-from-draft-store. |
| P2 | **Beta feedback survey** | Short per-session / weekly tester survey linked to `tester_id` (and optionally session ids): did the wiki capture the right teaching facts, did the next plan improve because of prior memory, what felt wrong/stale/missing, how much editing was needed, did approval feel trustworthy. Lets the operator compare survey comments against wiki diffs and transcripts — measures whether memory is improving, not just whether the UI works. |

Explicitly deferred from this v1.1 slice: year-start materials library /
chapterize (v1.2 Phase 3 — in-plan PDF upload already shipped; see
[`v1.2_class_materials_epic.md`](v1.2_class_materials_epic.md)), broader
Discuss/Class Brief verification packs beyond the advisory ones above, and
class-home proactive expansion (v1.5). They do not block the beta loop.

### Pre-beta code-audit backlog (parked 2026-07-21)

Tech-debt / hardening surfaced by the pre-beta QA audit
([`docs/pre_beta_qa_audit_2026-07-21.md`](../docs/pre_beta_qa_audit_2026-07-21.md)).
None block beta; each is a refactor best done on the working, test-covered code
post-launch. The beta-blocking findings (roster over-block, plan safety-gate
bypass) and the quick hardening were already fixed in the audit branch.

| ID | Item | Engineering notes |
|---|---|---|
| F5 | **Contract single-source-of-truth** | Generate `frontend/src/lib/api.ts` types from the FastAPI OpenAPI (e.g. `openapi-typescript`) and/or regenerate + CI-check `contracts/openapi.yaml` (currently ~9 of ~60 endpoints; stale since 2026-05-27). Hand-mirrored TS types can silently drift from the Pydantic contract. |
| F6 | **`useMemoryReview` extraction** | Pull sessionStorage review persistence, the `beforeunload` guard, the reset effects, and the double-commit idempotency guard out of the ~480-line `MemoryWorkspace` into a hook / state-machine. Overlaps **Workflow-drafts page slim-down** above; regression-test the commit flow. |
| F7 | **Split `routes.py` monolith** | 2613 lines / ~60 endpoints in one module. Split into per-domain routers (beta, classes, discussion, ingest, plan, memory-sweep) and share the repeated non-stream chat telemetry calls behind one wrapper. |
| F8 | **Type the API `dict` seam** | Replace untyped `dict` passthroughs (`executive_state`, `session_state`, `lesson_planning_state`, `memory_candidates`) with Pydantic models so the review UI's implicit shape dependency is compile-checked both ends. |
| F14 | **Retire `PlanTurnOutput` dual state path** | Drop the full-snapshot `session_state`/`lesson_planning_state` compatibility fallback once nothing relies on it; keep only `state_patch`. |
| F15 | **WikiStore facade boundary** (cosmetic) | ~30 `_private` methods are exposed on the public facade and called cross-module. Formalize public API vs internals. Lowest priority. |

Also parked from the audit: the **4 eval-tier goldens** (deepeval; likely golden
refresh after the capture/verification changes), **`knip`** for frontend
unused-export detection, and **idle-TTL eviction** for the per-workspace
`deps.py` service caches (bounding them naively would drop live in-memory
sessions).

### Incident / bug queue (living)

Short records for launch patches that still need a durable follow-up. Prefer one
entry per incident. Close or demote when the long-term fix ships. New agents:
start here before inventing a redesign.

**Template:** ID · status · symptom · root cause · reproduce · quick fix ·
long-term · tests.

#### MSW-001 — Memory Sweep stale KeyError → “Cannot reach API”

| | |
|---|---|
| **Status** | Launch patched (`73e8fb8`); long-term open |
| **Symptom** | Opening / resuming Memory Sweep review showed frontend “Cannot reach API”. Backend `GET /api/classes/{id}/memory/sweep/review` returned 500. |
| **Root cause** | `memory_sweep_stale_reasons` field-diffed wiki targets (and student summaries) over `set(previous) \| set(current)` but indexed with `previous_targets[target]` / `previous_summaries[id]`. A key present only in the *live* snapshot raised `KeyError` (HITL: `teaching_patterns.md`). |
| **Quick fix (shipped)** | Use `.get(...)` on both sides of the comparison so missing keys count as a change, never raise. |
| **Long-term** | Fingerprint-first stale gate: hash the whole source snapshot for `is_stale`; treat human-readable field reasons as best-effort and **never** let reason generation crash the review GET. Same discipline for student-summary keys. |
| **Tests** | `test_memory_sweep_stale_reasons_tolerates_asymmetric_wiki_targets`, `…_asymmetric_student_summaries` |

Non-goals:

- School SaaS accounts or role hierarchy.
- Voice/Telegram capture (see v1.6).
- Autonomous writes.

Validation:

- A teacher can update memory and save a grounded next plan with less manual
  source checking.
- The UI makes it clear what was used and what will be written.

---

## v1.2 - Scanned Material Upload And Processing

**Theme:** Turn photographed or scanned teacher material into reviewable,
structured, teacher-approved input.

**What it enables:** A teacher can attach a PDF (worksheet, textbook pages,
board photo exported to PDF, handwritten notes, prior exam) in Create lesson
plan, get OCR'd citable content without retyping, and promote it into the class
on save. Year-start library browse is still remaining. All durable writes stay
teacher-approved.

**Living epic:** [`v1.2_class_materials_epic.md`](v1.2_class_materials_epic.md).
OCR primary is **Mistral OCR 4**. Backups are **not shipped**: OpenAI vision/VLM
is a code skeleton (`NotImplementedError`); Docling is a later optional path.

### Approved next program: class course network (planned, not shipped)

The teacher-feedback concept-map direction has passed product design and moved
out of the parking lot. The MVP is a class-owned Chemie 8/9 NTG course network
with one `Lernbaustein` node type, standalone reviewed material ingestion,
reviewed material/graph enrichment, and automatic weekly planning retrieval and
lesson references. It does not add cross-class graph reuse, a question bank,
Kanban, vector search, or a graph database.

- Approved product contract:
  [`2026-08-17-class-course-network-design.md`](../docs/superpowers/specs/2026-08-17-class-course-network-design.md)
- Delivery/PR map:
  [`2026-08-18-class-course-network-program.md`](../docs/superpowers/plans/2026-08-18-class-course-network-program.md)
- Detailed execution plans: foundation/adoption, reviewed editing,
  materials/mapping, and planner/lesson integration in
  [`docs/superpowers/plans/`](../docs/superpowers/plans/)

Track progress through the A1-A3, B1-B2, C1-C3, and D1-D3 PR boundaries in the
delivery program. Move individual capabilities into Shipped only when their PR
and focused documentation updates merge.

### Shipped (in-plan slice)

- Plan-session PDF upload (Textbook / Personal), optimistic composer tile,
  Send gated until OCR finishes. PDF only (export from Word/PPT/tablet).
- Mistral OCR 4 → session scratch (outside wiki). Upload OCR runs off the
  FastAPI event loop.
- Compact materials TOC + `list/search/read_class_material`; cite
  `Material: id`; embed `assets/img-*` / `tbl-*.jpg`.
- Promote on plan save into `materials/{textbooks|personal}/` +
  `lessons/{date}/materials.json`. Debug OCR dumps stay in scratch.
- OCR annotation prompts assemble from class wiki (subject/grade/school) plus a
  small STEM figure library (Chemie, Physik, Biologie, Mathe). Unknown Fächer
  get a generic overlay. Not a per-upload prompt generator.

### Remaining

| Item | Engineering notes |
|---|---|
| **OpenAI vision / VLM OCR backup** | Skeleton in `materials_ocr.py` (`engine="openai_vision"`). Raises `NotImplementedError`. Not wired to upload. Rasterize PDF pages → OpenAI image inputs → same package shape. |
| **Native Word / PPT / photo ingest** | PDF only today. Teacher exports first. |
| **Page-range picker UI** | API `page_range` exists; attach dialog does not send it. |
| **Background OCR jobs** | Upload still waits on OCR. `asyncio.to_thread` only unblocks the event loop. |
| **Keep-in-materials without plan save** | Promotion is save-only. |
| **Year-start material library** | Browse promoted textbooks/personal; “use chapter 1”; flag plan-scoped vs standing library entries. |
| **Textbook chapterize / Batch** | Split large books; Mistral Batch. |
| **Scratch GC / TTL** | Expire abandoned plan-scratch OCR packages. |
| **Docling/PDF ingestion (later backup)** | Born-digital PDF/DOCX/PPTX or self-hosted/offline extraction. Not first-slice runtime. |
| **Extraction review UI** | Teacher-facing page/section review before promote (today: plan chat + save). |
| **Teacher-approved import to wiki memory** | OCR never auto-writes MemV4 / course_state / diary. |

Non-goals:

- Autonomous conversion of uploaded/scanned material into durable wiki facts.
- "All textbooks" as a default corpus before licensing/source constraints are
  solved.
- Vector database as the default retrieval path unless deterministic retrieval
  shows measured limits.

Validation (in-plan slice):

- Offline unit tests: OCR prompt assembly (STEM + generic), packaging, upload →
  scratch, promote-skip-debug, save → wiki, asset URLs, send-gate.
- HITL browser: new plan → PDF attach → ask about content; Send blocked while
  reading.
- Opt-in live Mistral: `RUN_LIVE_MISTRAL_OCR=1`. Live golden
  `9b_plan_materials_embed_mo_asset`.

---

## v1.3 - Exams And Grade Management

**Theme:** Teacher-side assessment creation and grade/feedback workflows,
grounded in taught scope.

**What it enables:** Generate exams/quizzes grounded in the taught sequence and
misconceptions, and manage grades and feedback drafts — all teacher-owned and
teacher-approved, never autonomous grading.

Primary items:

| Item | Engineering notes |
|---|---|
| **Test / exam generation** | New artifact workflow using `ArtifactSpec`; ground in taught sequence, misconceptions, and assessment readiness. Include answer key/rubric where useful. Reuses the shared artifact-session shell. |
| **Rubric / answer-key authoring** | Author and edit rubrics and answer keys alongside a generated assessment; keep them as reviewable artifacts. |
| **Grade management** | Record and track grades per class/assessment as a teacher-owned artifact. Not autonomous grading and not a high-stakes decision system. |
| **Report-comment / feedback drafts** | Draft student feedback and report comments grounded in recorded results and class memory, for teacher review and editing. |
| **Assessment calendar** | Track upcoming assessments and due dates on the class timeline; feed date/scope context into exam generation. |
| **Teacher-reviewed grading suggestions** | Optional suggested marks/feedback for teacher review only; explicit teacher approval required, no automatic grades. |

Non-goals:

- Autonomous grading or grade recommendations without teacher review.
- Real student names before the privacy/anonymization work lands.
- High-stakes decisions such as placement, diagnosis, discipline, or admission.

Validation:

- A teacher generates an exam grounded in the taught sequence with an answer
  key, and records/tracks grades and feedback drafts with explicit approval.

---

## v1.4 - Expand The Agent's Knowledge Safely

**Theme:** Trusted external knowledge, not generic web browsing.

**What it enables:** The copilot can enrich class-grounded plans with reputable
resources and subject teaching practices while keeping sources inspectable. The
initial deterministic trusted-source pilot shipped in v1.0; this version
broadens it safely.

Primary items:

| Item | Engineering notes |
|---|---|
| **Trusted search tool** | Bounded search/read over allowlisted sources: PhET, Wikipedia, official curriculum pages, reputable education sites, and approved news/source categories. Not open-web search. |
| **Resource adaptation workflow** | Return adaptation notes, links, risks, and classroom fit; never auto-insert external facts into wiki memory. |
| **Subject teaching-practice library v1** | Start narrow with chemistry: common misconceptions, diagnostic questions, safe experiments, activity formats, and assessment templates. |
| **Search/tool guardrails** | Keep class wiki retrieval as the default memory path; external search is task-specific. |
| **Agent safety hardening v1** | Extend the minimal teacher-agent security layer before adding trusted search or other higher-risk tools: SDK input/output guardrails for prompt leakage, PII-like leakage, hidden write requests, and high-stakes student decisions; full streamed-event redaction/sanitization, trace endpoint access control and retention, source-card UI instead of raw tool output, transactional rollback for blocked turns, stronger real-data privacy/anonymization, and broader adversarial eval coverage. |
| **OWASP ASI red-team pass** | Add optional DeepTeam/manual red-team runs for ASI-style risks, starting with goal hijack, tool misuse, memory/context poisoning, and human-agent trust exploitation. Promote useful findings into deterministic DeepEval goldens. |
| **Retire legacy broad wiki tools** | Replace or fence the broader `create_wiki_tools()` read path before the agent has external search or more sensitive data. Main chat tools should remain class-scoped and purpose-specific. |
| **In-chat memory confirmation cards** | When `remember(...)` fires, offer an embedded chat card to apply or reject immediately via existing `/memory/apply` and candidate-status APIs. Reuse fast-lane eligibility + apply infrastructure; Sweep remains the default review home until the teacher acts in chat. |
| **EU/Germany launch boundary note** | Keep lightweight unless launch plans become concrete: document that KlassenPilot is a teacher copilot, not an automated grading/placement/diagnosis/discipline system; identify which future features would trigger legal review. |

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

## v1.5 - Become Proactive

**Theme:** The copilot already looked.

**What it enables:** The class home shifts from a dashboard to a small executive
assistant surface with evidence-backed next actions.

Primary items:

| Item | Engineering notes |
|---|---|
| **Proactive class brief** | Extend the shipped read-only class brief with a next-calendar-gap signal and stale-item detection; cache with TTL. |
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
- Autonomous writes.
- Hermes-style self-authored skills.

Validation:

- A teacher opens a class, sees one accurate proactive sentence and one
  actionable task, completes or dismisses it in two clicks, and gets a sensible
  next suggestion.

---

## v1.6 - Add Low-Friction Capture

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

## v1.7 - Broaden Into Teaching Logistics

**Theme:** Reduce more operational work around class teaching.

**What it enables:** KlassenPilot becomes the operational home for class
teaching work, not just memory and planning.

Candidate workflows:

- homework/follow-up tracking
- parent/admin communication drafts
- class content organization
- multi-week lesson sequence planning
- recurring reminders and check-ins

(Assessment calendar and report-comment drafts moved to v1.3 Exams & Grade
Management.)

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
| **AWS hosting (future scale)** | Beta currently runs on Railway. Move to AWS only if scale/isolation needs it (roadmap-wise this is v1.2-or-later platform work, not v1.1). Target stack: Amplify (Next.js), ECS Fargate + HTTPS ALB (FastAPI/SSE; single task first to avoid multi-writer EFS issues; ALB idle timeout ≥300s for ~240s agent turns), EFS for per-workspace wiki roots, RDS/Aurora Postgres for telemetry, S3 for exports/backups, Secrets Manager for keys, CloudWatch logs. `APP_ENV=production`; CORS locked to the frontend domain; prefer `eu-central-1` for German testers. Keep the `RequestIdentity` boundary; only storage/deploy plumbing changes. |
| **Object-store wiki (S3)** | Optional later durability step: store wiki files in S3 behind a `WikiStore` storage facade instead of filesystem paths. Defer unless file persistence becomes a blocker; current code assumes filesystem semantics. |
| **Replace beta identity provider** | After tester validation: keep `RequestIdentity(tester_id, workspace_id, role)` and swap the invite-code resolver for Cognito, Auth.js, Clerk, Auth0, or equivalent OAuth-backed auth. The API and wiki-store access should continue consuming `RequestIdentity`, not provider-specific user objects. |
| **Production auth/account model** | When moving beyond invited testers: introduce durable user/account/workspace tables, OAuth login, account recovery, secure cookie/session rotation, and explicit workspace membership. Avoid school/team roles until there is pull. |
| **Generalized trace assemblies** | Before adding several more artifact/helper agents. |
| **Typed index/search improvements** | When deterministic retrieval has measured failures. |
| **Real-data privacy/security hardening** | Before real teacher/student data or non-local deployment: stronger pseudonymization/redaction, retention rules, access control for traces, output sanitization review, and EU/Germany legal checklist. |
| **Postgres/object storage/accounts** | Postgres is justified for hosted beta telemetry; broader account/product data should wait until multi-user demand is clear. |

---

## Parking Lot

Held ideas and displaced scope. Promote into a version only with a concrete
teacher-value or engineering trigger.

- **Fast class onboarding / class wiki factory.** Guided class creation for
  subject, year, unit, curriculum direction, default lesson structure, and
  teacher preferences; plus teacher-edited `class_config.md` custom sections and
  compact profile pages through approved flows, and explicit new-class sparse
  memory handling (one targeted setup question at a time). Displaced when v1.2
  became scan/upload processing.
- **Names-first student display (beta UX), IDs stay the internal key.** Surface
  student *names* on all teacher-facing surfaces while wiki entities stay
  `students/S-###.md` keyed — a display/render layer, reversible for real
  students. Held 2026-07-07 (owner testing on IDs first); for beta the name↔ID
  handling stays prompt-based.
- **Lightweight "add one thing" capture.** Add a forgotten observation or note
  without a full session and full re-review. No settled design yet; revisit
  after the review-brief/skip mechanics suggest a shape.
- Multiple classes polish, class calendar, lesson graph view.
- Long-running jobs and background queues.
- Memory approval queue.
- Private textbook/source integrations where licensing is solved.
- School/team collaboration features.
