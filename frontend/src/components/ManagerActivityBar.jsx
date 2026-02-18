import { useEffect, useRef, useState } from "preact/hooks";
import {
  managerTurnContext, agentLastActivity, agentActivityLog,
  agentThinking, agents,
} from "../state.js";
import { cap, taskIdStr, renderMarkdown } from "../utils.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function truncate(str, maxLen) {
  if (!str || str.length <= maxLen) return str;
  return str.slice(0, maxLen) + "\u2026";
}

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

// ---------------------------------------------------------------------------
// CyclingVerb — animated thinking placeholder
// ---------------------------------------------------------------------------

function CyclingVerb() {
  const [index, setIndex] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setIsTransitioning(true);
      setTimeout(() => {
        setIndex((prev) => (prev + 1) % THINKING_WORDS.length);
        setIsTransitioning(false);
      }, 200);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <span class={"cycling-verb" + (isTransitioning ? " cycling-out" : " cycling-in")}>
      {THINKING_WORDS[index]}…
    </span>
  );
}

// ---------------------------------------------------------------------------
// useStreamingText — reveals text word-by-word for a streaming effect.
//
// When `fullText` grows (server sends more thinking), we animate the new
// portion in word by word (~50-80ms per word).  Already-revealed text
// is rendered as plain HTML; only the newest words get the `.word-in`
// animation class.
// ---------------------------------------------------------------------------

