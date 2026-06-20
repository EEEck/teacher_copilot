# How the Copilot Works

**So what:** Understanding draft vs save and how memory is loaded helps you trust the copilot without treating it like a blank chatbot.

KlassenPilot is agent-backed, but the product contract is **teacher-controlled**. It should behave like a careful colleague with access to the class notebook.

## Class memory first

The copilot starts from approved class memory:

- recent lessons and what has been taught so far
- short planning summary, misconceptions, open loops
- class teaching patterns and your preferences

It should not make you restate the same context in every chat.

## Memory in plain language

Not all memory has the same job:

| Layer | Purpose |
|-------|---------|
| **Long-term memory** | The approved class notebook — reliable enough to use next week |
| **Compact memory** | The short version loaded often — what matters right now |
| **Task memory** | Temporary working state for this chat — target lesson, draft, open questions |
| **Evidence** | Detail the copilot can look up when exact lesson context is needed |

This keeps responses fast while still allowing careful lookup when your request depends on past class details.

> [!tip]
> When memory matters, the copilot should name the lesson or source it used — e.g. “based on the 2026-05-29 lesson notes.” Richer source panels are on the roadmap.

## Drafts are not writes

| Workflow | Draft updates | Durable writes |
|----------|---------------|----------------|
| Create lesson plan | Plan markdown | Save plan to a lesson date (separate action) |
| Update memory | Diary markdown | Commit after you approve proposed file changes |

Planning chat **never** writes wiki memory. Memory update chat **never** skips your review step.

## Working state during a chat

During a workflow, KlassenPilot tracks the current lesson target, open questions, evidence summaries, draft completeness, and planning decisions. That state helps the copilot continue without replaying a long chat or stuffing the whole wiki into the prompt.

You may see **target/date status** above the memory workspace — if the date needs confirmation, confirm it before saving.

## Design principles (short)

> [!important]
> **Draft first, save after review.** Saving memory is a teacher action. Professional judgment enters at the review step.

> [!note]
> **Honest when memory is sparse.** If class memory is thin, the copilot should say so and ask one useful question — not invent classroom patterns.

> [!tip]
> **Stable patterns become suggestions.** When the copilot notices a recurring preference, it may suggest profile updates after you save a plan. Those suggestions are reviewable — not automatic writes.

## What it will not do

> [!warning]
> The copilot will not grade students, diagnose students, or make consequential student decisions. It is not an automated placement or discipline system.

Assessment generation as a dedicated workflow is on the roadmap. You can ask for quiz ideas inside a lesson plan today.

---

**Next:** [Help and FAQ](/docs/help) — common questions and fixes.
