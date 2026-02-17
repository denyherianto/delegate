# Merge Process Invariants

This document describes the invariants, guarantees, and locking protocol for
the Delegate merge flow. Audience: engineers working on `merge.py`, `runtime.py`,
and `web.py`.

---

## Merge Flow Steps

The full merge sequence for a task in `in_approval` state:

1. **Transition to merging** — `merge_once()` calls `transition_task(..., "merging", manager)`.

2. **Phase 1: Rebase all repos** — For each repo in the task:
   a. Create a disposable worktree + temp branch from the feature branch
      (path: `teams/<team>/worktrees/_merge/<uid>/T<NNNN>/`).
   b. `git rebase --onto main <base_sha> HEAD` inside the disposable worktree.
   c. If rebase fails, attempt squash-reapply: create a fresh worktree from
      main, compute `git diff main...feature`, apply via `git apply --3way`.
   d. If squash-reapply also fails: true content conflict — escalate immediately
      (`merge_failed`, notify manager with conflict context). No agent worktrees
      are touched.
   e. Collect the rebased tip SHA from the disposable worktree HEAD.

   **All-or-nothing**: all repos are rebased before any agent worktree is touched.
   If any repo's rebase fails, the others' disposable worktrees are cleaned up
   and the function returns without modifying agent worktrees.

3. **Acquire worktree lock** — `_acquire_worktree_lock(exchange, team, task_id)`.
   Waits up to `WORKTREE_LOCK_TIMEOUT` (30 seconds). If the lock is unavailable,
   aborts and returns `WORKTREE_ERROR` (non-retryable).

