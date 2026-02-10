# Task Management

## Scoping & Focus

Tasks should be scoped to roughly half a day of work. If bigger, break it down first. One task at a time — finish what you started before picking up something new.

## Commands

```
python -m delegate.task create <home> --title "..." [--description "..."] [--repo <name>] [--priority high] [--depends-on 1,2]
python -m delegate.task list <home> [--status open] [--assignee <name>]
python -m delegate.task show <home> <task_id>
python -m delegate.task assign <home> <task_id> <assignee>
python -m delegate.task status <home> <task_id> <new_status>
```

Statuses: `open` → `in_progress` → `review` → `needs_merge` → `merged`. Also: `rejected` (→ `in_progress`), `conflict` (→ `in_progress`), `done` (legacy).

Tasks are global, stored in `~/.delegate/tasks/`. Associate with a repo using `--repo`.

## Workflow

1. Manager creates and assigns task.
2. Agent sets `in_progress`. If task has a repo, workspace auto-sets to a git worktree with `base_sha` recorded.
3. Agent completes → sets `review`, sends review request to QA.
4. QA reviews diff (base_sha → branch tip), runs tests.
5. QA approves → `needs_merge`. QA rejects → back to `in_progress` with feedback.
6. Boss approves (manual repos) or auto-merge (auto repos).
7. Merge worker rebases onto main, runs tests, fast-forward merges.
8. Task becomes `merged`.

## Dependencies

Specify with `--depends-on <ids>`. A task with unmerged dependencies must NOT be assigned. When a task merges, check if blocked tasks are now unblocked.

## Blockers

Message the manager immediately. Don't spend more than 15 minutes stuck before raising it.

## Completion

Write a summary: what you built, decisions made, anything the next person should know.
