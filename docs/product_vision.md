# KlassenPilot Product Vision

## North Star

KlassenPilot is a private, class-scoped teaching copilot that learns how a
teacher teaches a specific class and uses that memory to make the next teaching
step easier.

The product should feel like:

> A teacher opens a class, and the copilot already knows what was taught, what
> the class is struggling with, what worked last time, and how this teacher likes
> to plan.

The durable product thesis remains:

> Every approved lesson update makes the copilot more useful for future lessons.

## User Promise

For each class, the teacher should expect the agent to understand:

- the subject, school year, current unit, and curriculum direction
- the recent lesson sequence and what has been taught so far
- open loops, recurring misconceptions, and assessment readiness
- class-level learning patterns and teaching moves that worked
- the teacher's planning preferences and communication style
- previous corrections the teacher gave the copilot

The teacher should not have to restate this context in every chat. The agent
should load the relevant class memory automatically, then browse additional wiki
evidence when the request needs older or broader context.

## Product Shape

The app has three product layers.

1. **Class workspace**
   The class home is the teacher's entry point. It shows timeline, status,
   compact memory, open loops, and eventually proactive suggested tasks.

2. **Teacher workflows**
   The core workflows are:
   - update memory from a lesson conversation
   - create a lesson plan from class memory
   - later: generate tests/exams, reports, and resource adaptations

3. **Class copilot memory**
   The wiki is the canonical memory. Compact memory pages and a local
   Honcho-style profile make the copilot fast, personal, and consistent.

## Memory Model

KlassenPilot uses a tiered memory model.

- **Canonical wiki memory**
  Approved lesson records, saved plans, roll-ups, misconceptions, open loops,
  student notes, and subject guides. This is the source of truth.

- **Compact class memory**
  Derived pages under `wiki/classes/{class_id}/memory/`, including
  `taught_so_far.md`, `planning_brief.md`, `teaching_patterns.md`,
  `copilot_profile.md`, and `session_summaries.md`.

- **Workflow context packs**
  Read-only packs for base class chat, lesson planning, memory update, and
  review. These keep the active prompt small and purpose-specific.

- **Honcho-style copilot profile**
  A bounded local profile that stores stable teacher/class/copilot conclusions:
  preferences, recurring goals, communication style, class learning profile,
  planning patterns that worked, avoid/watch rules, and useful teacher
  corrections.

Memory should be class-scoped. Individual student memory should stay
pseudonymous and should not leak into broad teacher/class profile facts.

## Expected Agent Behavior

The agent should behave like a careful teaching colleague with access to the
class notebook.

- On class entry, it starts from the base class context.
- For planning, it loads recent lessons, compact memory, teaching patterns,
  open loops, and planning preferences.
- For memory update, it loads the previous lesson, logging conventions, compact
  memory, student index excerpt, and open loops. It may also start from a
  timeline/detail lesson hint, but the backend-owned runtime still tracks
  whether the date/lesson target is confirmed.
- For broad topic requests, it uses deterministic `search_memory` as a
  pathfinder, then reads the relevant lesson or memory pages.
- When it uses memory, it names or cites the source lesson/page.
- When memory is sparse, it says so and asks at most one targeted question.
- When it sees a durable pattern, it may propose a profile update for teacher
  review.

The agent should not silently rewrite the wiki, invent classroom patterns, or
store sensitive student-level conclusions in broad profile memory.

## Product Scope

### Current product scope

- One teacher, local/private deployment
- Multiple class ids supported by code, with `chemie_9b_2026_27` as the seed
  fixture
- Class-scoped markdown wiki memory
- Update memory with teacher-approved commits
- Timeline/detail shortcuts for adding or correcting lesson results without
  turning Update Memory into a wizard
- Create lesson plan with read-only wiki access
- Compact memory compaction endpoint
- Deterministic source-bearing wiki retrieval
- Query packs for planning, ingest, and review

### Near-term scope

- Make class home a useful briefing surface
- Surface one or two evidence-backed suggested tasks
- Improve lesson planning and test/exam generation
- Add lightweight source/evidence UI metadata
- Make profile updates visible and reviewable
- Add sparse-memory and stale-open-loop hygiene

### Out of scope until demand is proven

- Autonomous wiki writes
- Always-on external messaging
- Multi-user school admin platform
- Real student names
- Grading automation without teacher review
- Full AutoSci graph or multi-agent orchestration
- External Honcho dependency as the default memory layer
- Vector database as the default retrieval path

## Success Criteria

The product is working when:

- a teacher can open a class and immediately see useful class state
- a lesson plan reflects recent lessons, misconceptions, and teacher style
- memory updates improve future planning without hidden writes
- the agent can explain what memory it used
- compact memory stays small, stable, class-scoped, and rebuildable
- the teacher feels less like they are prompting from scratch each time

## Relationship To Other Docs

- `agent_contracts.md` defines behavior contracts and safety boundaries.
- `agent_architecture.md` explains the agent architecture and retrieval lessons.
- `product_backlog.md` tracks versioned feature direction.
