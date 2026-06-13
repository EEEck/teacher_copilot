# AI Agent Learning Guide

## Purpose

This document is for personal learning. It is not a product contract and not a
development checklist. It captures the agent-design lessons learned while
building KlassenPilot, reviewing the local Hermes and AutoSci reference repos,
and reading current agent memory/context guidance.

Use this as a self-contained study note when growing as an AI software engineer.
The shorter implementation source of truth is `agent_architecture.md`; the
behavior contract is `agent_contracts.md`. For repo-specific OpenAI Agents SDK
review notes, see `agent_sdk_practices_review.md`.

## The Core Mental Model

An AI agent is not just "an LLM with tools." A useful production agent is a
bounded system with:

- a clear user-facing job
- scoped context
- explicit tools
- a memory model
- retrieval strategy
- write boundaries
- validation and guardrails
- observability
- evaluation

For KlassenPilot, the right shape is one visible teacher copilot with tools and
strict boundaries, not a broad multi-agent graph.

The most important product rule is:

> The teacher should feel helped by accumulated class memory, but never lose
> control over durable writes.

## Agents, Workflows, And Tools

There are two common patterns:

- **Workflow**: fixed steps, deterministic control flow, predictable outputs.
- **Agent**: the model decides which tools to use and when, inside clear limits.

Most useful products mix both. KlassenPilot does this:

- Planning chat is agentic: the model can decide when to search or read memory.
- Wiki commit is workflow-like: validate, show diff, approve, write, reindex.
- Memory compaction uses LLM synthesis, but persistence is deterministic and
  path-restricted.

The OpenAI Agents SDK frames this well: `Agent` plus `Runner` manages turns,
tools, guardrails, handoffs, sessions, and traces, while run `context` is a
dependency-injection object passed to agents/tools and not shown to the model by
default. This matters because `class_id`, permissions, and write scope belong in
runtime context, not in model-generated text.

Important lesson:

> Use the LLM for judgment and synthesis; use backend code for authority,
> validation, paths, permissions, and persistence.

## Context Versus Memory Versus Retrieval

These terms are easy to blur.

**Context** is what the model sees in the current run: system prompt, user
message, loaded class pack, tool results, and current draft.

**Memory** is durable state that survives runs: wiki pages, compact memory,
profile conclusions, approved lesson records, saved plans.

**Retrieval** is how the agent finds relevant memory for the current task:
search, list lessons, read a date range, read a memory page.

**Compaction** turns detailed memory into smaller durable summaries. It is not
the same as retrieval. It is a maintenance step that makes future context
lighter and more personalized.

Good agents do not dump everything into the prompt. They:

1. load a small high-signal context pack
2. retrieve only when needed
3. cite or name the sources used
4. compact durable patterns separately

Anthropic's context-engineering guidance emphasizes memory outside the context
window, including file-based memory systems that help agents maintain project
state across sessions. LlamaIndex makes a similar distinction between
short-term memory, long-term memory blocks, and workflow context.

## The Karpathy Wiki Lesson

The Karpathy-style wiki idea is not "avoid search." It is:

> Store durable memory in human-readable, structured pages so both humans and
> agents can inspect, update, and navigate it.

The wiki is the readable map. Search and structured tools are the compass.

For a larger wiki, the agent needs:

- index pages and timelines
- compact roll-ups
- class-scoped search
- range-aware lesson readers
- source-bearing snippets
- a way to drill into full evidence pages

In KlassenPilot, this is why `search_memory` exists even though the wiki is
structured. The search tool is not the final answer source. It is the pathfinder
that helps the agent decide what to read.

## Hermes: Practical Memory Lessons

Local reference: `ref_repos/hermes-agent`.

Hermes is useful because it separates different memory problems:

- `tools/memory_tool.py`: small curated file-backed memory (`MEMORY.md` and
  `USER.md`). This is deterministic and bounded: the tool adds/replaces/removes
  controlled entries rather than letting the model freely rewrite memory.
- `tools/session_search_tool.py`: searchable session history using SQLite FTS.
  This is retrieval over prior conversations, not profile memory.
- `agent/context_compressor.py`: LLM-based compression of older active
  conversation context so the current session can continue.
- `plugins/memory/honcho/`: optional external memory/profile tooling.

The main learning:

> Do not treat "memory" as one thing. Separate curated facts, searchable
> history, compressed session context, and profile modeling.

For KlassenPilot, this maps to:

