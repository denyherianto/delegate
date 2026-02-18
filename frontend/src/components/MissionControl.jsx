import { useEffect, useRef, useState } from "preact/hooks";
import {
  allTeamsAgents, allTeamsTurnState, tasks,
  agentActivityLog, agentThinking,
  openPanel,
} from "../state.js";
import { cap, taskIdStr, renderMarkdown } from "../utils.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Build enriched agent data for ALL agents. Returns two lists:
 *   active — agents with inTurn === true (in source/append order)
 *   idle   — all others, sorted alphabetically by name
 */
function buildAgentLists(agentsList, turnState, allTasks) {
  const active = [];
  const idle = [];

  for (const a of agentsList) {
    const team = a.team || "unknown";
    const turn = (turnState[team] || {})[a.name];
    const inTurn = turn?.inTurn ?? false;
    const lastTaskId = turn?.taskId ?? null;
    const sender = turn?.sender ?? "";

    let taskTitle = "";
    let taskStatus = "";
    if (lastTaskId) {
      const task = allTasks.find(t => t.id === lastTaskId);
      if (task) {
        taskTitle = task.title || "";
        taskStatus = task.status || "";
      }
    }

    const entry = {
      name: a.name,
      team,
      role: a.role || "engineer",
      model: a.model || "sonnet",
      inTurn,
      taskId: lastTaskId,
      taskTitle,
      taskStatus,
      sender,
    };

    if (inTurn) {
      active.push(entry);
    } else {
      idle.push(entry);
    }
  }

  // Idle section: alphabetical by name
  idle.sort((a, b) => a.name.localeCompare(b.name));

  return { active, idle };
}

/** Get last N activity entries for a given agent from the log. */
function getRecentActivities(log, agentName, n = 3) {
  return log
    .filter(e => e.agent === agentName && e.type === "agent_activity")
    .slice(-n);
}

/**
 * Group idle agents by team. Returns array of { team, agents } sorted
 * alphabetically by team name.
 */
function groupIdleByTeam(idle) {
  const groups = {};
  for (const a of idle) {
    const t = a.team || "unknown";
    if (!groups[t]) groups[t] = [];
    groups[t].push(a);
  }
  return Object.keys(groups)
    .sort()
    .map(team => ({ team, agents: groups[team] }));
}

// ---------------------------------------------------------------------------
// Status summary
// ---------------------------------------------------------------------------

function getStatusSummary(agent) {
  if (agent.taskId && agent.taskTitle) {
    const verb = getStatusVerb(agent.taskStatus);
    if (verb) return capFirst(`${verb} ${taskIdStr(agent.taskId)}`);
    return capFirst(taskIdStr(agent.taskId));
  }
  if (agent.sender) return `Responding to ${cap(agent.sender)}`;
  if (agent.inTurn) return "Working";
  return "Idle";
}

function getStatusVerb(taskStatus) {
  switch (taskStatus) {
    case "in_progress": return "working on";
    case "in_review": return "reviewing";
    case "merge_failed": return "fixing merge for";
    case "todo": return "assigned to";
    default: return null;
  }
}

