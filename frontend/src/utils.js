/**
 * Pure formatting & utility helpers.
 * No side effects, no DOM access, no state.
 * Exception: useLiveTimer is a Preact hook exported for shared use.
 */
import { useState, useEffect } from "preact/hooks";
import { html as diff2HtmlRender, parse as diff2HtmlParse } from "diff2html";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { hcHome } from "./state.js";

// Configure marked for GFM
marked.setOptions({ gfm: true, breaks: true });

// ── Emoji post-processing: replace colorful/3D emojis with flat text ──
const _emojiMap = {
  "\uD83D\uDE80": "->",   // 🚀
  "\u2728": "*",           // ✨
  "\uD83D\uDD25": "*",    // 🔥
  "\uD83C\uDF89": "--",   // 🎉
  "\uD83C\uDF8A": "--",   // 🎊
  "\uD83D\uDCA1": "*",    // 💡
  "\uD83D\uDCDD": "-",    // 📝
  "\uD83C\uDFAF": "->",   // 🎯
  "\u26A1": "*",           // ⚡
  "\uD83D\uDEE0\uFE0F": "-", // 🛠️
  "\uD83D\uDEE0": "-",    // 🛠
  "\uD83D\uDCCA": "-",    // 📊
  "\uD83D\uDC4D": "+",    // 👍
  "\uD83D\uDC4E": "-",    // 👎
  "\u2705": "+",           // ✅
  "\u274C": "x",           // ❌
  "\u26A0\uFE0F": "!",    // ⚠️
  "\u26A0": "!",           // ⚠
  "\uD83D\uDCA5": "!",    // 💥
  "\uD83D\uDCAC": "-",    // 💬
  "\uD83D\uDCE6": "-",    // 📦
  "\uD83D\uDD0D": "-",    // 🔍
  "\uD83D\uDD12": "-",    // 🔒
  "\uD83D\uDD13": "-",    // 🔓
  "\uD83C\uDF1F": "*",    // 🌟
  "\uD83D\uDCAA": "-",    // 💪
  "\uD83E\uDD14": "?",    // 🤔
  "\uD83D\uDC40": "-",    // 👀
  "\u270F\uFE0F": "-",    // ✏️
  "\uD83D\uDCCB": "-",    // 📋
  "\uD83D\uDCC1": "-",    // 📁
  "\uD83D\uDCC2": "-",    // 📂
  "\uD83D\uDCCE": "-",    // 📎
  "\uD83D\uDCC4": "-",    // 📄
  "\uD83D\uDD27": "-",    // 🔧
  "\uD83E\uDDE9": "-",    // 🧩
  "\uD83D\uDEA8": "!",    // 🚨
  "\uD83D\uDED1": "x",    // 🛑
  "\uD83D\uDFE2": "+",    // 🟢
  "\uD83D\uDFE1": "!",    // 🟡
  "\uD83D\uDD34": "x",    // 🔴
  "\uD83D\uDFE0": "!",    // 🟠
  "\uD83D\uDE4F": "-",    // 🙏
  "\u2B50": "*",           // ⭐
  "\uD83C\uDF10": "-",    // 🌐
  "\uD83D\uDCBB": "-",    // 💻
  "\uD83D\uDD17": "-",    // 🔗
};
let _emojiRegex = null;
function _getEmojiRegex() {
  if (!_emojiRegex) {
    const keys = Object.keys(_emojiMap).map(k => k.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&"));
    _emojiRegex = new RegExp(keys.join("|"), "g");
  }
  return _emojiRegex;
}
export function stripEmojis(text) {
  if (!text) return text;
  return text.replace(_getEmojiRegex(), (match) => _emojiMap[match] || "");
}

// ── Markdown ──
const _mdCache = new Map();
const _MD_CACHE_MAX = 200;

export function renderMarkdown(text) {
  if (!text) return "";
  if (_mdCache.has(text)) return _mdCache.get(text);
  const html = DOMPurify.sanitize(marked.parse(stripEmojis(text)));
  if (_mdCache.size >= _MD_CACHE_MAX) {
    // Evict oldest entry
    const firstKey = _mdCache.keys().next().value;
    _mdCache.delete(firstKey);
  }
  _mdCache.set(text, html);
  return html;
}

// ── Formatting ──
export function cap(s) {
  if (!s) return "";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// Convert a slug (hyphens/underscores as word separators) to title-case display name.
// Examples: "my-project" -> "My Project", "q4_launch" -> "Q4 Launch"
export function prettyName(slug) {
  if (!slug) return "";
  return slug
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, c => c.toUpperCase());
}

export function fmtStatus(s) {
  if (!s) return "";
  return s.split("_").map(w => cap(w)).join(" ");
}

export function fmtTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

export function relativeTimeParts(iso) {
  if (!iso) return null;
  const sec = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  const min = Math.floor(sec / 60);
  const hr = Math.floor(min / 60);
  const days = Math.floor(hr / 24);
  return { sec, min, hr, days };
}

export function fmtTimestamp(iso) {
  if (!iso) return "\u2014";
  const t = relativeTimeParts(iso);
  if (!t) return "\u2014";
  if (t.sec < 60) return "Just now";
  if (t.min < 60) return t.min + " min ago";
  const d = new Date(iso);
  const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  if (t.hr < 24) return time;
  const mon = d.toLocaleDateString([], { month: "short", day: "numeric" });
  return mon + ", " + time;
}

export function fmtRelativeTime(iso) {
  const t = relativeTimeParts(iso);
  if (!t) return "";
  if (t.sec < 60) return "Just now";
  if (t.min < 60) return t.min + "m ago";
  if (t.hr < 24) return t.hr + "h ago";
  return t.days + "d ago";
}

export function fmtRelativeTimeShort(iso) {
  const t = relativeTimeParts(iso);
  if (!t) return "";
  if (t.sec < 60) return "<1m";
  if (t.min < 60) return t.min + "m";
  if (t.hr < 24) return t.hr + "h";
  return t.days + "d";
}

export function fmtElapsed(sec) {
  if (sec == null) return "\u2014";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m > 0 ? m + "m " + s + "s" : s + "s";
}

export function fmtTokens(tin, tout) {
  if (tin == null && tout == null) return "\u2014";
  return Number(tin || 0).toLocaleString() + " / " + Number(tout || 0).toLocaleString();
}

export function fmtTokensShort(n) {
  if (n == null || n === 0) return "0";
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return String(n);
}

export function fmtCost(usd) {
  if (usd == null) return "\u2014";
  return "$" + Number(usd).toFixed(2);
}

export function fmtDuration(sec) {
  if (sec == null || sec === 0) return "\u2014";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (h > 0) return h + "h " + m + "m";
  return m + "m";
}

// ── Escaping ──
const _escDiv = typeof document !== "undefined" ? document.createElement("div") : null;
export function esc(s) {
  if (!_escDiv) return String(s || "");
  _escDiv.textContent = s;
  return _escDiv.innerHTML;
}

// ── Avatars ──
const _avatarColors = [
  "#7DD3FC", "#C4B5FD", "#FCA5A5", "#6EE7B7",
  "#FDE68A", "#F9A8D4", "#E8E9ED",
];
export function avatarColor(name) {
  let h = 0;
  for (let i = 0; i < (name || "").length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
  return _avatarColors[Math.abs(h) % _avatarColors.length];
}
export function avatarInitial(name) {
  return (name || "?").charAt(0).toUpperCase();
}

// ── Multi-repo helpers ──
export function flattenDiffDict(diff) {
  if (!diff) return "";
  if (typeof diff === "string") return diff;
  if (typeof diff !== "object") return "";
  const keys = Object.keys(diff);
  if (keys.length === 0) return "";
  if (keys.length === 1) return diff[keys[0]] || "";
  return keys.map(repo => "# \u2500\u2500 " + repo + " \u2500\u2500\n" + (diff[repo] || "(no diff)")).join("\n\n");
}

export function flattenCommitsDict(commits) {
  if (!commits) return [];
  if (Array.isArray(commits)) return commits;
  if (typeof commits !== "object") return [];
  const all = [];
  Object.keys(commits).forEach(repo => {
    (commits[repo] || []).forEach(c => all.push(c));
  });
  return all;
}

// ── Linkify helpers (produce HTML strings for dangerouslySetInnerHTML) ──
export function linkifyTaskRefs(html) {
  return html.replace(/(^[^<]+|>[^<]*)/g, match =>
    match.replace(/(?<!\/)T(\d{4})\b/g, (full, digits) => {
      const id = parseInt(digits, 10);
      // Skip T0000 (system placeholder)
      if (id === 0) return full;
      return '<span class="task-link copyable" data-task-id="' + id + '">' + full + copyBtnHtml(full) + "</span>";
    })
  );
}

/**
 * Normalise a file path for the /teams/{team}/files/content endpoint.
 *
 * Absolute paths pass through unchanged.  Old delegate-relative paths
 * (no leading "/") also pass through -- the backend resolves them from
 * hc_home for backward compatibility.
 */
export function toApiPath(raw, team) {
  // Absolute paths and delegate-relative paths both pass through as-is.
  // Backend resolves relative paths from ~/.delegate for backward compat.
  return raw;
}

/**
 * Shorten a file path for display.
 *
 * Absolute paths under the user home directory are tilde-shortened
 * (e.g. /Users/x/.delegate/teams/... -> ~/.delegate/teams/...).
 * Other paths are shown in full.
 */
export function displayFilePath(path) {
  if (!path) return path;
  const home = hcHome.value;
  if (!home) return path;
  // hcHome = "/Users/x/.delegate"; derive user home as its parent
  const userHome = home.replace(/\/\.delegate$/, "");
  if (userHome && path.startsWith(userHome + "/")) {
    return "~" + path.substring(userHome.length);
  }
  return path;
}

export function linkifyFilePaths(html) {
  // Match:
  //  1. Tilde-prefixed paths: ~/anything/path
  //  2. Absolute paths with at least 2 segments: /foo/bar (avoids bare "/" or single-segment paths)
  return html.replace(/(^[^<]+|>[^<]*)/g, match =>
    match.replace(/(?:(?<=\s|^)~\/[\w\-\.\/]+[\w\/]|(?<=\s|^)\/[\w\-\.\/]+\/[\w\-\.\/]*\w)/g, path => {
      const display = displayFilePath(path);
      return '<span class="file-link copyable" data-file-path="' + esc(path) + '">' + esc(display) + copyBtnHtml(path) + "</span>";
    })
  );
}

export function agentifyRefs(html, agentNames) {
  if (!agentNames || !agentNames.length) return html;
  const pattern = new RegExp(
    "\\b(" + agentNames.map(n => n.charAt(0).toUpperCase() + n.slice(1)).join("|") + ")(?!/)",
    "g"
  );
  return html.replace(/(^[^<]+|>[^<]*)/g, match =>
    match.replace(pattern, full =>
      '<span class="agent-link copyable" data-agent-name="' + full.toLowerCase() + '">' + full + copyBtnHtml(full) + "</span>"
    )
  );
}

// ── diff2html wrappers ──
export { diff2HtmlRender, diff2HtmlParse };

// ── Task sorting ──
// Priority tiers for task ordering.  When a workflow is loaded, the tier
// can be derived from stage properties (terminal → bottom, auto → top).
// Fallback hardcoded mapping is kept for backward compatibility.
const _tierMap = {
  in_approval: 0, merging: 0, merge_failed: 0,
  in_progress: 1, in_review: 1,
  todo: 2,
  done: 3, cancelled: 4,
};
export function taskTier(t) {
  if (t.status in _tierMap) return _tierMap[t.status];
  // Workflow stages not in the hardcoded map: use generic heuristic
  // Terminal stages → bottom, auto stages → top, others → middle
  return 2;
}

export function taskIdStr(id) {
  return "T" + String(id).padStart(4, "0");
}

// ── Roles ──
export const roleBadgeMap = {
  engineer: "Engineer", worker: "Worker", manager: "Manager", qa: "QA",
  design: "Design", backend: "Backend", frontend: "Frontend",
};

// ── Agent dot helpers ──
export function getAgentDotClass(agent, tasksList, stats) {
  if (!agent.pid) return "dot-offline";
  const assignedTask = tasksList.find(t => t.assignee === agent.name && t.status === "in_progress");
  const taskUpdated = assignedTask ? new Date(assignedTask.updated_at) : null;
  const lastActive = stats && stats.last_active ? new Date(stats.last_active) : null;
  const timestamps = [taskUpdated, lastActive].filter(Boolean);
  const isManager = agent.role === "manager";
  if (timestamps.length === 0) return isManager ? "dot-manager-active" : "dot-active";
  const mostRecent = new Date(Math.max(...timestamps));
  const minutesAgo = (Date.now() - mostRecent.getTime()) / 60000;
  if (minutesAgo <= 5) return isManager ? "dot-manager-active" : "dot-active";
  if (minutesAgo <= 30) return "dot-stale";
  return "dot-stuck";
}

export function getAgentDotTooltip(dotClass, agent, tasksList) {
  if (dotClass === "dot-offline") return "Offline";
  const assignedTask = tasksList.find(t => t.assignee === agent.name && t.status === "in_progress");
  const lastTs = assignedTask && assignedTask.updated_at ? assignedTask.updated_at : null;
  const timeStr = lastTs ? fmtRelativeTime(lastTs) : "";
  if (dotClass === "dot-active" || dotClass === "dot-manager-active") return "Active" + (timeStr ? " \u2014 last activity " + timeStr : "");
  if (dotClass === "dot-stale") return "May be stuck" + (timeStr ? " \u2014 last activity " + timeStr : "");
  if (dotClass === "dot-stuck") return "Likely stuck" + (timeStr ? " \u2014 last activity " + timeStr : "");
  return "";
}

// ── Copy-to-clipboard utility ──
const _copySvg = '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="9" height="9" rx="1.5"/><path d="M5 11H3.5A1.5 1.5 0 0 1 2 9.5v-7A1.5 1.5 0 0 1 3.5 1h7A1.5 1.5 0 0 1 12 2.5V5"/></svg>';
const _checkSvg = '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 8 7 12 13 4"/></svg>';

/** Inline copy icon HTML to append inside linkified spans. */
export function copyBtnHtml(text) {
  return '<span class="copy-btn" data-copy="' + esc(text) + '" title="Copy">' + _copySvg + '</span>';
}

/** Handle a click on a .copy-btn element — copies text & shows checkmark. */
export function handleCopyClick(el) {
  const text = el.dataset.copy;
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    el.innerHTML = _checkSvg;
    el.classList.add("copied");
    setTimeout(() => {
      el.innerHTML = _copySvg;
      el.classList.remove("copied");
    }, 1500);
  }).catch(() => {});
}

