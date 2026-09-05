# KlassenPilot PM Hub

This is the product-facing source of truth for KlassenPilot. Use it to orient
roadmap, scope, prioritization, and product judgment before changing workflows.
The engineering roadmap lives in `../implementation_plans/product_backlog.md`;
behavior contracts live in `agent_contracts.md`.

## Product Vision

KlassenPilot gives every teacher a private executive assistant for their
classes. It remembers what happened, prepares what comes next, manages teaching
content and logistics, and turns class context into usable plans, materials, and
follow-ups.

Teachers stay in control. KlassenPilot handles the work around teaching so the
teacher can focus on students, judgment, and classroom presence.

## North Star

Save teachers time by minimizing "work about work," so they can focus on what
matters most: their students.

## North Star Metric

Weekly teacher time saved through completed class workflows.

Near-term proxy signals:

- memory updates completed per active teacher per week
- lesson plans saved from class memory
- teacher edits needed before saving an artifact
- source-backed plans as a share of saved plans
- time from opening a class to a useful next action
- repeat weekly active teachers

## Product Thesis

Every approved lesson update makes the copilot more useful for future lessons.

The product wins when a teacher no longer starts from a blank prompt. They open
a class and KlassenPilot already knows what was taught, what students struggled
with, what worked last time, and what should probably happen next.

## Current Product State

The current v1 prototype is a focused class-memory and lesson-planning product.

Shipped teacher workflows:

- **Class selection**: choose a class and open its workspace.
- **Class home**: executive-assistant landing with Classroom dashboard (brief,
  At a glance, Upcoming, My notes), Actions (Plan / Discuss, plus Sharpen
  assistant, Other wiki edits, and Browse class files), and Lesson timeline.
  Lesson memory capture is primarily via timeline row CTAs (Add results);
  Other wiki edits is the demoted freeform escape hatch.
- **Update memory**: chat with the copilot, produce lesson-results markdown,
  review proposed wiki file changes, and save only teacher-approved updates.
- **Create lesson plan**: chat with the copilot, refine a plan markdown artifact,
  review the plan-file diff, and save it to a lesson date. Plan chat can attach a
  **PDF class material** (Textbook or Personal): Mistral OCR 4 writes a session
  scratch package; the planner cites/embeds cutouts; durable wiki promotion
  happens only on plan save. The course feature branch adds a standalone reviewed
  chapter library and reuses plan-saved PDFs; larger whole-book intake remains separate.
- **Timeline/detail shortcuts**: one status chip per lesson — **Upcoming**
  (future plan), **Add results** (plan due / past), **Done** (results logged).
  Matching row CTAs open Update Memory (“Add results” / “Correct with agent”).
  Toolbar **+ plan next lesson** opens Create lesson plan.
- **Lesson detail**: inspect saved plan/results, revise lesson results, and view
  roll-up excerpts.
- **Wiki file viewer**: inspect changed markdown files after saves.
- **Beta tester mode**: invite-code login with an HTTP-only session cookie,
  workspace-scoped wiki copies, and `tester_id` / `workspace_id` request
  identity.
- **Beta telemetry**: local operator-side capture of app sessions, visible
  conversations, draft snapshots, app events, approved wiki diffs, and a
  Markdown beta report CLI.
- **Memory Sweep**: review accumulated memory signals in a backend-owned saved
  review session, apply supported writes, dismiss or postpone suggestions, and
  resume later without regenerating unless sources drifted.
- **MemV4 memory capture and sweep**: chat can stage review-only durable-memory
  candidates through the explicit `remember(...)` tool; a ledger/folding/gate
  layer throttles noise; the teacher-triggered sweep runs one high-reasoning
  consolidation call and presents a teacher-first Simple/Detailed review brief
  (sections: Explicitly requested, New memory, Changed, Already covered /
  not worth keeping, and a separate **Student summary updates** bucket).
- **Chemie 9 NTG planning grounding (shipped)**: adapted Anthropic open K–12
  lesson-planning + differentiation procedure (Apache-2.0; not a live plug-in);
  LehrplanPLUS/KMK as provenance-bearing trusted sources (section must be read
  before official curriculum claims); immutable shared teaching frameworks for
  Chemie 8/9 NTG with class overrides in `teaching_framework_adjustments.md`.

Core implementation shape:

- FastAPI backend with OpenAI Agents SDK.
- Next.js frontend using a shared artifact-session shell and a workflow-draft
  store for Plan / Update Memory chat.
- Backend-owned workflow drafts and Memory Sweep reviews under the wiki
  `workflow/` directory; teachers can leave and return without losing the turn
  or review draft.
