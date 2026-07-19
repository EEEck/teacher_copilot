# Reviewed Source Citation Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Discuss answers present English trusted-wiki material as a reviewed KlassenPilot summary, with a backend-owned link to the official German source and one bounded correction attempt for invalid model-written citations.

**Architecture:** Trusted-source reads already record `{source_id, section_id}` in `ClassDiscussionRuntime`. A pure citation helper will validate model-written citation syntax and build a teacher-facing footer by resolving only those recorded source references through `WikiStore`. `AgentRunner` will run one correction turn only when validation rejects a draft; after a second invalid draft, it removes model-written source lines and relies on the generated footer.

**Tech Stack:** Python, Pydantic, OpenAI Agents SDK, pytest.

## Global Constraints

- Keep English source-wiki content as reviewed, teacher-usable summaries; do not claim it is a verbatim official German quote.
- Build title, section, and canonical URL only from the linked trusted-source registry.
- Do not add runtime web browsing or new durable wiki writes.
- Cap correction at one additional model turn; keep a backend footer as the safe fallback.

---

### Task 1: Create deterministic citation presentation helpers

**Files:**
- Create: `backend/app/teacher_agent/citation_presentation.py`
- Test: `backend/tests/test_citation_presentation.py`

**Interfaces:**
- Produces `validate_discussion_source_presentation(reply, consulted_sources) -> list[str]`.
- Produces `render_reviewed_source_footer(wiki, class_id, consulted_sources) -> str`.

- [x] Write failing tests for a model URL/unread `Source:` citation and for a footer rendered from `by-lehrplanplus-chemie-9-ntg#c9_atombau`.
- [x] Run the new test module and verify failure before implementation.
- [x] Implement validation that rejects model-written URLs and citations not read in the session; implement a footer labelled `KlassenPilot reviewed English summary` with the registry title, German section title, and canonical URL.
- [x] Run the test module and verify it passes.

### Task 2: Add bounded Discuss correction and fallback

**Files:**
- Modify: `backend/app/teacher_agent/agents.py`
- Modify: `backend/app/teacher_agent/prompts.py`
- Test: `backend/tests/test_class_brief_discussion.py`

**Interfaces:**
- Consumes the Task 1 validator/footer and `ClassDiscussionRuntime.consulted_sources`.
- Produces a final Discuss reply with one correction retry or a safe footer-only source presentation.

- [x] Write failing tests showing an invalid first reply is retried once and a valid reply receives the rendered footer.
- [x] Run the focused test and verify failure before implementation.
- [x] Update Discuss instructions: English wiki text is a reviewed summary, not an official quotation; the model must not render source URLs because the backend does so.
- [x] Implement one correction prompt carrying the rejected draft and errors; on repeated failure strip model `Source:` lines/URLs and append the deterministic footer.
- [x] Run focused Discuss and citation tests and verify they pass.

### Task 3: Validate and commit

**Files:**
- Modify: `docs/superpowers/plans/2026-07-18-reviewed-source-citation-contract.md`

- [x] Run `pytest tests/test_citation_presentation.py tests/test_class_brief_discussion.py tests/test_wiki_tools.py -q` (the modules passed individually; one combined invocation timed out in the runner without reporting a test failure).
- [x] Run focused Ruff and `git diff --check`.
- [x] Run a live source-grounded Discuss validation: the authenticated trace confirmed source-tool raw evidence; a fresh in-process runtime then confirmed recorded provenance and the backend footer. The authenticated beta draft was pre-existing and therefore not used to create a destructive fresh session.
- [x] Mark the plan complete and commit the tested slice on the current branch.
