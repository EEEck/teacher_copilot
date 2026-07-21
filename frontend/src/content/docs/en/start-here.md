# Start Here

KlassenPilot is a private AI assistant for teachers.

The long-term vision is simple: every class should have an assistant that knows where the class stands, keeps track of what matters, and helps prepare the next teaching step — so teachers spend less time on work around teaching and more time with students.

The current beta is narrower. KlassenPilot focuses on one core loop:

> update class reality → review what gets remembered → plan the next lesson

## How KlassenPilot works in this beta

KlassenPilot is not a blank chatbot. It combines four pieces:

1. **A strong AI model**
   It can reason, draft, summarize, and help plan in natural language.

2. **A private class database**
   Each class has its own structured notebook: lesson notes, saved plans, open loops, misconceptions, teaching patterns, and useful context.

3. **Agent skills**
   KlassenPilot can search the class notebook, draft a lesson plan, turn lesson conversations into class updates, and prepare proposed changes for review.

4. **Teacher approval**
   The assistant can suggest what to write or remember. You decide what becomes part of the durable class record.

> [!important]
> **KlassenPilot can suggest. You decide what gets remembered.**
>
> Nothing becomes durable class memory until you review and approve it.

### How lesson plans are grounded

Planning for the beta Chemie class is not “generic AI lesson text.” It combines:

1. **Your class notebook** — what this class has been taught, open loops, misconceptions, and preferences.
2. **An adapted open K–12 planning procedure** — based on Anthropic’s open lesson-planning and differentiation skills (Apache-2.0). Adapted into KlassenPilot; **not** a live Anthropic plug-in.
3. **LehrplanPLUS / KMK trusted sources** — official curriculum provenance. The planner should open the relevant section before making official curriculum claims.
4. **Teaching frameworks** — curated pedagogy summaries for Chemie 9 NTG (shared frameworks also cover Chemie 8/9 NTG). These are **not** legal curriculum text. Class overrides go in a small teacher-approved adjustments page; the shared frameworks stay immutable.

For the fuller breakdown (frameworks vs LehrplanPLUS vs class memory), see [How the Copilot Works](/docs/how-it-works#curriculum-grounding-chemie-9-ntg).

## What the beta tests

This beta answers one question:

> Can a teacher update class memory, trust what changed, and get a better next lesson plan because of it?

We are not testing whether AI can write a generic lesson plan. We are testing whether a class-specific assistant becomes more useful when it works from approved class context.

Your feedback should focus on the memory loop:

* Did KlassenPilot capture the right teaching facts?
* Did the proposed changes feel trustworthy?
* Did the next lesson plan actually use the class context?
* What felt wrong, missing, stale, or too much work?
* Where did you still have to repeat context?

The main walkthrough is in [Your first session](/docs/first-session).

## What to try first

Use the seeded **Chemie 9b** mock class. It already has lesson history, misconceptions, open loops, and saved plans, so you can test the product without entering real student data.

> [!blueprint]
> **Quick start**
>
> 1. Open Chemie 9b from the class list.
> 2. Scan the class home: unit, open loops, misconceptions, and timeline.
> 3. Create a lesson plan for the next class.
> 4. Save the plan to a lesson date.
> 5. After teaching, add lesson results from that planned lesson.
> 6. Review what KlassenPilot proposes to remember.

The full walkthrough is in [Your first session](/docs/first-session).

## What KlassenPilot is for

KlassenPilot helps with the work around teaching.

In this beta, it has two main jobs:

1. **Plan lessons from class context**
   It uses the class notebook, recent lesson sequence, open loops, and teacher preferences to draft a practical next lesson — grounded for Chemie 9 NTG via the adapted K–12 procedure, LehrplanPLUS/KMK sources, and curated teaching frameworks (see above).

2. **Update class reality**
   It helps capture what actually happened: what was covered, what students struggled with, what needs follow-up, and what should shape the next plan.

Over time, this should create a class record that becomes more useful every week.

Coming later: assessment generation, material adaptation, broader trusted-source search beyond the Chemie 9 NTG allow-list, voice or message capture, report drafts, and broader teaching logistics.

## What it is not

> [!warning]
> During beta, do not enter real student names or sensitive student records.
>
> KlassenPilot is not a grading system, student diagnosis tool, discipline system, or school administration platform.

Keep saved memory **class-level**, **pseudonymous**, and useful for teaching the next lesson.

KlassenPilot is also not a replacement for teacher judgment. It prepares, drafts, and suggests. The teacher decides what is correct, what is useful, and what gets saved.

---

**Next:** [Your first session](/docs/first-session) — a 20-minute Chemie 9b walkthrough.
