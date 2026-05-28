# KlassenPilot MVP: Teacher Copilot Prototype PRD and Codex Build Plan

## 1. Product Summary

**Product name:** KlassenPilot MVP

**Concept:**  
A private teacher copilot for Gymnasium teachers that accumulates structured memory by **subject, class, lesson, and student observation**, then helps with lesson planning, class logistics, exam prep, and later grading.

**First prototype goal:**  
Build a local app where a teacher can:

1. Select a class, e.g. `Chemie 9b`
2. Paste rough lesson notes
3. Ask the agent to structure the notes
4. Review proposed memory updates
5. Save approved updates into a markdown wiki
6. Generate the next lesson from accumulated wiki memory

The core product thesis:

> Every lesson makes the teacher agent smarter.

---

## 2. Long-Term Vision

KlassenPilot should eventually become a **private teacher-level agent workspace** for Gymnasium teachers.

Long-term capabilities:

- Class logistics and teacher admin
- Lesson logging and class memory
- Lesson planning from previous lessons and class needs
- Student observation database
- Homework and open-loop tracking
- Exam question generation from the lesson graph
- Material ingestion via Docling
- Structured knowledge base via LLM Wiki
- Semantic search via pgvector
- Long-running agent jobs
- Notification when tasks are complete
- Review UIs for teacher approval
- Later: grading support, but always teacher-in-the-loop

The long-term product should feel like:

> “I hired a private teaching assistant who knows my classes, remembers what happened, and helps me plan the next step.”

---

## 3. First Prototype Scope

### In Scope

Build the smallest possible working prototype for one teacher and one class.

Initial class:

```text
Chemie 9b, school year 2026/27
```

Core workflows:

1. **Log Lesson**
   - Teacher pastes rough lesson notes.
   - Agent structures them into wiki updates.
   - Teacher reviews proposed changes.
   - Approved updates are written to the markdown wiki.

2. **Plan Next Lesson**
   - Teacher clicks “Generate next lesson plan.”
   - Agent reads the current class wiki memory.
   - Agent generates a 45-minute lesson plan based on class history, misconceptions, open loops, and teacher preferences.

### Out of Scope

Do not build these in the first prototype:

- Authentication
- Multi-user support
- School tenant/admin console
- pgvector
- Docling
- Grading
- Telegram notifications
- Calendar sync
- Student real names
- Complex React frontend
- Long-running production workflow engine

---

## 4. Recommended Prototype Stack

Use the fastest stack that still validates the architecture.

```text
Frontend:
  Streamlit

Backend:
  Python app

Agent runtime:
  OpenAI Agents SDK

Memory:
  Local markdown files using Karpathy-style LLM Wiki pattern

Storage:
  Local filesystem first

Optional later:
  SQLite
  Postgres
  pgvector
  Docling
  React / Next.js
```

Rationale:

- Streamlit is the fastest way to create a local working UI.
- OpenAI Agents SDK gives a clean agent loop, tools, and tracing.
- Filesystem markdown wiki is the fastest way to test persistent structured memory.
- pgvector and Docling are valuable later but not needed to validate the first loop.

---

## 5. Core Architecture

```text
Teacher action
→ Streamlit UI
→ OpenAI Agents SDK agent
→ read class wiki
→ propose structured memory updates
→ teacher approves
→ wiki files update
→ next lesson generated from wiki memory
```

The agent should not directly overwrite memory. It should always produce proposed updates first.

---

## 6. Memory Architecture

Use a Karpathy-style LLM Wiki.

The wiki has three conceptual layers:

```text
Raw notes:
  immutable teacher inputs

Curated wiki:
  structured markdown pages maintained by the agent

Log/index:
  navigation and change history
```

### Initial Folder Structure

```text
teacher_wiki/
├── AGENTS.md
├── index.md
├── log.md
├── teacher_profile.md
├── subjects/
│   └── chemie.md
└── classes/
    └── chemie_9b_2026_27/
        ├── course_state.md
        ├── lesson_graph.md
        ├── student_notes.md
        ├── misconceptions.md
        └── open_loops.md
```

### Later Folder Addition

After adding raw note preservation:

```text
teacher_wiki/
└── raw/
    └── chemie_9b_2026_27/
        └── YYYY-MM-DD_lesson_note.md
```

---

## 7. Wiki File Roles

### `teacher_profile.md`

Stores teacher-wide preferences.

Examples:

```text
- Prefers concise lesson plans.
- Likes 45-minute lessons with Einstieg, practice, and short reflection.
- Wants feedback and planning language in natural German.
```

### `subjects/chemie.md`

Stores subject-level reusable knowledge.

Examples:

```text
- Common Chemie lesson patterns
- Typical misconceptions
- Safety reminders
- Question templates
- Experiment planning notes
```

### `classes/chemie_9b_2026_27/course_state.md`

Current state of the class.

Examples:

```text
Current unit: Redox reactions
Current topic: Oxidation numbers
Overall class status: Needs more practice with notation
Next planned focus: Difference between oxidation number and ionic charge
```