- Durable background jobs (chat turns, sweep generation) surface in a small
  Running box with one completion toast when finished.
- Karpathy-style markdown wiki as canonical class memory.
- Compact class memory and profile pages for fast context.
- Teacher-approved durable writes; chat tools stay read-only.
- Model routing is tiered by call class: production uses the top model for chat
  and sweep quality, while economy may use a cheaper chat model but still keeps
  the sweep on the strong model.
- Beta auth is intentionally simple: invite codes plus an opaque cookie. The
  code path resolves every request through a `RequestIdentity`, so later
  production auth can replace only the identity provider instead of rewriting
  wiki access.

## Product Principles

- **Teacher stays in control**: no hidden writes and no irreversible autonomous
  actions.
- **Executive assistant, not passive chatbot**: complete the foreground task,
  verify class-state details in the background, and surface only consequential
  teacher decisions.
- **Class memory compounds**: every approved update should improve future work.
- **Start from the class, not a blank prompt**: context should load
  automatically.
- **Reduce work about work**: summaries, plans, follow-ups, materials, and admin
  drafts should become easier.
- **Ground claims in evidence**: plans and suggestions should cite class memory,
  uploaded materials, or trusted sources.
- **Practical over magical**: outputs must be editable, specific, and usable in
  real classroom time.
- **Privacy by default**: memory is class-scoped, local/private first, and
  student details remain pseudonymous.

## Strategic Pillars

1. **Remember the class**
   Build trustworthy, teacher-approved class memory from lessons, materials,
   preferences, and corrections.

2. **Prepare the next teaching step**
   Turn memory into plans, assessments, resources, and follow-ups with minimal
   prompting.

3. **Ground work in trusted sources**
   Combine class memory with uploaded materials and reputable sources the
   teacher can inspect.

4. **Reduce teaching logistics**
   Help with the administrative work around class teaching: follow-ups,
   reports, content organization, reminders, and recurring tasks.

5. **Proactively surface what matters**
   Move from "choose a workflow" to "the copilot already looked and has a useful
   next action."

## PM Gaps And Roadmap Response

| Gap / risk | Why it matters | Roadmap response |
|---|---|---|
| Class home is mostly a dashboard | The product should feel like an assistant that already looked | Class brief, suggested tasks, stale-loop hygiene |
| Sessions are prototype-grade | Losing chat history hurts trust during real use | SQLite or app-owned session persistence when user testing shows pain |
| Wiki viewer is not teacher-friendly | Teachers should not need to browse raw markdown | Memory explorer, evidence/source panel, editable preferences |
| Test/exam generation is not first-class | Clear high-frequency teacher time saver | New assessment artifact workflow |
| Memory/profile flows are partially productized | Personalization is part of the executive-assistant promise | Visible "copilot learned this" review and memory health |
| Wiki/input conflicts are not yet proactive | Teacher trust depends on the wiki being the baseline, especially for roster typos or class-state contradictions | Deterministic conflict detection first, then model clarification and teacher-confirmed resolution |
| Repository supports the private Railway beta deployment | Course release still needs deployment-specific persistence, restart and recovery acceptance | Continue the existing Railway setup; AWS is a later scale option, not a prerequisite for this release |
| Auth is beta-grade invite-code auth | Good for first testers, not proper production identity, account recovery, or school roles | Keep `RequestIdentity`; later swap invite-code provider for Cognito/Auth.js/Clerk/Auth0/OAuth |
| Evidence is not visible enough | Trust depends on inspecting sources | Source panel for class memory, uploads, and trusted web |
| Own-class onboarding and course materials need integrated release acceptance | Teachers must be able to bring their own class and PDFs | Class factory and map/material integration exist on the course feature branch; retain beta demos and verify fresh own-class workflows before rollout |
| Input capture still requires web workflow | Teachers often have seconds after class | Voice memo / Telegram capture after core value is validated |

## Product Roadmap Themes

### v1 - Prove The Core Memory Loop

Enabled today: a teacher can log lessons into reviewed class memory and create
the next lesson plan from that memory.

Success criterion: the teacher can complete one weekly loop: teach -> update
memory -> plan next lesson.

### v1.1 - Make The Core Loop Trustworthy

Enable teachers to trust and reuse the output with less review effort.

Primary bets:

- harden the existing Railway beta deployment, persistence and operator recovery
- operator beta reports and daily review workflow
- evidence/source panel
- better class-home briefing
- plan quality review
- test/exam generation as a first-class artifact
- visible memory/profile suggestions
- proactive input-vs-wiki reconciliation, starting with roster/name mismatches
- targeted session persistence if real usage exposes restart pain

### v1.2 - Make Onboarding And Memory Creation Easy

