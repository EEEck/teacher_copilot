# Teacher Wiki Browsing Plan

## Summary

Improve the lesson-planning agent's ability to browse class wiki memory while
keeping the MVP small. The goal is not a general research-agent platform. The
goal is one polished behavior: when a teacher asks for older context, a date
range, or an assessment spanning multiple lessons, the agent detects that the
base context pack is insufficient and fetches the missing class memory.

## MVP Scope

- Keep the existing OpenAI Agents SDK loop and assistant-ui integration.
- Keep the base planning context pack for normal next-lesson planning.
- Add focused range-aware wiki browsing tools for lesson planning.
- Use lightweight inline citations in generated plans.
- Ask one targeted question when class memory is sparse or incomplete.
- Fix only planning-path backend issues touched by the browsing work.

## In Scope

- `list_lessons`: list class lessons by date range and optional topic.
- `read_lesson`: read one lesson by date.
- `read_lesson_range`: read a compact packet for multiple lessons.
- `search_memory`: search class memory index-first.
- `read_memory_page`: read one class-scoped wiki page.
- Prompt policy that tells the model when to browse and when not to browse.
- Planning-path safety fixes, including stream result isolation and store method
  defaults needed by the tools.

## Out of Scope

- AutoSci-style graph.
- Full evidence API or UI source panel.
- Multi-agent review/sanity pass.
- Broad wiki lint/check system.
- Raw-source fallback as normal behavior.
- Large schema or index redesign.
- Non-planning backend hardening unless touched by this work.

## Agent Behavior

The agent should:

1. Start from the base context pack.
2. Decide whether the teacher request is fully covered by that pack.
3. Browse class memory when the request asks for older lessons, a date range,
   a topic not visible in the pack, or a test/quiz over prior weeks.
4. Prefer range tools for range requests instead of repeated single-page reads.
5. Cite the lessons or memory pages it uses inline in the generated plan.
6. State sparse-memory gaps honestly and ask at most one targeted question.
7. Never write wiki files directly during planning.

## Later Todos

- Add optional evidence metadata to the API for a future source panel.
- Add a wiki health-check operation.
- Add lightweight plan review after browsing/generation behavior is stable.
- Consider typed index improvements if the wiki grows.
- Consider graph/neighborhood browsing only when simple range/topic tools are
  no longer enough.
