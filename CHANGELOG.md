# Changelog

All notable changes to Delegate are documented here.

## 0.2.5 — 2026-02-15

### Added
- **OS-level bash sandboxing** — agents run with macOS Seatbelt / Linux bubblewrap isolation via `claude-agent-sdk`. Bash commands are kernel-restricted to the delegate home directory and platform temp directory; writes outside are blocked at the OS level regardless of what the model attempts.
- **Migrated to `claude-agent-sdk`** — replaced `claude-code-sdk` (v0.0.25) with `claude-agent-sdk` (v0.1.36), which bundles the Claude Code CLI binary (no separate `npm install` required) and adds native `SandboxSettings` support.

### Changed
- **Defense-in-depth permissioning** — three independent layers now enforce write isolation: (1) `can_use_tool` callback blocks Edit/Write tools outside allowed paths, (2) `disallowed_tools` hides dangerous git commands at the SDK level, (3) OS sandbox restricts all bash file writes at the kernel level.

## 0.2.4 — 2026-02-15

### Added
- **SharedWorker SSE multiplexing** — a `SharedWorker` maintains a single SSE connection to `/stream` shared across all browser tabs, with automatic fallback to direct `EventSource` when `SharedWorker` is unavailable. Unlimited tabs now share 1 HTTP connection.
- **Batch agent stats endpoint** — `GET /teams/{team}/agents/stats` returns stats for all agents in a single `GROUP BY` query, replacing N individual per-agent requests.

### Changed
- **esbuild watcher gated behind `--dev` flag** — `delegate start` no longer auto-starts the esbuild frontend watcher in dev checkouts. Use `delegate start --dev` to enable live frontend rebuilds. This avoids unnecessary node processes and potential startup delays in normal usage.
- **Single global SSE stream** — frontend opens one `EventSource` to `/stream` instead of one per team, eliminating browser connection pool exhaustion when multiple tabs are open.
- **Content-hash cache busting** — static assets (`app.js`, `styles.css`) served with `?v={hash}` derived from file contents, ensuring browsers always fetch the latest bundle after rebuilds or upgrades without manual version bumps.
- **`/bootstrap` performance** — eliminated redundant `ensure_schema` checks, batched agent stats into a single `GROUP BY` query, and reduced per-team agent counting to a cheap directory listing; ~80% faster cold bootstrap.
- **Agent stats deferred to agents tab** — polling loop only fetches agent stats when the agents tab is active, eliminating unnecessary DB round-trips on chat and tasks views.

### Fixed
- **`team remove` not cleaning up database** — removed teams still appeared in the UI because the `teams` table row was never deleted; now cleaned up on removal.
- **UI hang with multiple tabs** — per-team SSE connections exhausted the browser's 6-connection HTTP/1.1 pool; switching to a single global stream freed connections for normal API requests.

## 0.2.3 — 2026-02-15

### Added
- **`/bootstrap` endpoint** — single API call returns config, teams, and initial team data (tasks, agents, stats, messages), replacing the 5+ request waterfall on app load.
- **Self-hosted fonts** — Inter and JetBrains Mono served from the bundle via `@fontsource`, eliminating external Google Fonts requests and FOUT.

### Changed
- App startup refactored to use `/bootstrap` — first meaningful paint no longer blocked by sequential API calls.
- Polling loop no longer fires immediately on mount; defers to the interval timer so it doesn't race with bootstrap data.
- Task panel prefetch deferred by 5 seconds to avoid competing with initial render.

### Fixed
- **UI hang on server restart** — `fetchBootstrap` catch block now falls back to individual API calls when the endpoint is unavailable (e.g., old server still running), instead of silently swallowing the error and leaving the app blank.
- **`greet_team` crash** — `Message` dataclass accessed via dict syntax (`m["sender"]`) instead of attribute access (`m.sender`); fixed to use dot notation.

## 0.2.2 — 2026-02-15

### Added
- **Roadmap section in README** — documented upcoming features (sandboxing, external integrations, remote repos, team templates).
- **Local-first note in README** — clarified that Delegate currently works with local git repos, with remote/external tool support on the roadmap.

### Changed
- `/status` command redesigned — task-focused, concise output replacing the verbose previous format.
- `/diff` command shows red-bordered error block on failures instead of silently failing.
- API key error message now lists three clear options with examples: `export ANTHROPIC_API_KEY`, `delegate start --env-file`, and `claude login`.