Make KlassenPilot useful on day one, not only after weeks of logged lessons.

**Shipped (in-plan materials slice):** PDF textbook/personal upload in Create
lesson plan, Mistral OCR 4 → session scratch → materials tools/cite/embed →
promote on plan save. OCR prompts assemble from class wiki + a STEM figure
library (Chemie, Physik, Biologie, Mathe) with a generic fallback. OCR runtime
is Mistral only — OpenAI vision/VLM and Docling are **not** working backups
(VLM is a code skeleton; Docling is a later optional path).

Implemented on the course feature branch, awaiting integration/hosted acceptance:

- approved class course-network program for Chemie 8/9 NTG: class-owned
  `Lernbausteine`, reviewed curriculum adoption, standalone reviewed materials,
  graph/material enrichment, and automatic use in weekly planning. Product
  contract and PR map live in the
  [course-network design](superpowers/specs/2026-08-17-class-course-network-design.md)
  and [delivery program](superpowers/plans/2026-08-18-class-course-network-program.md);
  implementation and fresh-teacher local acceptance are recorded in
  [the course handoff](../implementation_plans/course_network/README.md)
- class wiki factory and guided class setup, with demo exploration retained and
  optional empty provisioning; custom class label, year and optional prior learning
- standalone chapter library, saved-plan PDF normalization, archive/restore,
  reviewed map corrections and explicit generation recovery

Remaining bets:

- teacher preference setup
- larger whole-book / year-start packaging beyond the bounded chapter workflow
- OCR backups: OpenAI vision/VLM (skeleton only), Docling later
- native Word/PPT/photo ingest and scratch GC; chapter page-range UI and background
  import recovery are present on the course feature branch
- inherited subject/grade setup: shared Chemistry framework plus a bounded
  teacher-adjustment page composed at runtime
- teacher-approved import from notes, worksheets, plans, and curriculum docs
  into durable memory (still not automatic from OCR)

### v1.3 - Expand The Agent's Knowledge Safely

Add reputable external knowledge without weakening class-memory trust.

Primary bets:

- trusted search over allowlisted sources
- source cards and adaptation notes
- resource suggestions for lessons
- broaden the subject teaching-practice library beyond chemistry
- extend curriculum grounding beyond Chemie 9 NTG (additional grades/subjects
  and richer trusted-source coverage); the Anthropic-adapted planning/
  differentiation procedure + LehrplanPLUS/KMK grounding for Chemie 9 NTG is
  already shipped — see Current Product State
- no automatic writes from external sources
- agent safety hardening before higher-risk tools: SDK guardrails where useful,
  teacher-visible output sanitization, OWASP ASI red-team discovery, and
  deterministic security evals
- lightweight EU/Germany product-boundary note: teacher copilot, not automated
  grading, placement, diagnosis, admission, or discipline

### v1.4 - Become Proactive

Move from teacher-pulled workflows to assistant-suggested next actions.

Primary bets:

- class brief on open
- small suggested-task stack
- stale open-loop detection
- post-commit follow-ups
- sparse-memory detection
- next-best teaching action

### v1.5 - Add Low-Friction Capture

Let teachers capture useful class memory in the moment.

Primary bets:

- voice memo ingestion
- Telegram or similar messaging capture
- transcript-to-memory draft
- quick admin notes and follow-up capture
- teacher review before durable writes

### v1.6 - Broaden Into Teaching Logistics

Reduce more of the operational work around teaching.

Primary bets:

- homework/follow-up tracking
- assessment calendar
- report-comment drafts
- parent/admin communication drafts
- class content organization
- multi-week lesson sequence planning

### v2 - Student Learning Copilot

Extend the class-memory foundation into a student-facing formative learning
assistant. Students see a strict student-visible lens over class memory and
materials, maintain separate per-student learning memory, work through wrong
answers after returned problem sets, and prepare for exams through active
recall, spaced repetition, and adaptive problem pathways.

This is a strategic expansion after the teacher-side memory loop is proven. It
must not expose teacher-private wiki memory, let students mutate the teacher
wiki, or make official grading/high-stakes decisions.

## Product Guardrails

- Do not add autonomous wiki writes.
- Do not add broad multi-agent infrastructure before a workflow requires it.
- Do not make external web search the default memory path.
- Do not store real student names or sensitive student facts in broad profiles.
- Do not build school-admin SaaS foundations before teacher value is proven.
- Do not treat voice/Telegram as a substitute for validating the core workflow.

## Prioritization Rule

Prioritize work that most increases weekly teacher time saved while preserving
teacher trust. When in doubt, improve the class-memory loop, source visibility,
and artifact usefulness before expanding surface area.
