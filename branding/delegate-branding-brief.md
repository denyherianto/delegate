# Delegate — Branding Brief

## Product Summary

Delegate is a single-developer productivity tool that creates AI agent teams to do real software engineering work. The user defines a team (manager, engineers, designers), writes briefs in plain English, and watches agents pick up tasks, write code, review each other's work, and deliver merge-ready branches.

The core emotional promise: **"You're one person. Delegate gives you a team."**

---

## Brand Personality

### Voice
- **Confident, not corporate.** Delegate talks like a sharp coworker, not a SaaS landing page.
- **Direct.** Short sentences. No filler. Respects the user's time.
- **Warm but not cute.** The agents call you by your first name. The tone is collegial, not playful.
- **Technical without jargon.** The audience writes code daily. Don't explain git to them. Don't baby them.

### Character Traits
- Competent — it works, reliably, without drama
- Alive — there's a hum of activity, things are happening
- Empowering — you're the boss, the tool amplifies you
- Opinionated — sensible defaults, doesn't ask you to configure everything

### What Delegate is NOT
- Not a dashboard full of charts nobody reads
- Not a "no-code" tool — the audience is developers
- Not enterprise software — no onboarding wizards, no role-based access control screens
- Not whimsical — no mascots, no emoji-heavy UI, no gamification

---

## Visual Identity

### Logo & Wordmark

**Wordmark: "delegate"** — all lowercase, a monospaced or semi-monospaced typeface. The word should feel like it belongs in a terminal. No icon needed in v1 — the wordmark is the logo.

**Reasoning:** Developers trust tools that look like they were made by developers. A polished-but-restrained wordmark in a monospaced font signals "this was built by someone like you."

**Typography suggestion for wordmark:** JetBrains Mono, Berkeley Mono, or IBM Plex Mono — pick one with good weight variation and a distinctive character. Avoid Fira Code (overused in dev tool branding).

### Favicon

The favicon should be a bold **"d"** lettermark, slightly geometric, recognizable at 16x16. Dark background with a bright accent mark. See attached SVG.

---

## Color System

### Philosophy

The UI is a **war room** — a dark, focused space where things are alive and moving. The dark background recedes; color is used sparingly to convey meaning (status, attention, identity). Every color earns its place.

### Primary Palette

| Role | Token | Hex | Usage |
|------|-------|-----|-------|
| **Background (base)** | `--bg-primary` | `#0F1117` | Main app background, the "room" |
| **Background (surface)** | `--bg-surface` | `#171923` | Cards, panels, sidebar |
| **Background (elevated)** | `--bg-elevated` | `#1E2130` | Hover states, active panels, dropdowns |
| **Border** | `--border-default` | `#2A2D3A` | Subtle panel separators |
| **Border (emphasis)** | `--border-emphasis` | `#3D4155` | Active borders, focused elements |
| **Text (primary)** | `--text-primary` | `#E8E9ED` | Main body text, headings |
| **Text (secondary)** | `--text-secondary` | `#8B8FA3` | Labels, timestamps, metadata |
| **Text (muted)** | `--text-muted` | `#565B73` | Placeholders, disabled text |

### Accent Color

| Role | Token | Hex | Usage |
|------|-------|-----|-------|
| **Accent** | `--accent` | `#6C8EEF` | Primary interactive elements, links, focus rings |
| **Accent hover** | `--accent-hover` | `#849FF2` | Hover state for accent elements |
| **Accent muted** | `--accent-muted` | `#6C8EEF1A` | Subtle accent backgrounds (10% opacity) |

**Why this blue:** It's a muted periwinkle — distinct from the "SaaS blue" (#4A90D9) that every B2B tool uses. Slightly desaturated to sit comfortably on dark backgrounds without vibrating. It reads as calm authority rather than corporate enthusiasm.

### Status Colors

These are functional. They convey task and agent state at a glance.

| Status | Token | Hex | Meaning |
|--------|-------|-----|---------|
| **Active / Online** | `--status-active` | `#4ADE80` | Agent working, task in progress |
| **Idle / Waiting** | `--status-idle` | `#FBBF24` | Agent idle, task awaiting assignment |
| **Needs you** | `--status-attention` | `#F87171` | Task blocked on human, review needed |
| **Offline / Done** | `--status-neutral` | `#565B73` | Agent offline, task completed |

