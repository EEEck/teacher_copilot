# Help and FAQ

**So what:** Quick answers when something feels off — and a short list of what to report during beta.

## Frequently asked questions

### Can I use real student data?

For the beta, use the mock Chemie 9b class unless you have explicit permission for real data. **Do not enter real student names or sensitive student records.**

### What happens when I save memory?

KlassenPilot writes the teacher-approved file changes into the class wiki. Those changes can influence future planning.

### Can planning chat change the wiki?

No. Planning chat updates the plan draft only. It does not directly write class memory.

### Why did it ask for a lesson date?

Memory and plans need a lesson target. If the date is known from the timeline, KlassenPilot can use it. If unclear, it should ask you to confirm.

### Can it generate tests?

Assessment generation is on the roadmap. The beta focuses on Update memory and Create lesson plan. You can ask for quiz ideas inside a lesson plan, but there is not yet a dedicated test workflow.

### Can it review student work?

Not as a beta workflow. Future student-work support should remain teacher-reviewed and carefully scoped.

### How do I know what it used?

Plans should name relevant class memory — recent lessons, misconceptions, planning briefs. Official curriculum claims should point to LehrplanPLUS/KMK sections the planner actually opened. Teaching frameworks are curated pedagogy for Chemie 9 NTG, not a substitute for those official sources. Richer source panels are part of the beta roadmap. See [How the Copilot Works](/docs/how-it-works#curriculum-grounding-chemie-9-ntg).

### What if the backend restarts?

> [!warning]
> The prototype may lose server-side chat history after a backend restart. Drafts may remain in the browser, but the session can be recreated without full chat history.

## Troubleshooting

### Backend not reachable

If the class list does not load, start the backend and frontend with the repo scripts or Docker Compose.

### Chat does not start

Check that the backend is reachable and the OpenAI API key is configured. The health endpoint should report that OpenAI is configured.

### Memory target needs confirmation

KlassenPilot is not fully sure which lesson should receive the update. Confirm the date or lesson title in chat before saving.

> [!tip]
> Wrong lesson date? Do not save. Correct the date in the workflow or return to the timeline and start from the intended lesson.

### Plan does not save

Make sure a lesson date is selected. If save still fails, keep the draft open and note the error message.

### Draft or proposed change looks wrong

Edit the draft directly or ask the copilot to revise it. Reject proposed file changes before commit — **a proposal is not durable memory until you approve it.**

## What to report during beta

Useful reports include:

- what you were trying to do
- class and lesson date
- what the copilot got wrong
- whether proposed memory was trustworthy
- whether the plan improved because of prior memory

---

**Back to start:** [Start here](/docs/start-here)
