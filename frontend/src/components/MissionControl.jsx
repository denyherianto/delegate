import { useCallback, useEffect, useRef, useState } from "preact/hooks";
import {
  allTeamsAgents, allTeamsTurnState, tasks,
  agentActivityLog, agentThinking,
  missionControlCollapsed, missionControlManuallyCollapsed,
  openPanel,
} from "../state.js";
import { cap, taskIdStr } from "../utils.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a flat list of active agents across all teams with enriched data. */
function buildActiveAgentList(agentsList, turnState, allTasks) {
  const result = [];
  for (const a of agentsList) {
    const team = a.team || "unknown";
    const turn = (turnState[team] || {})[a.name];
    const inTurn = turn?.inTurn ?? false;
    const lastTaskId = turn?.taskId ?? null;
    const sender = turn?.sender ?? "";

    // Only include agents that are doing something
    if (!inTurn && !lastTaskId) continue;

    let taskTitle = "";
    let taskStatus = "";
    if (lastTaskId) {
      const task = allTasks.find(t => t.id === lastTaskId);
      if (task) {
        taskTitle = task.title || "";
        taskStatus = task.status || "";
      }
    }

    result.push({
      name: a.name,
      team,
      inTurn,
      taskId: lastTaskId,
      taskTitle,
      taskStatus,
      sender,
    });
  }

  // Sort: actively working first, then waiting, then alpha
  result.sort((a, b) => {
    const order = (x) => x.inTurn ? 0 : 1;
    const diff = order(a) - order(b);
    if (diff !== 0) return diff;
    return a.name.localeCompare(b.name);
  });

  return result;
}

/** Get last N activity entries for a given agent from the log. */
function getRecentActivities(log, agentName, n = 5) {
  return log
    .filter(e => e.agent === agentName && e.type === "agent_activity")
    .slice(-n);
}

// ---------------------------------------------------------------------------
// Status verb mapping
// ---------------------------------------------------------------------------

function getStatusVerb(taskStatus) {
  switch (taskStatus) {
    case "in_progress": return "working on";
    case "in_review": return "reviewing";
    case "merge_failed": return "fixing merge for";
    case "todo": return "assigned to";
    default: return null;
  }
}

// ---------------------------------------------------------------------------
// SVG Icons
// ---------------------------------------------------------------------------

/** Chevron icon for card expand/collapse */
function ChevronIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none"
         stroke="currentColor" strokeWidth="1.5"
         strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3,1 7,5 3,9" />
    </svg>
  );
}

/** Toggle icon for panel collapse/expand */
function MCToggleIcon({ collapsed }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
         stroke="currentColor" strokeWidth="1.5"
         strokeLinecap="round" strokeLinejoin="round">
      {collapsed
        ? <polyline points="9,3 4,7 9,11" />
        : <polyline points="5,3 10,7 5,11" />}
    </svg>
  );
}

