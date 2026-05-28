# KlassenPilot

Private teacher copilot for Gymnasium teachers. Log lessons through chat, review structured memory with human-in-the-loop approval, and generate lesson plans from accumulated class wiki memory.

## Architecture

- **Backend:** FastAPI + OpenAI (`backend/`)
- **Frontend:** Next.js + Tailwind (`frontend/`)
- **Memory:** Karpathy-style markdown wiki (`backend/teacher_wiki/`)
- **Contracts:** OpenAPI + JSON Schemas (`contracts/`)

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e .
copy ..\.env.example .env     # add OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 2. Frontend

Requires **Node.js 18+** with npm. Uses [assistant-ui](https://github.com/assistant-ui/assistant-ui) for chat and **shadcn-style** shared components (`components/ui/`).

```bash
cd frontend
copy ..\.env.example .env.local
npm install
npm run dev
```

Optional — refresh assistant-ui styled components from upstream:

```bash
npx assistant-ui@latest init
```

App: http://localhost:3000

### UI architecture

| Layer | Location | Purpose |
|---|---|---|
| Design tokens | `src/app/globals.css` | shadcn CSS variables |
| Primitives | `src/components/ui/` | Button, Card, Textarea, Checkbox, … |
| Layout | `src/components/layout/` | AppShell, PageHeader |
| Domain | `src/components/klassenpilot/` | Timeline, checklist, wiki cards |
| Chat | `src/components/assistant-ui/` | Thread + IngestRuntimeProvider → FastAPI |

## Workflows (v1)

1. **Landing** → select Chemie 9b
2. **Class home** → lesson timeline + status
3. **Update memory** → chat with agent → review diary MD + wiki files → save
4. **Create lesson plan** → generate from wiki memory

## Wiki layout

```text
teacher_wiki/
  raw/classes/{class_id}/           # immutable approved diaries
  wiki/classes/{class_id}/
    lessons/{YYYY-MM-DD}/
      lesson_results.md
      lesson_plan.md
    course_state.md, student_notes.md, misconceptions.md, open_loops.md
```

## Environment

| Variable | Where | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | backend/.env | OpenAI API (required for chat/plan) |
| `OPENAI_MODEL` | backend/.env | Default `gpt-4o-mini` |
| `WIKI_ROOT` | backend/.env | Path to teacher_wiki |
| `NEXT_PUBLIC_API_BASE_URL` | frontend/.env.local | Backend URL |

## v1.1 (planned)

- Test questions and exam generation
- Chat-driven wiki personalization (`class_config.md` custom sections)