## 0.2.1 — 2026-02-15

### Added
- **Empty-state modal** — guided setup screen when no teams are configured.
- **Animated thinking indicator** — manager activity bar cycles through synonyms ("thinking…", "reasoning…", "pondering…") with smooth transitions.
- **Task approve/reject shortcuts** — `Ctrl+Enter` to approve, `Ctrl+Shift+Enter` to reject when the approval textarea is focused.
- **Agent inbox task badges** — task IDs shown as badges in agent inbox messages.
- **`/cost` command** — view token usage and cost breakdown per task inline in chat.
- **Slash command usage hints** — autocomplete items show argument descriptions.

### Changed
- Task panel rendering optimized with progressive diff loading, memoization, and lazy activity fetch.
- Cost summary task IDs styled in gray-scale (matching system task-id pattern) instead of green links.
- Toast borders changed from colored to neutral for a cleaner look.
- Reply blockquote spacing improved (blank line after quote).
- Playwright test suite stabilized for flat URLs, new components, and webkit timing.
- CI: frontend build skipped in pytest job; playwright steps reordered.

### Fixed
- `selectTeam` TDZ crash — `useCallback` declaration moved above the `useEffect` that depends on it, fixing a `ReferenceError` that broke the entire app on load.
- Cmd+K team switcher arrow key delay caused by re-registering keyboard handlers on every render.
- `/cost` command 500 error (missing `get_connection` import).
- `CollapsibleMessage` ref forwarding issue.
- Git `init -b main` in multi-team test fixture (CI compatibility).

## 0.2.0 — 2026-02-14

### Added
- **Workflow engine** — define custom task lifecycles in Python with stages, transitions, and hooks. Ships with a default `todo → in_progress → in_review → in_approval → merging → done` workflow.
- **Zero-config first run** — `delegate start` auto-detects your name, creates a team, registers the CWD repo, and greets you with a welcome message.
- **System user** — automated actions (task creation, status changes, merge events) are attributed to a `system` user instead of a team member.
- **Human members model** — replaces the single "boss" with proper human member identities stored in `~/.delegate/members/`. Humans can belong to multiple teams.
- **Multi-team isolation** — messages, tasks, and events are properly scoped per team. Cross-team message leakage fixed.
- **Merge preview tab** — view diff against `main` in the task panel without merging.
- **Squash-reapply fallback** — when rebase conflicts occur during merge, attempt a squash-reapply before escalating to the DRI.
- **Side panel stacking** — clicking links in a panel opens a new panel on top with a "Back" button.
- **Slash commands** — `/shell` to run commands, `/diff` to view task diffs inline. Autocomplete with Tab/Enter.
- **Audio notifications** — sounds for tasks needing approval and completed tasks.
- **Task prefetch** — task panel data loads instantly via prefetch on hover.
- **Cmd+K team switcher** — quick keyboard shortcut to switch between teams.
- **Configurable charter presets** — "quality first" and "ship fast" variants.
- **Global task endpoints** — access tasks without team context for cross-team views.
- **Agent name pool** — random agent names on team creation.

### Changed
- Manager identity standardized to `delegate` (removed `--manager` CLI option).
- Agent names must be unique within a team but no longer globally.
- URL routing simplified — flat `/chat`, `/tasks`, `/agents` paths.
- Chat input changed to `contentEditable` div for better UX.
- Sidebar redesigned with grouped teams and idle summary.
- Keyboard shortcuts respect input focus (no interference while typing).

### Fixed
- File viewer loading ("File loading..." on attachment clicks).
- Team selector dropdown not showing options after first use.
- Orphaned `esbuild` processes on shutdown.
- Manager activity indicator disappearing randomly.
- Shell command `~` expansion and error display.
- Timestamp alignment across message types.

## 0.1.0 — 2026-02-08

Initial release.

- Multi-agent team with manager + engineer agents
- Task management with full lifecycle (create, assign, review, merge)
- Git worktree isolation per agent
- Agent-to-agent code review
- Merge worker with rebase and pre-merge tests
- Real-time web UI with chat, task panel, agent panel
- SSE-based live updates
- `delegate` CLI with team, agent, and repo management
- Keyboard shortcuts (vim-style navigation)
- Per-team SQLite databases
- Agent memory (journals, notes, context files)
- Published to PyPI as `delegate-ai`