**Important:** Status dots should be the most immediately readable element on screen. Use filled circles (●) for online/active states, hollow circles (○) for offline. These tiny dots carry outsized meaning — the user glances at the sidebar and instantly knows who's working.

### Agent Identity Colors

Each agent needs a distinguishable identity in the chat and activity stream. Assign from this pool, rotating assignment:

| Agent Slot | Token | Hex |
|------------|-------|-----|
| Agent 1 | `--agent-1` | `#7DD3FC` | (sky blue)
| Agent 2 | `--agent-2` | `#C4B5FD` | (lavender)
| Agent 3 | `--agent-3` | `#FCA5A5` | (salmon)
| Agent 4 | `--agent-4` | `#6EE7B7` | (mint)
| Agent 5 | `--agent-5` | `#FDE68A` | (butter)
| Agent 6 | `--agent-6` | `#F9A8D4` | (pink)
| Manager | `--agent-manager` | `#E8E9ED` | (white — stands apart)

Agent colors appear on: name labels in chat, sidebar status indicators, activity feed entries, task assignment badges.

---

## Typography

### System

| Role | Font | Size | Weight | Usage |
|------|------|------|--------|-------|
| **Monospace** | JetBrains Mono | varies | 400/500 | Code blocks, task IDs, file paths, terminal-like elements, the wordmark |
| **UI text** | Inter | 13-14px | 400/500 | Body text, labels, descriptions — everything non-code |
| **Headings** | Inter | 16-20px | 600 | Section headers, panel titles |
| **Small** | Inter | 11-12px | 400 | Timestamps, metadata, secondary info |

**Why Inter for UI:** It's the one context where Inter is correct — it was literally designed for UI at small sizes. Developers already read it in VS Code, GitHub, Linear. It's invisible, which is what you want for the chrome around the content that matters.

**Why JetBrains Mono for code/identity:** Task IDs (BM-001), file paths, cost figures, branch names — all of these are "code-like" data. Monospace for these elements reinforces the developer context and improves scannability.

### Rules

- No text above 20px except the empty-state welcome message
- Line height: 1.5 for body, 1.3 for UI labels, 1.6 for chat messages
- Chat messages get slightly more generous line height for readability during fast scanning
- Never bold more than one word per label — bold is for emphasis, not decoration
- Task IDs, branch names, file paths, costs: always monospace

---

## UI/UX Grounding Principles

### 1. The Buzz is the Product

The user's visceral experience of delegate is a "buzzing team's Slack." Agent status changes, commits appearing, reviews happening, tasks moving — this ambient motion is delegate's most valuable feature. Every UI decision should preserve and amplify this feeling.

- The sidebar must show real-time agent activity — status changes, current action, last commit message
- The activity feed should update without refresh
- Transitions should be swift (150ms) but visible — a new message sliding in, a status dot changing color
- **Never batch updates.** If alice commits at :01 and bob starts a review at :02, those appear one second apart, not together. The stagger IS the buzz.

### 2. Glanceable Over Comprehensive

The user is working on their own stuff while delegate runs. They glance at the sidebar, glance at the chat, go back to their editor. The UI must reward a 1-second glance with useful information.

- Status dots before names (color is faster than text)
- "2 tasks need you" banner is the single most important element when it's present
- Task states are color-coded to match status colors
- Cost tracking is visible but not prominent — bottom corner, small monospace text
- Don't hide information behind tabs or dropdowns when a glance could show it

### 3. Chat is the Center

The chat panel is where the user and the manager interact. It's the primary input surface. Everything else (sidebar, banner, tabs) is peripheral to the chat.

- Chat input is always visible, never pushed off-screen by other content
- Chat messages from agents use their identity color for the name label
- The chat panel should feel spacious — generous padding, clear message separation
- No typing indicators or "is thinking..." for agents. Either they've said something or they haven't. The buzz comes from the activity stream, not fake presence indicators in chat.

### 4. Minimal Chrome

Every pixel of UI chrome is a pixel not showing useful information. The app should feel like it's mostly content with minimal frame around it.

