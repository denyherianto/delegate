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
  const turnCtx = managerTurnContext.value;
  const lastActivity = agentLastActivity.value;

  // Safety timeout: clear the indicator if no activity arrives for 30 seconds.
  // The timestamp on managerTurnContext is bumped on every activity SSE event
  // for the manager (see app.jsx), so this only fires if the stream truly stalls
  // (e.g. SSE disconnect without a turn_ended).
  useEffect(() => {
    if (!turnCtx) return;

    const timer = setTimeout(() => {
      if (managerTurnContext.value && managerTurnContext.value.agent === turnCtx.agent) {
        managerTurnContext.value = null;
      }
    }, 30000);

    return () => clearTimeout(timer);
  }, [turnCtx?.agent, turnCtx?.timestamp]);

  if (!turnCtx) return null;

  // Check if the active agent is the manager
  const agentList = agents.value;
  const managerAgent = agentList.find(a => a.role === "manager");
  if (!managerAgent || managerAgent.name !== turnCtx.agent) {
    return null;
  }

  // Build context string (task_id takes priority over sender)
  let contextString = "";
  if (turnCtx.task_id !== null && turnCtx.task_id !== undefined) {
    const taskIdStr = String(turnCtx.task_id).padStart(4, "0");
    contextString = `T${taskIdStr}`;
  } else if (turnCtx.sender) {
    contextString = capitalize(turnCtx.sender);
  } else {
    contextString = "";
  }

  // Build message string from agentLastActivity
  let messageString = "";
  const activity = lastActivity[turnCtx.agent];
  if (activity && activity.tool) {
    const now = Date.now();
    const activityTime = new Date(activity.timestamp).getTime();
    const ageMs = now - activityTime;
    // Only show tool info if it's recent (within last 10 seconds)
    if (ageMs < 10000) {
      const toolName = activity.tool;
      const detail = activity.detail ? " " + truncate(activity.detail, 40) : "";
      messageString = (
        <>
          <span class="tool-name">{toolName}</span>
          <span class="tool-command">{detail}</span>
        </>
      );
    }
  }

  // Default to "thinking..." if no tool activity
  if (!messageString) {
    messageString = <span class="thinking">thinking...</span>;
  }

  const agentName = capitalize(turnCtx.agent);

  return (
    <div class="manager-activity-bar">
      <div class="manager-activity-dot"></div>
      <div class="manager-activity-text">
        {agentName}
        <span class="arrow"> -&gt; </span>
        {contextString && <>{contextString}: </>}
        {messageString}
      </div>
    </div>
  );
}