- curated wiki lesson memory
- compact memory pages
- deterministic class search
- optional future conversation summaries
- local Honcho-style `copilot_profile.md`

## AutoSci: Practical Retrieval And Wiki Lessons

Local reference: `ref_repos/AutoSci`.

AutoSci is useful because it treats the wiki as an operational knowledge base,
not a pile of documents. The important patterns are:

- structured wiki folders
- indexes and logs
- deterministic search/ranking helpers
- compiled context packs
- evidence packets
- citations and provenance
- lint/maintenance tools
- proposal/action separation

Useful local examples:

- `tools/research_wiki.py`: wiki entity operations, metadata search, context
  compilation, similar-concept lookup.
- `tools/discover.py`: deterministic wiki relevance scoring inspired by BM25.
- `tools/daily_arxiv.py`: profile extraction and topic/paper summaries.
- `wiki/`: readable durable research memory.

The lesson is not "copy AutoSci." AutoSci has research-specific graph,
multi-agent, and paper-discovery machinery that is too heavy for KlassenPilot.
The lesson is:

> Use durable memory, clear contracts, deterministic retrieval, evidence
> packets, and reviewable writes.

## Honcho-Style Memory

Honcho is an external memory system that stores user/agent messages, reasons
over them, and exposes memory through context, search, profile/representation,
and reasoning-style endpoints.

The interesting product idea is not only recall. It is modeling:

- who the user is
- user preferences
- recurring goals
- communication style
- what the agent has learned about the relationship
- what context matters now

For KlassenPilot, a local Honcho-style layer should answer:

> What should the copilot know about how this teacher and this class work?

Examples:

- "Teacher prefers concise 45-minute plans with Einstieg, practice,
  reflection."
- "Class 9b needs concrete examples before symbolic abstraction."
- "Peer checking reduces equation-balancing errors."
- "Do not move from ion charge to oxidation number without explicit contrast."

This is why `copilot_profile.md` exists. We are borrowing the concept, not
integrating the external Honcho service yet.

## Deterministic And Bounded Memory

This phrase caused confusion, so it is worth defining.

**Bounded** means memory writes are limited by size, scope, allowed paths, and
content type. For example: only write small profile conclusions under
`wiki/classes/{class_id}/memory/`.

**Deterministic** means backend code decides how persistence happens. The LLM
may propose content, but code validates class scope, paths, page names, size,
and write behavior. Running the same accepted write should have predictable file
effects.

The rationale:

- teachers need auditability
- student data requires strict boundaries
- model output is probabilistic
- durable memory can corrupt future behavior if it drifts
- safe writes should be explainable in code

So the best pattern is:

> LLM proposes, backend validates, teacher approves, code writes.

## Current KlassenPilot Implementation

The current implementation follows the tiered model.

Key files:

- `backend/app/teacher_agent/wiki/context_packs.py`: builds base, plan, ingest,
  and review context/query packs.
- `backend/app/teacher_agent/wiki/search.py`: builds a deterministic
  class-scoped relevance corpus and returns source-bearing ranked search
  results.
- `backend/app/teacher_agent/wiki/memory.py`: manages compact memory pages,
  local profile helpers, and compaction commits.
- `backend/app/teacher_agent/wiki/store.py`: facade exposing wiki helpers.
- `backend/app/teacher_agent/tools.py`: model-visible read tools.
- `backend/app/teacher_agent/prompts.py`: workflow prompts and tool policy.
- `backend/app/api/routes.py`: includes the memory compact endpoint.

Current memory pages:

- `taught_so_far.md`: compact year-to-date sequence
- `planning_brief.md`: open loops, readiness, priorities
- `teaching_patterns.md`: what has worked or failed
- `copilot_profile.md`: teacher/class/copilot profile
- `session_summaries.md`: optional compact session summaries

Current retrieval behavior:

- start with context packs
- use deterministic `search_memory` for broad topic lookup
- rank lesson and compact memory pages above generic pages
- return path, kind, title, snippet, score, matched terms, and source
- read lesson or memory pages for evidence before final synthesis

## Context Loading Pattern

KlassenPilot follows the same broad pattern as modern memory-oriented agents
such as Hermes, but keeps it local and workflow-specific:

1. **Profile layer**: inject small stable teacher/class preferences when they
   matter for the teacher-facing task. In lesson planning this is
   `teacher_profile.md` plus class `copilot_profile.md`, loaded through
   `build_profiles_assembly`.
