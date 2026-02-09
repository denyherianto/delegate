# Code Review

## Workspace Isolation

Each agent works in their own **git worktree**, created automatically when they start a task associated with a registered repository. Worktrees are stored in the agent's directory (e.g., `~/.boss/teams/<team>/agents/<agent>/worktrees/<repo>-T<NNNN>/`). This ensures agents never interfere with each other's uncommitted changes while sharing the same repository.

Registered repos are stored as **symlinks** in `~/.boss/repos/` pointing to the real local repository root. No clones are made — all worktrees are created directly against the local repo. When an agent starts a task with an associated repo, a worktree is created with a dedicated branch and the current main HEAD is recorded as `base_sha` on the task.

## Branches

All work happens on feature branches. Branch naming convention:

```
<agent>/T<NNNN>
```

For example: `alice/T0012` or `bob/T0003`.

No direct pushes to main.

## Merge Flow

Agents don't merge their own branches. The merge flow is:

1. Agent completes work and sets the task status to `review`.
2. Agent sends a review request to QA: `REVIEW_REQUEST: repo=<repo_name> branch=<branch>`
3. QA creates a worktree from the repo (via symlink), reviews only the diff between `base_sha` and branch tip, runs tests, and verifies quality.
4. If QA approves: task status moves to `needs_merge`.
5. If QA rejects: task returns to `in_progress` with feedback.
6. For repos with `approval: manual` (default): the boss must approve the merge in the UI.
7. For repos with `approval: auto`: the daemon auto-merges after QA approval.
8. The merge worker **rebases** the feature branch onto latest `main`. If conflicts arise, the task status becomes `conflict` and the manager is notified.
9. After a clean rebase, the merge worker **runs tests** on the rebased branch. If they fail, the task becomes `conflict`.
10. If rebase and tests succeed, the merge worker does a **fast-forward merge** (`git merge --ff-only`) to atomically advance `main`.
11. On successful merge: task status becomes `merged`, worktree and branch are cleaned up.

## Review Standards

The reviewer holds the line on code quality. Your approval means "I am confident this is correct, readable, tested, and consistent with our specs." If you wouldn't be comfortable maintaining this code yourself, don't approve it.

**Do not approve code with known bugs.** If you find a bug — even a minor one — it must be fixed before merge. Noting a bug as "non-blocking" and approving anyway is not acceptable. Every known issue is blocking until it's resolved. The purpose of review is to catch problems *before* they reach main, not to document them for later.

**Actually test the code.** Don't just read the diff. Check out the branch, run it, and verify the behavior matches the task requirements. Click the buttons, trigger the edge cases, check the error paths. If you can't verify it works, you can't approve it.

If the author and reviewer genuinely disagree and can't resolve it between themselves, escalate to the project DRI. The DRI makes the final call.

## Review Focus

Reviewers focus on four things:

1. **Correctness** — does it do what it claims? Did you actually run it and verify?
2. **Readability** — can I understand this without the author explaining it?
3. **Test coverage** — are the important business-logic paths tested?
4. **Consistency** — does this match documented specs and conventions?

## Turnaround

Keep review turnaround under 30 minutes when possible. Quick feedback loops keep the team moving. If you can't review within 30 minutes, let the author know so they can context-switch rather than wait.

## Feedback Style

When you have concerns, raise them as specific questions or suggestions, not vague reactions. "What happens if this input is empty?" is useful feedback. "I don't like this approach" is not — say why, and suggest an alternative.