function useStreamingText(fullText) {
  const [revealedLen, setRevealedLen] = useState(0);
  const rafRef = useRef(null);
  const timerRef = useRef(null);

  // When fullText shrinks or is cleared (new turn), reset
  useEffect(() => {
    if (fullText.length === 0) {
      setRevealedLen(0);
      if (timerRef.current) clearTimeout(timerRef.current);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    }
  }, [fullText.length === 0]);

  // Animate towards full length
  useEffect(() => {
    if (revealedLen >= fullText.length) return;

    // Find the next word boundary
    function revealNext() {
      setRevealedLen(prev => {
        if (prev >= fullText.length) return prev;
        // Advance by one word (skip whitespace, then skip word chars)
        let i = prev;
        // skip whitespace
        while (i < fullText.length && /\s/.test(fullText[i])) i++;
        // skip word
        while (i < fullText.length && !/\s/.test(fullText[i])) i++;
        return i;
      });
    }

    timerRef.current = setTimeout(revealNext, 30 + Math.random() * 50);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [revealedLen, fullText.length]);

  return revealedLen;
}

// ---------------------------------------------------------------------------
// StreamingThinkingText — renders thinking with word-by-word animation
// ---------------------------------------------------------------------------

function StreamingThinkingText({ fullText, streamRef }) {
  const revealedLen = useStreamingText(fullText);

  // Split into revealed (stable) and new (animated) portions
  const revealed = fullText.slice(0, revealedLen);

  // Auto-scroll when more text is revealed
  useEffect(() => {
    const el = streamRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [revealedLen]);

  // Render the full revealed text as markdown
  // The newest words (last batch) get the word-in animation class
  // For simplicity and performance, we render the whole revealed text
  // as markdown; the streaming illusion comes from the progressive reveal.
  const html = renderMarkdown(revealed);

  return (
    <div
      class="delegate-thinking-stream"
      ref={streamRef}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

// ---------------------------------------------------------------------------
// DelegateThinkingFooter
//
// Shows Delegate's thinking inline in the chat panel when active.
//   - Hidden when Delegate is idle (0 height)
//   - Glass card with green accent when active
//   - Thinking text streams in word-by-word
// ---------------------------------------------------------------------------

export function ManagerActivityBar() {
  const turnCtx = managerTurnContext.value;
  const lastActivity = agentLastActivity.value;
  const thinking = agentThinking.value;
  const activityLog = agentActivityLog.value;
  const streamRef = useRef(null);

  // Identify the manager agent
  const agentList = agents.value;
  const managerAgent = agentList.find(a => a.role === "manager");
  const isActive = turnCtx && managerAgent && managerAgent.name === turnCtx.agent;

  // Derive manager data — always computed (never behind early returns)
  const managerName = turnCtx?.agent || "";
  const thinkingData = isActive ? thinking[managerName] : null;
  const thinkingText = thinkingData?.text || "";
  const hasThinking = thinkingText.length > 0;

  // Tool epoch logic (same as MissionControl AgentRow)
  const agentActivities = isActive
    ? activityLog.filter(e => e.agent === managerName && e.type === "agent_activity")
    : [];
  const breaks = (thinkingText.match(/\n\n---\n\n/g) || []).length;
  const unconsumedTools = Math.max(0, agentActivities.length - breaks);
  const recentTools = unconsumedTools > 0
    ? agentActivities.slice(-Math.min(unconsumedTools, 2))
    : [];

  // Context: what Delegate is working on
  let contextLabel = "";
  if (isActive) {
    if (turnCtx.task_id > 0 && turnCtx.sender) {
      contextLabel = `${cap(turnCtx.sender)} · ${taskIdStr(turnCtx.task_id)}`;
    } else if (turnCtx.task_id > 0) {
      contextLabel = taskIdStr(turnCtx.task_id);
    } else if (turnCtx.sender) {
      contextLabel = cap(turnCtx.sender);
    }
  }

  // ── Hooks (always called unconditionally) ──

  // Safety timeout: clear if no activity for 120s (SSE stall / disconnect).
  useEffect(() => {
    if (!turnCtx) return;
    const timer = setTimeout(() => {
      if (managerTurnContext.value && managerTurnContext.value.agent === turnCtx.agent) {
        managerTurnContext.value = null;
      }
    }, 120000);
    return () => clearTimeout(timer);
  }, [turnCtx?.agent, turnCtx?.timestamp]);

  // ── Render ──

  // Hidden — Delegate idle
  if (!isActive) {
    return <div class="delegate-footer" />;
  }

  // Status indicator for the header bar
  const activity = lastActivity[managerName];
  let statusText = null;
  if (activity && activity.tool) {
    const ageMs = Date.now() - new Date(activity.timestamp).getTime();
    if (ageMs < 10000) {
      const detail = activity.detail ? ": " + truncate(activity.detail, 48) : "";
      statusText = (
        <span class="delegate-footer-status">
          <span class="delegate-footer-tool">{activity.tool.toLowerCase()}</span>{detail}
        </span>
      );
    }
  }
  if (!statusText) {
    statusText = (
      <span class="delegate-footer-status delegate-footer-thinking">
        <CyclingVerb />
      </span>
    );
  }

  return (
    <div class={"delegate-footer delegate-footer-active" + (hasThinking ? " delegate-footer-expanded" : "")}>
      {/* Header bar */}
      <div class="delegate-footer-bar">
        <span class="delegate-footer-dots">
          <span class="delegate-dot" />
          <span class="delegate-dot" />
          <span class="delegate-dot" />
        </span>
        <span class="delegate-footer-text">
          <span class="delegate-footer-name">{cap(managerName)}</span>
          {contextLabel && (
            <>
              <span class="delegate-footer-sep"> · </span>
              <span class="delegate-footer-busy">{contextLabel}</span>
            </>
          )}
        </span>
        {statusText}
      </div>

      {/* Thinking stream — word-by-word streaming */}
      {hasThinking && (
        <div class="delegate-footer-stream">
          <StreamingThinkingText fullText={thinkingText} streamRef={streamRef} />

          {/* Tool entries — last 2 from current epoch */}
          {recentTools.map((act, i) => {
            const detail = act.detail
              ? act.detail.split("/").pop().substring(0, 50)
              : "";
            return (
              <div key={`${act.tool}-${act.timestamp}-${i}`} class="delegate-tool-line">
                <span class="delegate-tool-name">{act.tool.toLowerCase()}</span>
                {detail && <span class="delegate-tool-detail">{detail}</span>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
