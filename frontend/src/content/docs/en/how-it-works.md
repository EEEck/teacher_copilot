# How the Copilot Works

**So what:** Understanding draft vs save and how memory is loaded helps you trust the copilot without treating it like a blank chatbot.

KlassenPilot is agent-backed, but the product contract is **teacher-controlled**. It should behave like a careful colleague with access to the class notebook.

## Design: why it feels class-aware

KlassenPilot is designed to feel less like a blank chatbot and more like a private assistant who already prepared before helping.

It combines four parts:

1. **A best-in-class reasoning model**
   KlassenPilot uses a strong OpenAI reasoning model to understand teacher requests, plan multi-step work, draft lesson artifacts, and decide when it needs more context.

2. **An agent framework with teaching skills**
   The model is not only chatting. It can use specific skills, such as searching class memory, reading lesson notes, drafting a plan, preparing lesson results, and proposing memory updates for review.

3. **A private class database**
   Each class has its own structured knowledge base: lesson history, saved plans, open loops, misconceptions, class state, teacher preferences, and useful source material. This is the class file the copilot works from.

4. **A teacher approval gate**
   The agent may draft or suggest changes, but it does not silently change durable class memory. The teacher reviews what changed and decides what gets saved.

The important design choice is context loading.

KlassenPilot does not paste the entire class database into every chat. Instead, it starts with the most useful current briefing: what was taught recently, what matters now, known open issues, and relevant teacher preferences. If the conversation needs more detail, the agent can search the class database and pull in the exact lesson, plan, or note it needs.

That is what creates the executive-assistant feeling: the copilot starts prepared, keeps track of the current task, and can fetch the right background without making the teacher repeat everything.

## Class memory first

The copilot starts from approved class memory:

- recent lessons and what has been taught so far
- short planning summary, misconceptions, open loops
- class teaching patterns and your preferences

It should not make you restate the same context in every chat.

## How the Agents remembers 

KlassenPilot does not remember everything in one big pile. It keeps a few kinds of notes, each with a different job.

| Memory type               | What it means                                                                                                                     |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **Living class notebook** | The approved record of the class: lessons, plans, open loops, misconceptions, and what should matter next time                    |
| **Current class state**   | The short briefing KlassenPilot loads often: where the class stands right now, what was taught recently, and what needs attention |
| **Teacher preferences**   | Stable things about how you like to plan: structure, tone, level of detail, recurring corrections, and teaching style             |
| **Assistant notes**       | Small reminders that help KlassenPilot behave better: what worked before, what to avoid, and how to respond more usefully         |
| **Sources and evidence**  | Specific lesson notes, saved plans, or uploaded materials KlassenPilot can look up when exact context matters                     |

The goal is simple: when you open a class, KlassenPilot should already know the useful context — without forcing you to explain everything again.


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