/** Capitalize first letter of a string. */
function capFirst(s) {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// ---------------------------------------------------------------------------
// Rotating thinking verb — shown while waiting for model response
// ---------------------------------------------------------------------------

const THINKING_WORDS = [
  "thinking",
  "pondering",
  "noodling",
  "considering",
  "mulling",
  "reasoning",
  "deliberating",
  "reflecting",
  "processing",
  "contemplating",
];

function CyclingVerb() {
  const [index, setIndex] = useState(0);
  const [fading, setFading] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setFading(true);
      setTimeout(() => {
        setIndex(prev => (prev + 1) % THINKING_WORDS.length);
        setFading(false);
      }, 200);
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  return (
    <span class={"mc-cycling-verb" + (fading ? " mc-cycling-out" : " mc-cycling-in")}>
      {THINKING_WORDS[index]}&hellip;
    </span>
  );
}

// ---------------------------------------------------------------------------
// SVG Icons
// ---------------------------------------------------------------------------

function ToolIcon({ tool }) {
  const t = tool.toLowerCase();
  const p = {
    width: "12", height: "12", viewBox: "0 0 16 16",
    fill: "none", stroke: "currentColor",
    strokeWidth: "1.5", strokeLinecap: "round", strokeLinejoin: "round",
  };

  if (t.includes("read") || t.includes("cat") || t.includes("view")) {
    return (
      <svg {...p}>
        <path d="M1 8s3-5.5 7-5.5S15 8 15 8s-3 5.5-7 5.5S1 8 1 8z" />
        <circle cx="8" cy="8" r="2" />
      </svg>
    );
  }
  if (t.includes("write") || t.includes("edit") || t.includes("patch") || t.includes("replace")) {
    return (
      <svg {...p}><path d="M11.5 1.5l3 3L5 14H2v-3z" /></svg>
    );
  }
  if (t.includes("bash") || t.includes("shell") || t.includes("exec") || t.includes("run")) {
    return (
      <svg {...p}><path d="M2 12l4-4-4-4" /><path d="M8 12h6" /></svg>
    );
  }
  if (t.includes("search") || t.includes("grep") || t.includes("find")) {
    return (
      <svg {...p}><circle cx="7" cy="7" r="4" /><path d="M10.5 10.5L14 14" /></svg>
    );
  }
  if (t.includes("list") || t.includes("ls") || t.includes("glob")) {
    return (
      <svg {...p}><path d="M3 4h10" /><path d="M3 8h10" /><path d="M3 12h10" /></svg>
    );
  }
  return (
    <svg {...p}><circle cx="8" cy="8" r="2.5" fill="currentColor" stroke="none" /></svg>
  );
}

// ---------------------------------------------------------------------------
// AgentCard — active agent, content-height card
// ---------------------------------------------------------------------------

function AgentCard({ agent, thinking, activities }) {
  const thinkingHtml = thinking?.text ? renderMarkdown(thinking.text) : null;
  const status = getStatusSummary(agent);

  return (
    <div class="mc-card">
      {/* Header: [dot] [name+status, flex:1] [model-badge] */}
      <div class="mc-card-header">
        <span class="mc-dot dot-active" />
        <div class="mc-header-content">
          <span
            class="mc-agent-name"
            onClick={() => openPanel("agent", agent.name)}
          >
            {cap(agent.name)}
          </span>
          <span class="mc-header-status">{status}</span>
        </div>
        <span class="mc-badge mc-badge-model">{agent.model}</span>
      </div>

      {/* Card body */}
      <div class="mc-card-body">
        {/* Thinking text — markdown rendered, soft height cap */}
        {thinkingHtml ? (
          <div class="mc-thinking-block">
            <div class="mc-thinking-label">
              <span class="mc-thinking-indicator" />
              <span>Thinking</span>
            </div>
            <div
              class="mc-thinking-text agent-markdown-content"
              dangerouslySetInnerHTML={{ __html: thinkingHtml }}
/>
          </div>
        ) : agent.inTurn ? (
          <div class="mc-stream-waiting"><CyclingVerb /></div>
        ) : null}

        {/* Tool entries — last 3 */}
        {activities.length > 0 && (
          <div class="mc-stream-tools">
            {activities.map((act, i) => {
              const detail = act.detail
                ? act.detail.split("/").pop().substring(0, 40)
                : "";
              const diffLines = act.diff && act.diff.length > 0 ? act.diff.slice(0, 3) : null;
              return (
                <div key={i} class="mc-tool-entry">
                  <div class="mc-tool-entry-row">
                    <span class="mc-tool-icon">
                      <ToolIcon tool={act.tool} />
                    </span>
                    <span class="mc-tool-name">{act.tool.toLowerCase()}</span>
                    {detail && <span class="mc-tool-detail">{detail}</span>}
                  </div>
                  {diffLines && (
                    <div class="mc-diff-block">
                      {diffLines.map((line, j) => {
                        const cls = line.startsWith("+")
                          ? "mc-diff-line mc-diff-add"
                          : line.startsWith("-")
                          ? "mc-diff-line mc-diff-del"
                          : "mc-diff-line mc-diff-ctx";
                        return <div key={j} class={cls}>{line}</div>;
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// IdleRow — single-line idle agent
// ---------------------------------------------------------------------------

function IdleRow({ agent }) {
  return (
    <div class="mc-idle-row" onClick={() => openPanel("agent", agent.name)}>
      <span class="mc-dot dot-idle" />
      <span class="mc-idle-name">{cap(agent.name)}</span>
      <span class="mc-badge mc-badge-model">{agent.model}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MissionControl
// ---------------------------------------------------------------------------

export function MissionControl() {
  const turnState = allTeamsTurnState.value;
  const thinking = agentThinking.value;
  const allAgentsList = allTeamsAgents.value;
  const allTasks = tasks.value;
  const activityLog = agentActivityLog.value;

  const { active, idle } = buildAgentLists(allAgentsList, turnState, allTasks);

  // ── Collapsed team state (all teams start collapsed) ──
  const [collapsedTeams, setCollapsedTeams] = useState({});

  function toggleTeam(teamName) {
    setCollapsedTeams(prev => ({ ...prev, [teamName]: !prev[teamName] }));
  }

  // Teams are collapsed by default (absent key = collapsed)
  function isCollapsed(teamName) {
    return collapsedTeams[teamName] !== false;
  }

  // ── Transition tracking ──
  // We track which agents are "exiting" from each section so we can play
  // fade-out animations before removing from DOM.

  // exitingCards: agents that just left the active section (fading out as cards)
  const [exitingCards, setExitingCards] = useState([]);
  // exitingIdleNames: agent names that just left the idle section (fading out as rows)
  const [exitingIdleNames, setExitingIdleNames] = useState([]);
  // enteringCardNames: agents that just entered the active section (fading in)
  const [enteringCardNames, setEnteringCardNames] = useState(new Set());

  const prevActiveNamesRef = useRef(new Set());

  const currentActiveNames = new Set(active.map(a => a.name));

  useEffect(() => {
    const prev = prevActiveNamesRef.current;
    const cur = currentActiveNames;

    // Agents newly becoming active
    const newlyActive = [...cur].filter(n => !prev.has(n));
    if (newlyActive.length) {
      setEnteringCardNames(new Set(newlyActive));
      // These agents' idle rows should fade out
      setExitingIdleNames(prev2 => [...new Set([...prev2, ...newlyActive])]);
      const t = setTimeout(() => {
        setEnteringCardNames(new Set());
        setExitingIdleNames(prev2 => prev2.filter(n => !newlyActive.includes(n)));
      }, 250);
      return ()=> clearTimeout(t);
    }

    // Agents newly becoming idle
    const newlyIdle = [...prev].filter(n => !cur.has(n));
    if (newlyIdle.length) {
      const exitAgents = allAgentsList
        .filter(a => newlyIdle.includes(a.name))
        .map(a => ({
          name: a.name,
          team: a.team || "unknown",
          role: a.role || "engineer",
          model: a.model || "sonnet",
          inTurn: false,
          taskId: null, taskTitle: "", taskStatus: "", sender: "",
        }));
      setExitingCards(prev2 => [...prev2, ...exitAgents.filter(a => !prev2.some(p => p.name === a.name))]);
      const t = setTimeout(() => {
        setExitingCards(prev2 => prev2.filter(a => !newlyIdle.includes(a.name)));
      }, 200);
      return () => clearTimeout(t);
    }

    prevActiveNamesRef.current = cur;
  }, [JSON.stringify([...currentActiveNames].sort())]);

  // Update prev ref after render
  useEffect(() => {
    prevActiveNamesRef.current = new Set(active.map(a => a.name));
  });

  const showActiveSection = active.length > 0 || exitingCards.length > 0;

  const idleGroups = groupIdleByTeam(idle);

  return (
    <div class="mc">
      <div class="mc-header">
        <span class="mc-title">Mission Control</span>
      </div>

      <div class="mc-body">
        {/* ── Active section ── */}
        {showActiveSection && (
          <div class="mc-section">
            <div class="mc-section-label">Active</div>

            {/* Cards fading out (became idle) */}
            {exitingCards.map(a => (
              <div key={`exit-${a.name}`} class="mc-card-exit">
                <AgentCard agent={a} thinking={null} activities={[]} />
              </div>
            ))}

            {/* Active cards */}
            {active.map(a => (
              <div
                key={`${a.team}-${a.name}`}
                class={enteringCardNames.has(a.name) ? "mc-card-enter" : ""}
              >
                <AgentCard
                  agent={a}
                  thinking={thinking[a.name]}
                  activities={getRecentActivities(activityLog, a.name)}
                />
              </div>
            ))}
          </div>
        )}

        {/* ── Idle section — grouped by team, each team collapsible ── */}
        {idle.length > 0 && (
          <div class="mc-section mc-section-idle">
            <div class="mc-section-label">Idle</div>
            {idleGroups.map(({ team, agents }) => {
              const collapsed = isCollapsed(team);
              return (
                <div key={team}>
                  {/* Team header row */}
                  <div
                    class="mc-idle-team-row"
                    onClick={() => toggleTeam(team)}
                  >
                    <span class="mc-idle-team-name">{team}</span>
                    <span class="mc-idle-team-count">· {agents.length} idle</span>
                    <span class="mc-idle-toggle">{collapsed ? "▸" : "▾"}</span>
                  </div>
                  {/* Agent rows — only when expanded */}
                  {!collapsed && agents.map(a => (
                    <div
                      key={`${a.team}-${a.name}`}
                      class={exitingIdleNames.includes(a.name) ? "mc-idle-row-exit" : ""}
                    >
                      <IdleRow agent={a} />
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        )}

        {/* No agents at all */}
        {active.length === 0 && idle.length === 0 && exitingCards.length === 0 && (
          <div class="mc-empty">
            <div class="mc-empty-text">No agents</div>
          </div>
        )}
      </div>
    </div>
  );
}
