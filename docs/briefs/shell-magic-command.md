# `/shell` Magic Command — Design Brief

## Overview

Add support for magic commands in the chat input, starting with `/shell <command>`, which executes a shell command server-side and shows the output inline in the chat log.

## What it does

When the user types `/shell <command>` in the chat input and hits Enter, instead of sending a message to an agent, Delegate executes the shell command **server-side** and shows the output inline in the chat log.

## CWD resolution

- **Default**: The first registered repo for the current team. This is what the user most likely cares about.
- **Override**: `/shell --repo backend git status` to pick a specific registered repo by name.
- **Override**: `/shell --cwd /some/path ls -la` for an arbitrary directory.
- **Fallback**: If no repos are registered, use `~/.delegate/teams/<team>/` as cwd.

## Backend

### Execute endpoint

```
POST /teams/{team}/shell
Body: { "command": "...", "cwd": null, "repo": null }
Response (immediate): { "id": "sh-<uuid>", "status": "running", "command": "..." }
```

The server spawns the command via `subprocess.Popen` in a background thread (or async), captures stdout+stderr, and stores results in memory (or a small SQLite table). A timeout (e.g. 60s) kills the process and marks it `error`.

### Poll/result endpoint

```
GET /teams/{team}/shell/<id>
Response: {
  "id": "...",
  "status": "running" | "done" | "error",
  "exit_code": 0,
  "stdout": "...",
  "stderr": "...",
  "duration_ms": 1234
}
```

### Security considerations

This is a local tool, not a public service — the user is running commands on their own machine. Still:
- Log every command executed.
- Cap output at ~100KB to avoid flooding the UI.
- Enforce a timeout (60s default) to prevent runaway processes.

## How results appear in the chat log

Shell commands appear as a **special message type** (`type: "shell"`) in the chat log, alongside regular messages and events.

### Lifecycle

1. **Immediately on send**: A local "pending" bubble appears, styled like a terminal:
   ```
   🖥 /shell git status
   ⏳ Running...
   ```

2. **While running**: The bubble stays in place with a spinner. New messages from agents continue to arrive above/below it normally — it doesn't block the chat flow.

3. **On completion**: The bubble updates in-place:
   ```
   🖥 /shell git status (repo: boss-ai) — 0.3s ✓
   ┌─────────────────────────────────
   │ On branch main
   │ Your branch is up to date with 'origin/main'.
   │ nothing to commit, working tree clean
   └─────────────────────────────────
   ```

4. **On error**:
   ```
   🖥 /shell npm test (repo: frontend) — 12.4s ✗ (exit 1)
   ┌─────────────────────────────────
   │ ... stderr output ...
   └─────────────────────────────────
   ```

5. **Collapsible**: If output exceeds ~20 lines, show the first 10 with a "Show more" toggle.

6. **Persisted**: Shell results are stored in the DB (same `messages` table with `type='shell'`, or a dedicated `shell_runs` table) so they survive page reloads and appear in the correct chronological position.

## Parsing

```
/shell git status                    → cmd="git status", cwd=default repo
/shell --repo backend git log -5     → cmd="git log -5", cwd=repos/backend
/shell --cwd /tmp ls                 → cmd="ls", cwd=/tmp
```

The frontend parses the `/shell` prefix and extracts `--repo`/`--cwd` flags; the backend receives the raw command string + optional `repo`/`cwd` override.

## Frontend flow

1. **Intercept in `handleSend`**: Before calling `api.sendMessage()`, check if the input starts with `/`. If so, parse the command name and dispatch accordingly. For `/shell`, call `api.runShell(team, command, repo)` instead.
2. **Optimistic UI**: Immediately insert a local shell bubble (with status `"running"`) into the messages signal so it appears instantly.
3. **Poll for result**: Start polling `GET /teams/{team}/shell/<id>` every 1–2s. When `status === "done"` or `"error"`, update the bubble in-place with the output.
4. **Styling**: Shell bubbles get a distinct CSS class (`.msg-shell`) with monospace font, dark/muted background, no avatar/sender, and collapse/expand for long output.

## Files to change

| File | Change |
|------|--------|
| `frontend/src/components/ChatPanel.jsx` | Intercept `/` commands in `handleSend`, render shell bubbles |
| `frontend/src/api.js` | Add `runShell()`, `getShellResult()` |
| `frontend/src/styles.css` | `.msg-shell` styles |
| `delegate/web.py` | `POST /teams/{team}/shell`, `GET /teams/{team}/shell/{id}` |
| `delegate/db.py` | Optional: `shell_runs` table or reuse messages with `type='shell'` |

## Future magic commands

This architecture generalizes to other commands:
- `/task create <title>` — quick task creation
- `/assign T0042 alice` — reassign a task
- `/status` — quick team status summary
- `/approve T0042` — approve from chat
