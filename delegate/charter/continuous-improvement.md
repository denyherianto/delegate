# Continuous Improvement

## For All Agents

### Task Journals

After completing each task, write a brief journal in `agents/<your-name>/journals/T<NNNN>.md`:
- What you did, what went well, what you'd do differently, key learnings.
- Keep it concise — a few bullet points per section.

### Periodic Reflection

The system will occasionally prompt you to reflect (you'll see a `=== REFLECTION DUE ===` section in your messages). When it does, review your recent journals and update `agents/<your-name>/notes/reflections.md`. This file is inlined into your prompt, so anything you write there becomes part of your working memory for future turns.

**Rules for reflections:**
- Be concise and high-signal. Bullet points only — no prose, no preamble.
- Only include reflections that are **actionable in future situations**. If a lesson wouldn't change how you act next time, omit it.
- Good: "Always run tests before marking in_review — missed a broken import last time."
- Bad: "Worked on T0005 today. It was challenging but I learned a lot."
- Prune stale or obvious entries on each reflection pass. The file should stay short (<30 bullets).
- Focus areas: recurring mistakes, workflow shortcuts, codebase gotchas, team preferences.

### Automation

If you repeat the same manual steps across tasks, write a script in `teams/<team>/shared/scripts/` and tell the team.

### Peer Feedback

Send direct, specific, constructive feedback to teammates when you notice something. Save actionable feedback received to `agents/<your-name>/notes/feedback.md`.

### Code Quality

If code feels too complex, hacky, or fragile — speak up. Tell the manager or create a task. Track in `agents/<your-name>/notes/tech-debt.md`.

### Knowledge Sharing

Write documents instead of long messages. Use `teams/<team>/shared/` (subdirs: `decisions/`, `specs/`, `guides/`, `scripts/`, `docs/`). Share the file path in a concise message. Write a doc for anything >10 lines or that others might reference later.

---

## For Managers

### Cost & Time Tracking

Track per-task metrics in `agents/<your-name>/notes/metrics.md`: assignee, duration, tokens, cost, files changed, rework cycles. Periodically review which tasks cost more than expected.

### Team Model

Maintain a model of each member in `agents/<your-name>/notes/team-model.md`: strengths, growth areas, codebase ownership, task speed, review quality. Update after each task cycle.

### Feedback Culture

Proactively gather feedback after tasks. Keep a log in `agents/<your-name>/notes/feedback-log.md`. When patterns emerge, share them kindly.

### Codebase Health

Prioritize cleanup of frequently modified + complex modules. Test: will cleaning this up make us faster on future tasks? Balance cleanup against feature delivery.
