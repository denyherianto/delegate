# Task Management

## Scoping

Tasks should be scoped to roughly half a day of work. If a task feels bigger than that, break it down into smaller pieces before starting. Smaller tasks are easier to review, easier to unblock, and easier to reason about.

## Focus

One task at a time. Focus on finishing what you started before picking up something new. Partial progress on three tasks is worth less than one completed task.

## Task Commands

```
# Create a task
python -m boss.task create <home> --title "..." [--description "..."] [--repo <name>] [--priority high] [--depends-on 1,2]

# List tasks
python -m boss.task list <home> [--status open] [--assignee <name>]

# View a task
python -m boss.task show <home> <task_id>

# Assign a task
python -m boss.task assign <home> <task_id> <assignee>

# Update task status
python -m boss.task status <home> <task_id> <new_status>
```

Valid statuses: `open` → `in_progress` → `review` → `needs_merge` → `merged`.

Additional statuses: `rejected` (can go back to `in_progress`), `conflict` (rebase/test failure, goes back to `in_progress`), `done` (legacy).

Tasks are global across all teams and stored in `~/.boss/tasks/`. When a task is associated with a registered repository, specify it with `--repo`.

## Workflow

1. Manager creates a task and assigns it to an agent.
2. Agent sets status to `in_progress` when they start working.
3. If the task has an associated repo, the agent's workspace is automatically set to a git worktree for that repo. The current main HEAD is recorded as `base_sha`.
4. When done, agent sets status to `review` and sends a review request to QA.
5. QA reviews the diff between `base_sha` and branch tip, runs tests, checks coverage.
6. QA approves → task moves to `needs_merge`.
7. Boss approves (for manual repos) or auto-merge kicks in (for auto repos).
8. Merge worker rebases onto main, runs tests, fast-forward merges.
9. Task becomes `merged`.

## Dependencies

Dependencies between tasks are enforced:

- When creating a task, specify dependencies: `--depends-on 1,2` (task IDs).
- **A task with unmerged dependencies must NOT be assigned.** The manager is responsible for checking that all `depends_on` tasks are in `merged` status before assigning work.
- When a task is merged, check if any blocked tasks are now unblocked and assign them.
- If you discover a new dependency while working, message the manager immediately.

## Blockers

When you're blocked, message the manager immediately with a clear description of what's blocking you. Don't spend more than 15 minutes stuck before raising it.

## Completion

When a task is done, write a summary describing what you built, any decisions you made, and anything the next person should know.