### `lesson_graph.md`

Chronological lesson history.

Example:

```text
## 2026-09-21 — Introduction to Redox
Covered:
- Oxidation and reduction
- Electron transfer
- First examples

Observed:
- Students understood basic vocabulary
- Many confused oxidation number and charge

Homework:
- Worksheet 2, tasks 1–4
```

### `student_notes.md`

Pseudonymous student observations.

Example:

```text
## S-014
- Strong conceptual understanding
- Participates actively
- Needs occasional reminder to show units

## S-021
- Struggled with oxidation number notation
- Should receive extra scaffolded practice
```

### `misconceptions.md`

Recurring class-level learning gaps.

Example:

```text
- Many students confuse oxidation number with ionic charge.
- Some students think oxidation always requires oxygen.
```

### `open_loops.md`

Follow-ups the teacher/agent should remember.

Example:

```text
- Start next lesson with 5-minute diagnostic warmup on oxidation numbers.
- Revisit reducing agent vs oxidizing agent with concrete examples.
```

---

## 8. Core Screens

For the first prototype, build only four screens/sections:

```text
1. Class selector
2. Lesson log input
3. Proposed memory updates review
4. Next lesson planner
```

### Screen 1: Class Selector

Initial option:

```text
Chemie 9b — 2026/27
```

### Screen 2: Lesson Log Input

Textarea:

```text
What happened in today’s lesson?
```

Button:

```text
Structure lesson notes
```

### Screen 3: Proposed Memory Updates Review

Show proposed updates by target file:

```text
course_state.md
lesson_graph.md
student_notes.md
misconceptions.md
open_loops.md
```

Teacher can approve or reject.

### Screen 4: Next Lesson Planner

Button:

```text
Generate next lesson plan
```

Output:

```text
45-minute lesson plan
Learning goals
Lesson flow
Warmup
Practice tasks
Homework
Teacher notes
```

---

## 9. Agent Tools

Initial tools:

```text
read_wiki_file(path)
propose_wiki_update(path, update_text)
apply_approved_update(path, update_text)
append_log(message)
generate_lesson_plan(class_id)
```

Tool rules:

- The agent may read wiki files.
- The agent may propose updates.
- The agent may not directly write to wiki files.
- Writes happen only after teacher approval in the UI.
- Student notes must use pseudonymous IDs like `S-001`, `S-002`.

---

## 10. Agent Behavior Rules

System behavior:

```text
You are KlassenPilot, a private teacher copilot for a Bavarian Gymnasium teacher.

You help structure lesson notes, update class memory, and plan next lessons.

Always identify the class context first.
Never mix memories across classes unless explicitly requested.
Use class memory before general subject memory.
Use subject memory before generic knowledge.
Use teacher preferences when planning.
For memory updates, always propose changes instead of silently committing.
Use pseudonymous student IDs.
Do not infer sensitive student facts beyond what the teacher wrote.
Do not generate final grades.
Keep outputs practical, structured, and teacher-friendly.
```

---

## 11. Build Order

Recommended implementation sequence:

```text
1. Build Streamlit app and markdown wiki skeleton.
2. Add OpenAI Agents SDK agent.
3. Add lesson note → memory proposal.
4. Add approve/save workflow.
5. Add next lesson generation.
6. Add nicer UI.
7. Add raw note preservation.
8. Later add Docling, pgvector, email notifications, and React/v0 UI.
```

---

## 12. Codex Prompt 1: Initial Implementation

Paste this into Codex first:

```text
Build a minimal local prototype called KlassenPilot.

Goal:
Create a teacher-level AI copilot for Gymnasium teachers. The first prototype should support one class, Chemie 9b, and two workflows:
1. Log a lesson from rough teacher notes.
2. Generate the next lesson plan from accumulated class memory.

Use:
- Python
- Streamlit for UI
- OpenAI Agents SDK for the agent loop
- Local markdown files for memory
- No database yet
- No authentication
- No grading

Implement this folder structure:

teacher_wiki/
├── AGENTS.md
├── index.md
├── log.md
├── teacher_profile.md
├── subjects/
│   └── chemie.md
└── classes/
    └── chemie_9b_2026_27/
        ├── course_state.md
        ├── lesson_graph.md
        ├── student_notes.md
        ├── misconceptions.md
        └── open_loops.md

Build a Streamlit app with:
1. Sidebar class selector, initially only Chemie 9b.
2. Text area: “What happened in today’s lesson?”
3. Button: “Structure lesson notes.”
4. Agent returns proposed updates for:
   - lesson_graph.md
   - course_state.md
   - misconceptions.md
   - student_notes.md
   - open_loops.md
5. UI shows proposed updates before writing.
6. Button: “Approve and save memory.”
7. Button: “Generate next lesson plan.”
8. Lesson plan is generated from the current wiki files.

Important rules:
- The agent must not directly overwrite memory.
- It must propose changes first.
- Memory writes happen only after user approval.
- Student notes should use pseudonymous IDs like S-001, S-002.
- Keep the code simple and readable.
- Add a README with setup instructions.

Create the full initial implementation.
```