/** Small tool-type icon for the timeline. */
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
      <svg {...p}>
        <path d="M11.5 1.5l3 3L5 14H2v-3z" />
      </svg>
    );
  }
  if (t.includes("bash") || t.includes("shell") || t.includes("exec") || t.includes("run")) {
    return (
      <svg {...p}>
        <path d="M2 12l4-4-4-4" />
        <path d="M8 12h6" />
      </svg>
    );
  }
  if (t.includes("search") || t.includes("grep") || t.includes("find")) {
    return (
      <svg {...p}>
        <circle cx="7" cy="7" r="4" />
        <path d="M10.5 10.5L14 14" />
      </svg>
    );
  }
  if (t.includes("list") || t.includes("ls") || t.includes("glob")) {
    return (
      <svg {...p}>
        <path d="M3 4h10" />
        <path d="M3 8h10" />
        <path d="M3 12h10" />
      </svg>
    );
  }
  // Default: small filled circle
  return (
    <svg {...p}>
      <circle cx="8" cy="8" r="2.5" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Empty-state icon (radar / monitoring) */
function EmptyIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.2"
         strokeLinecap="round" strokeLinejoin="round" class="mc-empty-icon">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 12l4-4" />
      <circle cx="12" cy="12" r="2" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// AgentCard
// ---------------------------------------------------------------------------

function AgentCard({ agent, thinking, activities, expanded, onToggle }) {
  const thinkingRef = useRef(null);

  // Auto-scroll thinking area to bottom as new text streams in
  useEffect(() => {
    const el = thinkingRef.current;
    if (el && thinking?.text) {
      // Only auto-scroll if user hasn't scrolled up significantly
      const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
      if (isNearBottom) {
        el.scrollTop = el.scrollHeight;
      }
    }
  }, [thinking?.text]);

  const dotClass = agent.inTurn ? "dot-active" : "dot-waiting";
  const verb = agent.taskStatus ? getStatusVerb(agent.taskStatus) : null;

  return (
    <div class={"mc-card" + (expanded ? " mc-card-expanded" : "")}>
      {/* Header: dot + name + team + chevron */}
      <div class="mc-card-header" onClick={onToggle}>
        <span class={"mc-dot " + dotClass} />
        <span
          class="mc-agent-name"
          onClick={(e) => { e.stopPropagation(); openPanel("agent", agent.name); }}
        >
          {cap(agent.name)}
        </span>
        <span class="mc-agent-team">{agent.team}</span>
        <span class={"mc-chevron" + (expanded ? " mc-chevron-open" : "")}>
          <ChevronIcon />
        </span>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div class="mc-card-body">
          {/* Task line */}
          {agent.taskId && (
            <div
              class="mc-card-task"
              onClick={() => openPanel("task", agent.taskId)}
            >
              <span class="mc-task-id">{taskIdStr(agent.taskId)}</span>
              {agent.taskTitle && (
                <span class="mc-task-title">
                  {verb ? `${verb} ` : ""}{agent.taskTitle}
                </span>
              )}
            </div>
          )}

          {/* Responding to (non-task message) */}
          {!agent.taskId && agent.sender && (
            <div class="mc-card-task">
              responding to {cap(agent.sender)}
            </div>
          )}

          {/* Thinking trace — full scrollable inset panel */}
          {thinking && thinking.text ? (
            <div class="mc-thinking">
              <div class="mc-thinking-header">
                <span class="mc-thinking-indicator" />
                <span>Thinking</span>
              </div>
              <div class="mc-thinking-text" ref={thinkingRef}>
                {thinking.text}
              </div>
            </div>
          ) : agent.inTurn ? (
            <div class="mc-idle">Waiting for model response…</div>
          ) : null}

          {/* Tool timeline */}
          {activities.length > 0 && (
            <div class="mc-tools">
              <div class="mc-tools-label">Recent tools</div>
              {activities.map((act, i) => {
                const detail = act.detail
                  ? act.detail.split("/").pop().substring(0, 40)
                  : "";
                return (
                  <div key={i} class="mc-tool-entry">
                    <span class="mc-tool-icon">
                      <ToolIcon tool={act.tool} />
                    </span>
                    <span class="mc-tool-name">{act.tool.toLowerCase()}</span>
                    {detail && <span class="mc-tool-detail">{detail}</span>}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// MissionControl
// ---------------------------------------------------------------------------

export function MissionControl() {
  const collapsed = missionControlCollapsed.value;
  const turnState = allTeamsTurnState.value;
  const thinking = agentThinking.value;
  const allAgentsList = allTeamsAgents.value;
  const allTasks = tasks.value;
  const activityLog = agentActivityLog.value;

  const activeAgents = buildActiveAgentList(allAgentsList, turnState, allTasks);
  const hasActive = activeAgents.length > 0;

  // --- Per-card expand/collapse ---
  // Cards that are manually collapsed by the user
  const [collapsedCards, setCollapsedCards] = useState(new Set());

  const toggleCard = useCallback((agentName) => {
    setCollapsedCards(prev => {
      const next = new Set(prev);
      if (next.has(agentName)) {
        next.delete(agentName);
      } else {
        next.add(agentName);
      }
      return next;
    });
  }, []);

  // By default agents are expanded; user can collapse individual cards
  const isExpanded = (agentName) => !collapsedCards.has(agentName);

  // --- Auto-collapse / expand logic ---
  const graceTimer = useRef(null);

  useEffect(() => {
    // Don't auto-toggle if user manually collapsed
    if (missionControlManuallyCollapsed.value) return;

    if (hasActive && collapsed) {
      // Auto-expand immediately
      missionControlCollapsed.value = false;
    } else if (!hasActive && !collapsed) {
      // Auto-collapse after grace period
      graceTimer.current = setTimeout(() => {
        if (!missionControlManuallyCollapsed.value) {
          missionControlCollapsed.value = true;
        }
      }, 5000);
    }

    return () => {
      if (graceTimer.current) clearTimeout(graceTimer.current);
    };
  }, [hasActive, collapsed]);

  const toggle = useCallback(() => {
    const next = !missionControlCollapsed.value;
    missionControlCollapsed.value = next;
    missionControlManuallyCollapsed.value = next;
  }, []);

  // Fully hidden when collapsed and no agents
  if (collapsed && !hasActive) return null;

  // --- Rail mode (collapsed but has active agents) ---
  if (collapsed) {
    return (
      <div class="mc mc-rail">
        <div class="mc-header">
          <button class="mc-toggle" onClick={toggle} title="Expand Mission Control">
            <MCToggleIcon collapsed={true} />
          </button>
        </div>
        <div class="mc-rail-dots">
          {activeAgents.map(a => (
            <div
              key={`${a.team}-${a.name}`}
              class={"mc-rail-dot " + (a.inTurn ? "dot-active" : "dot-waiting")}
              title={`${cap(a.name)} (${a.team})`}
              onClick={toggle}
            />
          ))}
        </div>
      </div>
    );
  }

  // --- Full panel ---
  return (
    <div class="mc">
      <div class="mc-header">
        <span class="mc-title">Mission Control</span>
        <button class="mc-toggle" onClick={toggle} title="Collapse">
          <MCToggleIcon collapsed={false} />
        </button>
      </div>

      <div class="mc-cards">
        {activeAgents.map(a => (
          <AgentCard
            key={`${a.team}-${a.name}`}
            agent={a}
            thinking={thinking[a.name]}
            activities={getRecentActivities(activityLog, a.name)}
            expanded={isExpanded(a.name)}
            onToggle={() => toggleCard(a.name)}
          />
        ))}
        {!hasActive && (
          <div class="mc-empty">
            <EmptyIcon />
            <div class="mc-empty-text">No active agents</div>
          </div>
        )}
      </div>
    </div>
  );
}
