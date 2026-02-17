import { useCallback, useEffect, useRef } from "preact/hooks";
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
function getRecentActivities(log, agentName, n = 3) {
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
// AgentCard
// ---------------------------------------------------------------------------

function AgentCard({ agent, thinking, activities }) {
  const dotClass = agent.inTurn ? "dot-active" : "dot-waiting";
  const verb = agent.taskStatus ? getStatusVerb(agent.taskStatus) : null;

  return (
    <div class="mc-card">
      {/* Header: dot + name + team badge */}
      <div class="mc-card-header">
        <span class={"mc-dot " + dotClass}></span>
        <span
          class="mc-agent-name"
          onClick={() => openPanel("agent", agent.name)}
        >
          {cap(agent.name)}
        </span>
        <span class="mc-agent-team">{agent.team}</span>
      </div>

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

      {/* Thinking line — the "alive" feeling */}
      {thinking && thinking.text && (
        <div class="mc-thinking">
          <span class="mc-thinking-indicator"></span>
          <span class="mc-thinking-text">{thinking.text}</span>
        </div>
      )}

      {/* Recent tool calls */}
      {activities.map((act, i) => {
        const detail = act.detail
          ? act.detail.split("/").pop().substring(0, 30)
          : "";
        return (
          <div key={i} class="mc-tool-line">
            {act.tool.toLowerCase()}{detail ? `: ${detail}` : ""}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Toggle icon
// ---------------------------------------------------------------------------

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

  return (
    <div class={"mc" + (collapsed ? " mc-collapsed" : "")}>
      <div class="mc-header">
        <span class="mc-title">Mission Control</span>
        <button class="mc-toggle" onClick={toggle} title={collapsed ? "Expand" : "Collapse"}>
          <MCToggleIcon collapsed={collapsed} />
        </button>
      </div>

      {!collapsed && (
        <div class="mc-cards">
          {activeAgents.map(a => (
            <AgentCard
              key={`${a.team}-${a.name}`}
              agent={a}
              thinking={thinking[a.name]}
              activities={getRecentActivities(activityLog, a.name)}
            />
          ))}
          {!hasActive && (
            <div class="mc-empty">No active agents</div>
          )}
        </div>
      )}
    </div>
  );
}