---

## 13. Codex Prompt 2: Refactor Architecture

Use after the first version runs:

```text
Refactor the prototype into a cleaner architecture.

Create these files:

app.py
teacher_agent/
  __init__.py
  agent.py
  tools.py
  wiki_store.py
  schemas.py
  prompts.py
teacher_wiki/
  ...

Requirements:
- schemas.py should define Pydantic models:
  LessonLogInput
  WikiUpdateProposal
  WikiUpdateBundle
  LessonPlan
- wiki_store.py should handle all file reads/writes.
- tools.py should expose safe tools for reading wiki files and preparing update proposals.
- agent.py should define the OpenAI Agents SDK agent.
- prompts.py should contain the system prompt.
- app.py should only contain Streamlit UI logic.

Keep functionality the same.
```

---

## 14. Codex Prompt 3: Add Karpathy-Style Wiki Behavior

```text
Add Karpathy-style LLM Wiki behavior.

Use these concepts:
- raw notes are preserved
- wiki pages are curated summaries
- index.md summarizes available wiki pages
- log.md records approved memory updates
- the agent should read index.md first before selecting class memory files
- after saving updates, append a concise timestamped log entry to log.md

Add:
teacher_wiki/raw/chemie_9b_2026_27/

When a lesson note is approved:
1. Save the raw note into raw/chemie_9b_2026_27/YYYY-MM-DD_lesson_note.md
2. Apply approved updates to wiki files
3. Update log.md
4. Optionally update index.md if new concepts/classes/files are introduced

Keep this simple and robust.
```

---

## 15. Codex Prompt 4: Improve UI

Use once the Python prototype works:

```text
Improve the Streamlit UI so it feels like a modern teacher copilot.

Add:
- A top-level title: KlassenPilot
- Class status card showing current unit, last lesson, open loops
- Two tabs:
  1. Log Lesson
  2. Plan Next Lesson
- In the proposal review, show one expandable section per target wiki file
- Add a small “Class Memory Snapshot” panel showing:
  - Current unit
  - Last 3 lesson graph entries
  - Top misconceptions
  - Open loops
- Keep the app local and simple.
```

---

## 16. Repos and Resources

### Agent Runtime

#### OpenAI Agents SDK

Repo:  
https://github.com/openai/openai-agents-python

Use for:

- Agent loop
- Tools
- Tracing
- Structured agent orchestration

### LLM Wiki / Memory

#### Karpathy LLM Wiki gist

URL:  
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

Use for:

- Core wiki memory pattern
- Raw notes → curated wiki → index/log

#### Astro-Han Karpathy LLM Wiki

Repo:  
https://github.com/Astro-Han/karpathy-llm-wiki

Use for:

- Wiki workflow inspiration
- Prompt rules
- Ingest/query/lint ideas

#### llmwiki.app

Repo:  
https://github.com/lucasastorian/llmwiki

Use for:

- Full-stack wiki app inspiration
- Document upload + wiki generation ideas

#### llm-wiki-skill

Repo:  
https://github.com/lewislulu/llm-wiki-skill

Use for:

- Agent skill packaging of LLM Wiki workflows

### Agent Architecture

#### 12-Factor Agents

Repo:  
https://github.com/humanlayer/12-factor-agents

Use for:

- Own the control flow
- Own the context window
- Keep agents small and focused
- Treat agent design as software engineering, not magic autonomy

### UI

#### Streamlit

Docs:  
https://docs.streamlit.io/

Use for:

- Fast local prototype UI

#### v0

URL:  
https://v0.app/

Use later for:

- Clean React/Next.js UI generation

#### shadcn/ui

URL:  
https://ui.shadcn.com/

Use later for:

- Modern UI components

### Future Ingestion

#### Docling

Repo:  
https://github.com/docling-project/docling

Use later for:

- Parsing PDFs, DOCX, PPTX, and structured classroom material

---

## 17. Future Roadmap

### Phase 0: Local Prototype

```text
Streamlit
OpenAI Agents SDK
Filesystem markdown wiki
One class
Lesson logging
Next lesson generation
```

### Phase 1: Better Teacher MVP

```text
Multiple classes
Student list
Class calendar
Lesson graph view
Exam question generation
Nicer UI
```

### Phase 2: Real App

```text
FastAPI backend
Postgres
pgvector
Object storage
Docling ingestion
User accounts
Email notifications
```

### Phase 3: Agentic Teacher Workspace

```text
Long-running jobs
Review artifacts
Memory approval queue
Skill proposals
Lesson-to-exam workflow
Parent/admin communication drafts
```

### Phase 4: Grading Support

```text
Rubric generation
Student answer ingestion
Teacher-reviewed grading suggestions
Feedback drafts
Audit trail
```

---

## 18. Success Criterion for First Prototype

The first prototype succeeds if:

```text
A teacher can paste one messy lesson note,
the agent turns it into structured class memory,
the teacher approves the update,
and the agent generates a better next lesson because it remembers what happened.
```

This validates the core product loop.
