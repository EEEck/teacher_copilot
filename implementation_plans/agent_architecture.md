# Agent Architecture And Learnings

## Purpose

This is the current architecture and learning note for the KlassenPilot teacher
copilot. It explains how the agent should behave, how memory is organized, and
which lessons from AutoSci, Hermes, Honcho-style memory, and current agent
practice are relevant to this product.

Product scope lives in `product_vision.md`. Feature sequencing lives in
`product_backlog.md`. Reviewable behavior contracts live in `agent_contracts.md`.

## Core Operating Model

KlassenPilot should use one visible teacher copilot with clear workflow
boundaries, not a broad multi-agent graph.

- Planning is read-only with respect to the wiki.
- Memory update can draft lesson memory, but durable wiki writes happen only
  through teacher-approved commit or explicit revise actions.
- The model receives small class-scoped context packs, then browses only when
  the teacher request needs older or broader evidence.
- The backend owns class scope, allowed paths, write validation, and persistence.
- The agent should cite or name the class memory it uses.

This keeps teacher trust high: no silent writes, no invented class history, and
no opaque memory claims.

## Memory Architecture

The product uses tiered class memory.

1. **Canonical wiki memory**
   Approved lesson records, saved plans, roll-ups, subject guides, open loops,
   misconceptions, and pseudonymous student observations.

2. **Compact class memory**
   Derived pages under `wiki/classes/{class_id}/memory/`:
   `taught_so_far.md`, `planning_brief.md`, `teaching_patterns.md`,
   `copilot_profile.md`, and `session_summaries.md`.

3. **Workflow context packs**
   Read-only packs for base class chat, lesson planning, ingest, and review.
   These are rebuilt from the wiki and compact memory rather than stored as
   separate durable state.

4. **Local Honcho-style profile**
   A bounded profile of stable teacher/class/copilot facts: preferences,
   recurring goals, communication style, class learning profile, planning
   patterns that worked, avoid/watch rules, and teacher corrections.

The wiki remains the source of truth. Compact memory is derived and rebuildable.
The profile should be small, stable, class-scoped, and source-backed where
possible.

## Retrieval Architecture

The Karpathy-style wiki is the readable map; deterministic retrieval tools are
the compass.

For larger wiki memory, the agent should not rely on a flat dump of pages or an
opaque vector top-k result. It should:

- start from compact class context
- use `search_memory` as a deterministic pathfinder for broad topic requests
- return source-bearing ranked results with `path`, `kind`, `title`, `snippet`,
  `score`, `matched_terms`, and `source`
- drill into specific lessons or memory pages when snippets are not enough
- synthesize only after selected evidence is loaded

AutoSci's useful pattern is deterministic, purpose-specific retrieval:
weighted corpus fields, stable scoring, source paths, evidence packets, and
small compiled context packs. We should borrow that discipline, not the full
research graph or multi-agent orchestration.

## Workflow Context

The agent should use purpose-specific context packages.

- `base_class_context`: subject, class configuration, current unit, curriculum
  direction, core misconceptions, open loops, recent timeline, compact profile.
- `plan_context`: base context plus last taught lessons, recent saved plans,
  taught-so-far summary, teaching patterns, planning preferences.
- `ingest_context`: base context plus previous lesson, student index excerpt,
  logging conventions, compact class memory, open loops.
- `review_context`: compact sequence, recurring misconceptions, unresolved
  issues, and relevant lesson range.

The teacher should not have to restate class state in each chat. The model
should receive enough context to start well and use tools for the long tail.

## Best-Practice Learnings

- Keep active context small and high-signal.
- Prefer just-in-time retrieval over loading the whole wiki.
- Separate short-term conversation state from long-term class memory.
- Keep memory writes deterministic, bounded, and auditable.
- Let LLM synthesis propose compact updates; let backend code validate and
  persist allowed paths.
- Treat explicit teacher corrections as high-priority memory.
- Prefer stable reusable facts over raw session logs.
- Keep student-specific sensitive details out of broad profile memory.
- Use source-bearing retrieval so the teacher can audit the plan.
- Add embeddings or vector search only after deterministic wiki retrieval shows
  measurable limits.

## Deliberate Non-Goals

- Full AutoSci graph or edge schema.
- Multi-agent review pipeline.
- External Honcho service as the default memory layer.
- Vector database as the default retrieval path.
- Autonomous wiki writes.
- Raw-source fallback as normal planning behavior.
- Grading automation without teacher review.

## Implementation Map

- Agent prompts: `backend/app/teacher_agent/prompts.py`
- Agent tools: `backend/app/teacher_agent/tools.py`
- Agent runner: `backend/app/teacher_agent/agents.py`
- Structured outputs: `backend/app/teacher_agent/models.py`
- Wiki facade: `backend/app/teacher_agent/wiki/store.py`
- Wiki retrieval: `backend/app/teacher_agent/wiki/search.py`
- Context packs: `backend/app/teacher_agent/wiki/context_packs.py`
- Compact memory: `backend/app/teacher_agent/wiki/memory.py`
- Wiki schema rules: `backend/teacher_wiki/AGENTS.md`

## Testing Expectations

Agent and memory tests should stay offline and deterministic.

Use focused backend tests when changing agent memory or retrieval:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_wiki_tools.py tests\test_wiki_search.py tests\test_api_plan.py tests\test_prompts.py tests\test_api_stream.py tests\test_wiki_context_packs.py tests\test_memory_compaction.py
```

From repo root, use:

```powershell
.\scripts\test.ps1
```