- No thick toolbars or navigation bars
- Sidebar is narrow (220-260px), collapses on narrow viewports
- Tab bar (Tasks, Agents, etc.) is text-only, no icons
- Borders are 1px and subtle (`--border-default`) — used for structure, not decoration
- No shadows. Flat hierarchy. Differentiate with background shading only.
- No rounded corners above 4px — keep it crisp

### 5. Terminal Heritage

The audience lives in terminals. The UI should feel like a well-designed terminal tool that happens to be in a browser — not like a web app that was made for developers.

- Monospace for all data-like content (IDs, paths, costs, commands)
- Dark theme only for v1 — light theme is a future concession, not a priority
- The empty-state shows terminal commands, not GUI buttons
- Keyboard shortcuts for common actions (approve task, switch teams, open review)
- No confirmation dialogs except for destructive actions — trust the user

### 6. Reviews Are Spatial

The one place that needs rich UI is the diff review view. Inline comments on specific lines, side-by-side or unified diff, comment threads — this is inherently spatial and needs proper layout.

- Open in a dedicated view (not a modal, not a panel within the chat)
- Diff rendering with syntax highlighting (use the same color scheme as the app)
- Inline comment form appears at the clicked line — no separate panel
- Comment resolution is a single click, not a dropdown
- Show review attempt history as collapsed sections (Attempt 1, Attempt 2...)

### 7. Progressive Disclosure

Don't show everything at once. The default view is the war room (sidebar + chat + banner). Advanced views are one click away but not in your face.

- **Default view:** sidebar (agents + "needs you") + chat + banner
- **One click:** task list, agent details, cost breakdown, review view
- **Settings/config:** CLI only, never in the UI

---

## Layout Reference

```
┌───────────────────────────────────────────────────────┐
│  [bookmark-team ▾]                          $0.42 ⚙  │  ← Top bar: team selector, session cost, settings
├──────────────┬────────────────────────────────────────┤
│ TEAM         │  Tasks  Agents  Reviews               │  ← Tab bar (text only)
│              │                                        │
│ ● alice      │ ┌─ 🔴 2 tasks need you ─────────────┐│  ← Attention banner (conditional)
│   writing    │ └────────────────────────────────────┘│
│   tests...   │                                        │
│              │  alex (manager)              9:41 AM   │  ← Chat messages
│ ● bob        │  Created BM-003: Add delete endpoint  │
│   idle       │  Assigned to alice.                    │
│              │                                        │
│ ○ carol      │  alice                       9:42 AM   │
│   offline    │  On it. Looking at the existing model  │
│              │  schema now.                            │
│──────────────│                                        │
│ ACTIVITY     │                                        │
│ alice ← BM-003                                       │
│ bob ✓ BM-002 │                                        │
│ qa → BM-001  │                                        │
│              ├────────────────────────────────────────┤
│              │  Type a message...              Send ▶ │  ← Always visible input
└──────────────┴────────────────────────────────────────┘
```

### Sidebar Detail

The sidebar has two sections:

**TEAM** — agents with real-time status:
- Status dot (●/○) using status colors
- Agent name in their identity color
- Current action in `--text-secondary`, truncated to one line
- Updates live as agents work — this is the buzz source

**ACTIVITY** — recent events, reverse chronological:
- Compact one-line entries: `alice ← BM-003` (assigned), `bob ✓ BM-002` (completed), `qa → BM-001` (reviewing)
- Uses agent identity colors for names
- Auto-scrolls, max ~8 visible entries before requiring scroll
- New entries animate in from the top (subtle slide, 150ms)

### Attention Banner

- Only visible when `owner = user` on one or more tasks
- Sits between tab bar and chat, full width of the content area
- Background: `--status-attention` at 12% opacity
- Text: `--status-attention` color, e.g. "2 tasks need you"
- Click navigates to Tasks view with filter applied
- Disappears when no tasks are blocked on user (no residual empty space)

---

## Component Patterns

### Chat Message

```
┌──────────────────────────────────────┐
│ alice                      9:42 AM   │  ← Name in agent color, timestamp in --text-muted
│ Implemented the POST endpoint with   │  ← Body in --text-primary
│ validation. Used pydantic for the    │
│ request model. Committing now.       │
└──────────────────────────────────────┘
```

