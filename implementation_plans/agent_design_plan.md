# Agent Design Plan

## Purpose

This document is the living design note for the teacher copilot agent. It captures
the current MVP direction, the useful lessons from the Karpathy-style LLM wiki
pattern and AutoSci reference agent, and the items intentionally deferred until
after the prototype behavior is reliable.

The MVP focuses on two polished workflows:

- Lesson planning
- Memory update for the teacher wiki

The agent should stay simpler than AutoSci. It is one teacher-facing assistant
using class-scoped wiki memory, with explicit teacher actions for saving lesson
plans and updating memory.

## Key Learnings

- Use the compiled wiki as persistent working memory, not just retrieval storage.
- Start each planning session with a base context pack.
- Browse the wiki only when the teacher request exceeds the base pack.
- Separate read-only planning from write/update actions.
- Report missing or sparse memory honestly.
- Copy AutoSci's discipline, not its full machinery.
- Use deterministic, source-bearing retrieval as a pathfinder; keep query packs
  small, purpose-specific, and rebuildable.
- Prefer compact compiled memory plus ranked evidence over flat top-k dumping.

The most important AutoSci pattern is not a large agent architecture. It is the
operating discipline: each workflow has a clear read/write contract, bounded
retrieval, evidence-grounded synthesis, and explicit handoff before mutations.

The useful 2026 retrieval lesson is that a Karpathy-style wiki does not remove
the need for search. The wiki is the readable map; deterministic pathfinder
tools are the compass. Current best practice is small high-signal context,
just-in-time retrieval, compact durable memory, and source-bearing tool results.
OpenAI-style tool/context guidance, Anthropic context-engineering guidance,
LlamaIndex's short-term versus long-term memory split, and recent agent-memory
research all point in the same direction: avoid dumping flat top-k context into
the model; first isolate reusable facts and ranked candidate pages, then let the
LLM synthesize from selected evidence.

For this MVP, AutoSci is the best local reference for this behavior. We should
borrow its deterministic corpus/ranking and purpose-specific query-pack pattern:
tokenize content, weight titles/frontmatter/compiled pages higher than raw body
text, return a small ranked list with provenance, and compile workflow-specific
context packs under a fixed budget. We should not copy AutoSci's graph engine or
multi-agent research workflow unless the class wiki grows enough to prove that
need.

For the teacher copilot, this means lesson planning should browse and cite class
memory, but it should not silently update the wiki. Memory updates remain a
separate teacher-approved workflow.

The reviewable behavior contracts live in `implementation_plans/agent_contracts.md`.
When agent behavior changes, update that file first or in the same change as the
code.

## Current MVP Plan

- Keep the existing OpenAI Agents SDK loop and assistant-ui integration.
- Improve the lesson-planning prompt and tool policy.
- Add focused range-aware wiki browsing tools:
  - list lessons by date/topic
  - read one lesson
  - read a compact lesson range
  - search/read class memory
- Use AutoSci-style deterministic retrieval for broad topic lookup:
  - build a class-scoped relevance corpus from index rows, compact memory,
    roll-ups, and lesson pages
  - rank with BM25-style lexical scoring and stable tie-breaks
  - return path, kind, title, snippet, score, matched terms, and source
- Add purpose-specific read-only query packs for planning, ingest, and review
  so the model gets the right map before broader browsing.
- Use lightweight inline citations in generated plans.
- Ask one targeted question when memory is sparse or missing for the teacher's
  requested range.
- Fix only planning-path backend issues touched by this work.

The target behavior is:

> The agent starts with recent class context, detects when the teacher's request
> needs older or broader memory, browses the class wiki by date/topic, then
> produces a practical lesson plan or assessment draft grounded in the lessons it
> actually found.

## Out of Scope for MVP

- AutoSci-style graph.
- Full evidence API/UI source panel.
- Multi-agent review pass.
- Broad wiki lint/check system.
- Raw-source fallback as normal behavior.
- Big schema, vector database, or opaque semantic index redesign.
- Non-planning backend hardening unless touched by the browsing work.

## Later Todos

- Add optional source panel or evidence metadata.
- Add wiki health check/lint operation.
- Add lightweight plan review after core behavior is stable.
- Consider typed index improvements.
- Consider graph/neighborhood browsing only if the wiki grows enough to need it.
- Harden ingest approval flow separately.

## Assumptions

- This folder uses snake_case: `implementation_plans`.
- This document should summarize decisions, not duplicate every detail from chat.
- This is a planning artifact, not production documentation.
- No code changes are included in this documentation step.
