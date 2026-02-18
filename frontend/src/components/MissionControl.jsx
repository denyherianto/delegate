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

/** Build enriched agent data for ALL agents, sorted: active first, then idle alpha. */
function buildAgentList(agentsList, turnState, allTasks) {
  const result = [];

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

    result.push({
      name: a.name,
      team,
      role: a.role || "engineer",
      model: a.model || "sonnet",
      inTurn,
      taskId: lastTaskId,
      taskTitle,
      taskStatus,
      sender,
    });
  }

  // Active first (preserve order), then idle alphabetically
  result.sort((a, b) => {
    if (a.inTurn !== b.inTurn) return a.inTurn ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  return result;
}

/** Get last N activity entries for a given agent from the log. */
function getRecentActivities(log, agentName, n = 4) {
  return log
    .filter(e => e.agent === agentName && e.type === "agent_activity")
    .slice(-n);
}

// ---------------------------------------------------------------------------
// Status summary — fits on one line next to the name
// ---------------------------------------------------------------------------

function getStatusSummary(agent) {
  if (agent.taskId && agent.taskTitle) {
    const verb = getStatusVerb(agent.taskStatus);
    if (verb) return `${verb} ${taskIdStr(agent.taskId)}`;
    return taskIdStr(agent.taskId);
  }
  if (agent.sender) return `responding to ${cap(agent.sender)}`;
  if (agent.inTurn) return "working";
  return "idle";
}

function getStatusVerb(taskStatus) {
  switch (taskStatus) {
    case "in_progress": return "working on";
    case "in_review":   return "reviewing";
    case "merge_failed": return "fixing merge for";
    case "todo":        return "assigned to";
    default: return null;
  }
}

// ---------------------------------------------------------------------------
// Cycling verb — shown before first thinking text arrives
// ---------------------------------------------------------------------------

const THINKING_WORDS = [
  "thinking", "pondering", "noodling", "considering", "mulling",
  "reasoning", "deliberating", "reflecting", "processing", "contemplating",
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
    <span class={"mc-cycling" + (fading ? " mc-cycling-out" : "")}>
      {THINKING_WORDS[index]}…
    </span>
  );
}

// ---------------------------------------------------------------------------
// SVG Icons
// ---------------------------------------------------------------------------

/** Small thinking icon — aligned with the agent dot */
function ThinkingIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none"
         stroke="currentColor" strokeWidth="1.5"
         strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="6" r="5" />
      <path d="M6 11.5c0 1 .9 2.5 2 2.5s2-1.5 2-2.5" />
    </svg>
  );
}

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
    return <svg {...p}><path d="M11.5 1.5l3 3L5 14H2v-3z" /></svg>;
  }
  if (t.includes("bash") || t.includes("shell") || t.includes("exec") || t.includes("run")) {
    return <svg {...p}><path d="M2 12l4-4-4-4" /><path d="M8 12h6" /></svg>;
  }
  if (t.includes("search") || t.includes("grep") || t.includes("find")) {
    return <svg {...p}><circle cx="7" cy="7" r="4" /><path d="M10.5 10.5L14 14" /></svg>;
  }
  if (t.includes("list") || t.includes("ls") || t.includes("glob")) {
    return <svg {...p}><path d="M3 4h10" /><path d="M3 8h10" /><path d="M3 12h10" /></svg>;
  }
  return <svg {...p}><circle cx="8" cy="8" r="2.5" fill="currentColor" stroke="none" /></svg>;
}

// ---------------------------------------------------------------------------
// AgentRow — unified: one line for all agents, expandable body for active ones
// ---------------------------------------------------------------------------

function AgentRow({ agent, thinking, activities }) {
  const streamRef = useRef(null);
  const thinkingText = thinking?.text || "";

  // Auto-scroll thinking stream to bottom — always, since scrollbar is hidden
  useEffect(() => {
    const el = streamRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [thinkingText]);

  const status = getStatusSummary(agent);
  const hasThinking = thinkingText.length > 0;

  // ── Tool epoch logic ──
  // The backend inserts "---" into thinking text when new thinking arrives
  // after tools ran.  Count separators = epoch.  Only show tools that
  // arrived in the current (latest) epoch.
  const epoch = (thinkingText.match(/\n\n---\n\n/g) || []).length;
  const epochToolCountRef = useRef(0);
  const prevEpochRef = useRef(0);
  const prevActivityLenRef = useRef(0);

  // Reset tool count when epoch advances (new thinking after tools)
  if (epoch !== prevEpochRef.current) {
    epochToolCountRef.current = 0;
    prevActivityLenRef.current = activities.length;
    prevEpochRef.current = epoch;
  }

  // Count new tools in this epoch
  if (activities.length > prevActivityLenRef.current) {
    epochToolCountRef.current += activities.length - prevActivityLenRef.current;
    prevActivityLenRef.current = activities.length;
  }

  // Show last 2 tools from this epoch only
  const toolsInEpoch = epochToolCountRef.current;
  const recentTools = toolsInEpoch > 0
    ? activities.slice(-Math.min(toolsInEpoch, 2))
    : [];

  return (
    <div class={"mc-row" + (agent.inTurn ? " mc-row-active" : "")} onClick={() => openPanel("agent", agent.name)}>
      {/* ── Line 1: dot · name · status ── */}
      <div class="mc-row-header">
        <span class={"mc-dot " + (agent.inTurn ? "dot-active" : "dot-idle")} />
        <span class="mc-name">{cap(agent.name)}</span>
        <span class="mc-status">{status}</span>
      </div>

      {/* ── Active body: thinking stream + tools ── */}
      {agent.inTurn && (
        <div class="mc-row-body">
          {/* Thinking stream (or cycling verb placeholder) */}
          {hasThinking ? (
            <div class="mc-entry" onClick={(e) => e.stopPropagation()}>
              <span class="mc-entry-icon"><ThinkingIcon /></span>
              <div
                class="mc-thinking-stream"
                ref={streamRef}
                dangerouslySetInnerHTML={{ __html: renderMarkdown(thinkingText) }}
              />
            </div>
          ) : (
            <div class="mc-entry">
              <span class="mc-entry-icon"><ThinkingIcon /></span>
              <span class="mc-entry-text"><CyclingVerb /></span>
            </div>
          )}

          {/* Tool entries — last 2 from current epoch */}
          {recentTools.map((act, i) => {
            const detail = act.detail
              ? act.detail.split("/").pop().substring(0, 40)
              : "";
            return (
              <div key={`${act.tool}-${act.timestamp}-${i}`} class="mc-entry" onClick={(e) => e.stopPropagation()}>
                <span class="mc-entry-icon"><ToolIcon tool={act.tool} /></span>
                <span class="mc-entry-text">
                  <span class="mc-tool-name">{act.tool.toLowerCase()}</span>
                  {detail && <span class="mc-tool-detail">{detail}</span>}
                </span>
              </div>
            );
          })}
        </div>
      )}
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

  const agents = buildAgentList(allAgentsList, turnState, allTasks);

  if (agents.length === 0) {
    return (
      <div class="mc">
        <div class="mc-body">
          <div class="mc-empty">No agents</div>
        </div>
      </div>
    );
  }

  return (
    <div class="mc">
      <div class="mc-body">
        {agents.map(a => (
          <AgentRow
            key={`${a.team}-${a.name}`}
            agent={a}
            thinking={thinking[a.name]}
            activities={getRecentActivities(activityLog, a.name)}
          />
        ))}
      </div>
    </div>
  );
}