2. **Task context layer**: build a compact workflow-specific context pack from
   the memory hierarchy. Lesson planning uses `build_plan_context_slim`, which
   includes subject guidance, `taught_so_far.md`, `planning_brief.md`,
   `teaching_patterns.md`, and `class_state.md` when present.
3. **Evidence layer**: do not dump full canonical wiki pages into the base
   prompt. Use tools such as `search_memory`, `list_lessons`,
   `read_lesson_range`, and `read_memory_page` when the teacher request needs
   exact details or older history.
4. **Runtime layer**: inject short-lived session state separately from durable
   memory. For planning this is `PlanRuntime`: phase, decisions, artifact
   state, evidence briefs, raw refs, and memory candidates.
5. **Trace layer**: expose the assembled context with source path, builder
   function, included flag, character count, and rendered text so humans and AI
   agents can debug what the model actually saw.

The point is not to load everything. The point is to load all small, stable,
high-signal context before the real task turn, then retrieve detailed evidence
only when the request calls for it.

For future teacher-facing workflows, define this explicitly before writing the
prompt: profile layer, task context pack, evidence tools, runtime state, and
trace shape. Avoid generic context dumps.

## Teacher Copilot Design Rules

For this product, the agent should:

- be class-scoped
- load class context automatically
- plan from recent lessons and compact memory
- browse older memory only when needed
- cite or name sources
- report sparse memory honestly
- ask at most one targeted clarifying question
- propose durable memory updates only when useful
- keep teacher corrections high-priority
- avoid sensitive student facts in broad memory
- never silently write wiki files

The three trust rules are:

1. No silent writes.
2. Honest gaps.
3. Visible evidence.

## Prompt And Tool Patterns

Good prompts are contractual. They define:

- role
- mode
- allowed tools
- forbidden actions
- evidence requirements
- sparse-memory behavior
- output shape

Good tool definitions are also contractual. OpenAI's function-calling guidance
is very practical here: tool names, descriptions, parameters, and schemas tell
the model what the tool does and when it should use it. If the model keeps
choosing the wrong tool, do not immediately add more prompt trigger phrases.
First ask whether the tool would pass the "intern test":

> Could a competent human use this tool correctly with only the name,
> description, parameters, and output shape?

If not, improve the tool interface.

For planning:

```text
Mode: LESSON_PLANNING_READ_ONLY.
Start from the plan context pack.
Use tools only when the request exceeds the pack.
For topic lookup, use search_memory as a pathfinder.
When memory influences the plan, cite or name the source.
Do not write wiki files.
If memory is sparse, say what was found and ask one targeted question.
```

For memory update:

```text
Mode: MEMORY_UPDATE_DRAFT_ONLY.
Extract only what the teacher stated or clearly implied.
Write diary_markdown only.
Do not commit wiki changes.
Durable writes happen through teacher-approved commit.
```

For compaction:

```text
Read approved wiki content only.
Synthesize compact memory pages.
Do not invent patterns from sparse data.
Return warnings when evidence is thin.
Backend code writes only allowed memory paths.
```

### Tool-Selection Lesson From The FCKW Trace

In the FCKW lesson-planning run, the teacher later asked for a "5 min review
session of the last 4 lectures" and wanted the plan to incorporate what students
had found confusing.

The first instinct was to add a hardcoded prompt rule:

```text
Browse when the teacher asks for "last N" or "recent N" lessons.
```

That worked, but it was the wrong direction. It does not scale because every
teacher phrasing would become another brittle trigger.

The better fix was:

- describe the agent's job as evidence-grounded planning
- say tools are chosen by information need, not keyword matching
- improve `list_lessons` so it clearly means "map the class lesson sequence"
- improve `read_lesson_range` so it clearly means "read evidence across several
  lessons for review, planning, tests, or recurring confusions"
- keep traces so we can inspect whether the tool choice actually improved

After moving behavior into tool descriptions, the agent selected
`read_lesson_range` immediately for the multi-lesson request and produced a
clean teacher-facing artifact without debug evidence blocks.

The pattern:

> Prompt describes the job and evidence standard. Tools describe capabilities.
> Backend validates scope and persistence. Traces reveal failures.

This is a better agent architecture than a growing list of phrase triggers.

## Retrieval Patterns

Basic retrieval methods:

- **Exact search**: stable and auditable, but brittle for natural language.
- **FTS/BM25-style lexical search**: deterministic, explainable, good MVP
  default.