/** Inline copy icon SVG strings for use in Preact components. */
export const COPY_SVG = _copySvg;
export const CHECK_SVG = _checkSvg;

// ── Message status icon (HTML string) ──
// Single check = seen, double check = processed, all grayscale
export function msgStatusIcon(m) {
  if (m.processed_at) return '<span class="msg-status msg-processed" title="Processed">\u2713\u2713</span>';
  if (m.seen_at) return '<span class="msg-status msg-seen" title="Seen">\u2713</span>';
  if (m.delivered_at) return '<span class="msg-status msg-delivered" title="Delivered"></span>';
  return '';
}

// ── File icon helper ──
function getFileIcon(ext) {
  const icons = {
    pdf: 'PDF',
    md: 'MD',
    txt: 'TXT',
    csv: 'CSV',
    json: 'JSON',
    yaml: 'YAML',
    yml: 'YAML',
    zip: 'ZIP',
    html: 'HTML',
    css: 'CSS',
    js: 'JS',
    py: 'PY',
    svg: 'SVG',
  };
  return icons[ext] || ext.toUpperCase();
}

// ── File reference rendering ──
export function renderFileReferences(html, team) {
  // Match [file:path/to/file.ext] tokens
  // Replace with appropriate HTML based on file type

  const fileRefPattern = /\[file:([~\w/._-]+)\]/g;

  return html.replace(fileRefPattern, (match, filePath) => {
    const ext = filePath.split('.').pop().toLowerCase();
    const fileName = filePath.split('/').pop();
    let url;
    if (filePath.startsWith('/') || filePath.startsWith('~')) {
      // Detect upload paths and use the direct file-serving route
      const uploadMatch = filePath.match(/\/uploads\/(\d{4})\/(\d{2})\/(.+)$/);
      if (uploadMatch) {
        const [, year, month, fname] = uploadMatch;
        url = `/teams/${team}/uploads/${year}/${month}/${encodeURIComponent(fname)}`;
      } else {
        url = `/teams/${team}/files/content?path=${encodeURIComponent(filePath)}`;
      }
    } else {
      url = `/teams/${team}/${filePath}`;
    }

    const imageExts = ['png', 'jpg', 'jpeg', 'gif', 'webp'];

    if (imageExts.includes(ext)) {
      // Render inline image thumbnail
      return `<div class="file-preview file-preview-image">
        <a href="${url}" target="_blank" rel="noopener">
          <img src="${url}" alt="${esc(fileName)}" class="file-preview-img" loading="lazy" />
        </a>
        <span class="file-preview-name">${esc(fileName)}</span>
      </div>`;
    } else {
      // Render download link (including SVG for security)
      return `<a href="${url}" class="file-preview file-preview-link" download="${esc(fileName)}">
        <span class="file-preview-icon">${getFileIcon(ext)}</span>
        <span class="file-preview-name">${esc(fileName)}</span>
      </a>`;
    }
  });
}

// ── Compact duration formatter ──
// Given elapsed milliseconds, returns a compact single-unit string:
// "42s", "14m", "3h", "2d" — largest unit only.
export function fmtCompactDuration(ms) {
  if (ms < 0) ms = 0;
  const s = Math.floor(ms / 1000);
  if (s < 60) return s + "s";
  const m = Math.floor(s / 60);
  if (m < 60) return m + "m";
  const h = Math.floor(m / 60);
  if (h < 24) return h + "h";
  const d = Math.floor(h / 24);
  return d + "d";
}

// ── Live elapsed timer hook ──
// Returns a compact elapsed string (e.g. "42s", "14m") that updates every
// second.  Pass an ISO timestamp as startIso; returns null when startIso is
// falsy.  Shared by AgentRow, TaskSidePanel, DiffPanel, etc.
export function useLiveTimer(startIso) {
  const [elapsed, setElapsed] = useState(() =>
    startIso ? fmtCompactDuration(Date.now() - new Date(startIso).getTime()) : null
  );
  useEffect(() => {
    if (!startIso) { setElapsed(null); return; }
    const tick = () => setElapsed(fmtCompactDuration(Date.now() - new Date(startIso).getTime()));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startIso]);
  return elapsed;
}
