import { useEffect, useState } from "preact/hooks";
import { managerTurnContext, agentLastActivity, agents } from "../state.js";

function capitalize(str) {
  return str ? str.charAt(0).toUpperCase() + str.slice(1) : "";
}

function truncate(str, maxLen) {
  if (!str || str.length <= maxLen) return str;
  return str.slice(0, maxLen) + "...";
}

export function ManagerActivityBar() {
  const [timeoutCleared, setTimeoutCleared] = useState(false);
  const turnCtx = managerTurnContext.value;
  const lastActivity = agentLastActivity.value;

  // Safety timeout: if no activity update for 5 seconds and no turn_ended, clear context
  useEffect(() => {
    if (!turnCtx) {
      setTimeoutCleared(false);
      return;
    }

    const timer = setTimeout(() => {
      if (managerTurnContext.value && managerTurnContext.value.agent === turnCtx.agent) {
        managerTurnContext.value = null;
        setTimeoutCleared(true);
      }
    }, 5000);

    return () => clearTimeout(timer);
  }, [turnCtx, lastActivity]);

  if (!turnCtx) return null;

  // Check if the active agent is the manager
  const agentList = agents.value;
  const managerAgent = agentList.find(a => a.role === "manager");
  if (!managerAgent || managerAgent.name !== turnCtx.agent) {
    return null;
  }

  // Build context string
  let contextString = "";
  if (turnCtx.task_id !== null && turnCtx.task_id !== undefined) {
    const taskIdStr = String(turnCtx.task_id).padStart(4, "0");
    contextString = `is working on T${taskIdStr}`;
  } else if (turnCtx.sender) {
    contextString = `is thinking about ${capitalize(turnCtx.sender)}'s message`;
  } else {
    contextString = "is thinking";
  }

  // Build tool string from agentLastActivity
  let toolString = "";
  const activity = lastActivity[turnCtx.agent];
  if (activity && activity.tool) {
    const now = Date.now();
    const activityTime = new Date(activity.timestamp).getTime();
    const ageMs = now - activityTime;
    // Only show tool info if it's recent (within last 10 seconds)
    if (ageMs < 10000) {
      const toolName = activity.tool.toLowerCase();
      const detail = activity.detail ? " " + truncate(activity.detail, 40) : "";
      toolString = `: ${toolName}${detail}`;
    }
  }

  const fullText = `${capitalize(turnCtx.agent)} ${contextString}${toolString}`;

  return (
    <div class="manager-activity-bar">
      <div class="manager-activity-dot"></div>
      <div class="manager-activity-text">{fullText}</div>
    </div>
  );
}