- **Vector search**: useful for semantic paraphrase, but less transparent and
  requires more tuning.
- **Hybrid search**: combines lexical and semantic retrieval, useful later.
- **Graph search**: useful when relationships matter, but heavy early.

KlassenPilot currently chooses deterministic lexical ranking because it is:

- easy to audit
- offline and cheap
- enough for the current wiki size
- source-bearing
- predictable in tests

Embeddings or graph retrieval should come later only if deterministic wiki
retrieval shows measurable failures.

## Safety And Privacy

Teacher copilots are high-trust systems. The safety shape is:

- class isolation
- teacher approval for durable writes
- pseudonymous student ids
- data minimization
- no broad student profiling
- no emotion inference
- no automatic grading as default behavior
- clear audit/log behavior

The product should store only what helps instructional continuity. It should
avoid raw conversation transcripts as durable memory unless there is a specific
reviewed reason.

## Evaluation And Observability

Agents need evals because good demos can hide weak reliability.

Useful metrics:

- valid citation rate
- claim-with-evidence rate
- hallucinated prior-memory claim rate
- search result relevance for long teacher prompts
- tool calls per planning session
- sparse-memory question quality
- compaction warning rate
- teacher edit distance on generated plans
- approval/rejection rate for proposed memory updates
- cross-class leakage rate

OpenAI Agents SDK tracing and local CLI traces are useful for debugging tool
choices, context packs, and final outputs. Traces can contain sensitive class
memory, so local `runs/*.jsonl` files should be treated as disposable debug
artifacts.

The useful trace shape for KlassenPilot is:

```text
wiki/source file -> builder function -> compacted/rendered section -> prompt
tool call input -> raw output -> raw_ref -> evidence brief -> next prompt
```

The local plan trace endpoint now exposes this through `prompt_assembly` and
per-turn `prompt_assembly` events. This makes it much easier to debug agent
behavior than looking only at the final answer.

## Anti-Patterns

Avoid these:

- huge prompt dumps instead of scoped context packs
- vector search as a default before lexical retrieval is exhausted
- model-written files without backend validation
- hidden memory updates during normal chat
- broad multi-agent graphs before the workflow needs them
- storing raw transcripts as long-term memory
- profile facts without source or teacher confirmation
- asking multiple broad clarifying questions
- citing sources the agent did not actually read

## Study Path For An AI SWE

1. Learn the difference between workflow, agent, tool, handoff, context, memory,
   retrieval, and compaction.
2. Read the current KlassenPilot `product_vision.md`, `agent_architecture.md`,
   and `agent_contracts.md`.
3. Trace one planning run and inspect context packs plus tool calls.
4. Read Hermes memory files:
   - `tools/memory_tool.py`
   - `tools/session_search_tool.py`
   - `agent/context_compressor.py`
   - `plugins/memory/honcho/`
5. Read AutoSci retrieval/wiki files:
   - `tools/research_wiki.py`
   - `tools/discover.py`
   - `tools/daily_arxiv.py`
   - `wiki/index.md`
6. Compare those patterns to KlassenPilot:
   - `wiki/search.py`
   - `wiki/context_packs.py`
   - `wiki/memory.py`
   - `tools.py`
   - `prompts.py`
7. Build one small improvement with tests: a better context pack, a safer write
   check, or a retrieval ranking test.

## Source Notes

Public references:

- Anthropic, "Effective context engineering for AI agents":
  https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- OpenAI Agents SDK docs:
  https://developers.openai.com/api/docs/guides/agents
- OpenAI Agents SDK guardrails and human review:
  https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
- OpenAI Agents SDK running agents:
  https://developers.openai.com/api/docs/guides/agents/running-agents
- LlamaIndex agent memory docs:
  https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/memory/
- Honcho docs:
  https://honcho.dev/docs/v2/documentation/introduction/overview
- Agentic Context Engineering paper:
  https://arxiv.org/abs/2510.04618
- "Is Agent Memory a Database?" paper:
  https://arxiv.org/abs/2605.26252

Local references:

- `ref_repos/hermes-agent`
- `ref_repos/AutoSci`
- `backend/app/teacher_agent/wiki/`
- `backend/app/teacher_agent/prompts.py`
- `backend/app/teacher_agent/tools.py`

Historical note:

An older long-form teacher-copilot best-practices memo has been deleted. Its
practical lessons have been condensed here and in `agent_architecture.md`.
