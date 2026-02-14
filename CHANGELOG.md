# Changelog

All notable changes to Delegate are documented here.

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