- No avatars. Agent color on the name is sufficient identity. Avatars waste horizontal space in a narrow chat column.
- Messages from the user (you) have no special styling — just your name in `--text-primary`.
- Messages from the manager have a subtly different background (`--bg-elevated`) to visually distinguish coordination from execution chatter.

### Task Card (in task list view)

```
┌──────────────────────────────────────────┐
│ BM-003         in progress      ● alice  │  ← ID (mono), status pill, agent dot+name
│ Add DELETE /bookmarks/{id} endpoint      │  ← Title in --text-primary
│ bookmark-api                     $0.08   │  ← Repo name, cost so far
└──────────────────────────────────────────┘
```

- Status pill is color-coded: `todo` (neutral), `in progress` (green), `in review` (blue/accent), `in approval` (amber), `done` (neutral)
- Agent dot uses their identity color
- Cost in monospace, right-aligned

### Status Pills

| State | Background | Text |
|-------|-----------|------|
| todo | `#565B731A` | `--text-secondary` |
| in progress | `#4ADE801A` | `#4ADE80` |
| in review | `#6C8EEF1A` | `#6C8EEF` |
| in approval | `#FBBF241A` | `#FBBF24` |
| done | `#565B731A` | `--text-secondary` |

Low-opacity background with saturated text. Readable but not overwhelming when you have 15 tasks on screen.

---

## Motion & Interaction

### Timing

| Action | Duration | Easing |
|--------|----------|--------|
| Status dot color change | 200ms | ease-out |
| New activity entry slide-in | 150ms | ease-out |
| Panel/view transition | 200ms | ease-in-out |
| Banner appear/dismiss | 250ms | ease-out |
| Hover state | 100ms | linear |

### Rules

- No loading spinners — use skeleton states or instant transitions
- No toasts or success notifications — the activity feed IS the notification system
- No entrance animations for content that's already there when you navigate
- Agent status changes should feel organic — a dot changing from green to amber mid-glance, like a light on a switchboard

---

## Responsive Behavior

**Primary target: 1280px+ (developer's browser alongside their editor)**

At smaller widths:
- Below 1024px: sidebar collapses, accessible via hamburger icon
- Below 768px: single-column layout, tabs for switching between chat/sidebar/tasks
- Mobile is not a priority — this is a desktop tool for developers at their workstation

---

## What to Avoid

- **Purple gradients** — the universal signifier of "AI product." Delegate is a dev tool that happens to use AI, not an AI product.
- **Glassmorphism / blur effects** — heavy on rendering, adds no information
- **Card shadows** — use background color differences for hierarchy, not shadows
- **Animated backgrounds** — the agents provide the animation; the chrome is still
- **Loading shimmer / skeleton screens** everywhere — one or two is fine, more feels like the app is broken
- **Emoji in the UI chrome** — agents might use emoji in chat (that's fine), but the UI itself should not
- **"AI-powered" badges or sparkle icons** — the user knows it's AI. Don't remind them.
- **Light theme** — not for v1. Don't spend time on it.

---

## Favicon Spec

The favicon is a geometric **"d"** lettermark:
- Dark background matching `--bg-primary` (#0F1117)
- The "d" rendered in `--accent` (#6C8EEF)
- Simple, geometric, recognizable at 16x16
- No gradients, no detail that's lost at small sizes

See attached `favicon.svg`.

Render to: favicon.ico (multi-size: 16, 32, 48), apple-touch-icon.png (180x180), og-image icon (512x512).

---

## Deliverables Checklist (for UI team)

- [ ] CSS custom properties file with all tokens above
- [ ] Dark theme implementation (the only theme)
- [ ] Chat message component with agent color system
- [ ] Sidebar with real-time agent status + activity feed
- [ ] Attention banner ("N tasks need you")
- [ ] Task list view with status pills
- [ ] Tab navigation (Tasks, Agents, Reviews)
- [ ] Team selector dropdown (only shows when >1 team)
- [ ] Empty state with terminal commands
- [ ] Diff review view with inline comments
- [ ] Keyboard shortcut system
- [ ] Favicon in all required sizes