4. **Phase 2: Reset all agent worktrees** — For each repo (while holding lock):
   a. Capture the agent worktree's current HEAD (for rollback).
   b. `git reset --hard <rebased-tip>` in the agent's feature worktree.
      - Moves HEAD (still on feature branch) to rebased tip.
      - Updates tracked files in the working tree.
      - **Untracked files (environment artifacts) are preserved.**
   c. If reset fails, roll back already-reset worktrees to their original HEAD.
   d. If rollback also fails (shouldn't happen), log a warning and continue.

5. **Release worktree lock** — Lock is released in a `finally` block regardless
   of success or failure.

6. **Update base_sha** — `update_task(..., base_sha=main_head_dict)` records the
   current main HEAD as the new base_sha for each repo. This is done atomically
   with the reset (before disposable WTs are removed).

7. **Remove disposable worktrees** — All temp branches and worktrees created in
   Phase 1 are removed. The agent worktree is now the canonical working copy.

8. **Phase 3: Run pre-merge tests** — `_run_pre_merge()` is called with the
   **agent worktree path** (not the disposable worktree). This ensures tests run
   in the environment the agent built and reviewed (with `__pycache__`, installed
   packages, build output intact).
   - If a pre-merge script is configured for the repo, it is run.
   - Otherwise, pytest/npm/make are auto-detected.
   - If tests fail: task becomes `merge_failed`, agent worktree is left at the
     rebased tip (agent can fix and resubmit without manual recovery).

9. **Phase 4: Fast-forward merge** — `_ff_merge_to_sha(repo_dir, tip_sha)`.
   Merges main to the rebased tip SHA (not a branch ref — the temp branch is
   already removed).
   - If user has `main` checked out and clean: `git merge --ff-only <sha>`.
   - If user has `main` checked out and dirty: fail (retryable: `DIRTY_MAIN`).
   - If user is on another branch: `git update-ref` with CAS (atomic, ref-only).

10. **Record merge metadata** — `merge_base` and `merge_tip` are stored on the task.

11. **Mark done** — `change_status(..., "done")`.

12. **Clean up** — Feature branch and agent worktree are removed (if no sibling
    tasks share the branch). Disposable worktrees were already removed in step 7.

13. **Discard lock entry** — `exchange.discard_worktree_lock(team, task_id)` removes
    the asyncio.Lock from the registry (prevents unbounded growth).

---

## State Transitions

```
in_approval
    -> merging          (merge_once, on first attempt)
    -> merge_failed     (non-retryable failure or max retries exhausted)
    -> done             (successful merge)

merging (retry loop, up to MAX_MERGE_ATTEMPTS=3):
    -> merging          (retryable failure: DIRTY_MAIN, FF_NOT_POSSIBLE, UPDATE_REF_FAILED)
    -> merge_failed     (non-retryable or max retries)
    -> done             (success)
```

Non-retryable reasons (escalate immediately):
- `REBASE_CONFLICT` — rebase failed but squash also failed
- `SQUASH_CONFLICT` — true content conflict (both strategies failed)
- `PRE_MERGE_FAILED` — tests failed in agent worktree
- `WORKTREE_ERROR` — could not create worktree, lock timeout, or reset failed

Retryable reasons (stay in `merging`, retry up to 3 times):
- `DIRTY_MAIN` — main has uncommitted changes
- `FF_NOT_POSSIBLE` — fast-forward not possible (branch not descendant)
- `UPDATE_REF_FAILED` — concurrent push/update

---

## Worktree Isolation Guarantees

**Agent worktrees are only mutated during `merging` state**, and only via:
1. `git reset --hard <rebased-tip>` — while holding the worktree lock.

This is enforced by two complementary mechanisms:

### Mechanism A: Per-task AsyncRWLock (primary)

The `TelephoneExchange` maintains a registry of `AsyncRWLock` objects (a custom
async read-write lock), keyed by `(team, task_id)`.

- **Turn dispatcher** (`run_turn` in `runtime.py`): acquires a **read lock** at
  the start of a turn and releases it at the very end (after all bookkeeping,
  including the optional reflection turn). Lock is released in a `finally` block.
  Multiple agent turns on the same task can hold the read lock simultaneously
  (e.g. manager and DRI both active concurrently without contention).

- **Merge worker** (`merge_task` in `merge.py`): acquires a **write lock** before
  `git reset --hard` in Phase 2, releases immediately after all repos are reset.
  The write lock waits for all active readers to finish and blocks new readers
  while held. Uses `run_coroutine_threadsafe` since the merge worker runs in a
  thread pool.

Both run in the same asyncio event loop. `AsyncRWLock` uses `asyncio.Condition`
internally.

**Lock ordering**: only one write lock per task is ever held at a time (by the
merge worker). No cross-task or cross-lock ordering constraint exists (no
deadlock risk).

### Mechanism B: Task state gate (defense-in-depth)

The daemon dispatch loop (`_dispatch_turn` in `web.py`) checks: before dispatching
a turn for agent `A`, query all tasks in `merging` state. If any has `dri == A`,
skip dispatch for this cycle.

This is defense-in-depth — the lock already prevents concurrent access. The
state gate prevents even attempting to run a turn during the merge window, which
would waste a turn and fight the lock.

---

## Locking Protocol Summary

| Actor | When | Lock type | Lock held for |
|-------|------|-----------|---------------|
| `run_turn` | start of turn | read lock on `(team, task_id)` | entire turn duration |
| `merge_task` | before Phase 2 | write lock on `(team, task_id)` | Phase 2 only (reset loop) |
| daemon loop | before dispatch | (no lock — state gate is a read check) | n/a |

---

## Multi-Repo All-or-Nothing Semantics

For tasks with multiple repos (`task["repo"] = ["repo_a", "repo_b", ...]`):

- **Rebase phase**: all repos are rebased before any agent worktree is touched.
  If repo_b's rebase fails after repo_a succeeded, repo_a's disposable worktree
  is cleaned up and the merge aborts without touching either agent worktree.

- **Reset phase**: worktrees are reset in order. If reset fails for repo_b after
  repo_a was already reset, repo_a is rolled back to its original HEAD.

- **Test phase**: tests are run per-repo, in order. If repo_b's tests fail,
  the merge fails and the agent worktrees are left at the rebased tip for both
  repos (not rolled back — the agent should fix the failing tests and resubmit).

- **FF-merge phase**: repos are merged in order. If repo_b's FF-merge fails after
  repo_a succeeded, the task is left in a partially-merged state (retryable if
  the failure is transient).

---

## Agent Worktree State After Merge Outcomes

| Outcome | Agent worktree state |
|---------|---------------------|
| Success | Removed (clean up) |
| `PRE_MERGE_FAILED` | Feature branch at rebased tip, environment intact. Agent can fix tests and resubmit via `task status in_review`. |
| `REBASE_CONFLICT` / `SQUASH_CONFLICT` | Unchanged (pre-rebase state). Agent uses `rebase_to_main` MCP tool to resolve conflicts manually. |
| `WORKTREE_ERROR` (lock/reset) | May be partially reset or unchanged. Agent should check state. |
| `DIRTY_MAIN` / retryable | Unchanged (reset not attempted yet). Retry happens automatically. |

---

## base_sha Update Semantics

`base_sha` is a per-repo dict stored on the task: `{repo_name: sha}`.

- **Set initially**: when the daemon creates the agent worktree, `base_sha` is set
  to the main HEAD at that time. This records the point from which the agent's
  commits are rebased.

- **Updated during merge**: after Phase 2 (agent WT reset), `base_sha` is updated
  to the current main HEAD (the rebase point used for this merge attempt). This
  ensures that if the task is retried (e.g., after `PRE_MERGE_FAILED`), the next
  rebase uses the correct base SHA and doesn't re-apply already-rebased commits.

---

## Disposable Merge Worktrees

Disposable worktrees are created in `teams/<team>/worktrees/_merge/<uid>/T<NNNN>/`.

- Created in Phase 1 for rebase.
- Removed immediately after Phase 2 (before tests run).
- Also removed on any failure that occurs after creation.
- The `_merge/` directory and empty parent directories are pruned on cleanup.

**Tests do NOT run in disposable worktrees.** They run in the agent's feature
worktree after the reset, preserving the agent's environment.

---

## When the Main Repo Working Directory Is Touched

The main repo working tree is only updated during the FF-merge step (Phase 4),
and only when the user has `main` checked out with a clean state. In that case,
`git merge --ff-only` advances both the ref and the working tree.

If the user is on any other branch, only the `refs/heads/main` ref is updated
atomically via `git update-ref` with compare-and-swap. The working tree is
never touched in that case.

---

## Notes for Implementors

- `merge_task()` is **pure**: it returns `MergeResult` and does not change task
  status. Status changes are the caller's responsibility (`merge_once()`).

- The worktree write lock is acquired/released synchronously by the merge worker
  (which runs in a thread pool via `asyncio.to_thread`). `run_coroutine_threadsafe`
  is used to schedule both `acquire_write()` and `release_write()` on the event
  loop, and `future.result()` waits for acquisition synchronously. Release is
  fire-and-forget (not awaited) since we just need the write flag cleared.

- Agent turns acquire the read lock directly with `await lock.acquire_read()` /
  `await lock.release_read()` since `run_turn` is an async function.

- If the exchange is `None` (e.g., in unit tests), locking is skipped entirely.
  Tests should pass `exchange=None` to `merge_task()`.

- `discard_worktree_lock()` is called after task completion to prevent unbounded
  growth of the lock registry. It is safe to call on a non-existent key.
