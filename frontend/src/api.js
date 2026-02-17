/**
 * Centralized API fetch functions.
 * Each function returns parsed JSON (or throws).
 */

export async function fetchConfig() {
  const r = await fetch("/config");
  return r.ok ? r.json() : {};
}

export async function fetchBootstrap(team = null) {
  const qs = team ? `?team=${encodeURIComponent(team)}` : "";
  const r = await fetch(`/bootstrap${qs}`);
  return r.ok ? r.json() : null;
}

export async function fetchTeams() {
  const r = await fetch("/teams");
  if (!r.ok) return [];
  const data = await r.json();
  // Backend returns [{name, team_id, agent_count, task_count, human_count, created_at}, ...]
  if (data.length > 0 && typeof data[0] === "object") {
    return data;  // Return full objects
  }
  // Fallback for plain string arrays
  return data.map(name => ({ name, agent_count: 0, task_count: 0, human_count: 0 }));
}

export async function fetchTasks(team) {
  const r = await fetch(`/teams/${team}/tasks`);
  return r.ok ? r.json() : [];
}

export async function fetchAllTasks() {
  const r = await fetch(`/api/tasks?team=all`);
  return r.ok ? r.json() : [];
}

export async function fetchAgents(team) {
  const r = await fetch(`/teams/${team}/agents`);
  return r.ok ? r.json() : [];
}

export async function fetchAgentsCrossTeam() {
  const r = await fetch("/api/agents?team=all");
  return r.ok ? r.json() : [];
}

export async function fetchAgentActivity(team, agentName, n = 100) {
  const r = await fetch(`/teams/${team}/agents/${agentName}/activity?n=${n}`);
  return r.ok ? r.json() : [];
}

export async function addAgent(team, name, options = {}) {
  const r = await fetch(`/teams/${team}/agents/add`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, ...options }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

export async function fetchMessages(team, params) {
  // Filter out undefined/null params
  const cleanParams = {};
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        cleanParams[key] = value;
      }
    }
  }
  const qs = Object.keys(cleanParams).length ? "?" + new URLSearchParams(cleanParams).toString() : "";
  const r = await fetch(`/teams/${team}/messages${qs}`);
  return r.ok ? r.json() : [];
}

export async function sendMessage(team, recipient, content) {
  const r = await fetch(`/teams/${team}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recipient, content }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

export async function greetTeam(team, lastSeen = null) {
  const url = lastSeen
    ? `/teams/${team}/greet?last_seen=${encodeURIComponent(lastSeen)}`
    : `/teams/${team}/greet`;
  const r = await fetch(url, {
    method: "POST",
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

// --- Task endpoints: Use global /api/tasks/{id}/... versions below ---

export async function fetchAgentTab(team, agentName, tab) {
  const r = await fetch(`/teams/${team}/agents/${agentName}/${tab}`);
  return r.ok ? r.json() : null;
}

export async function fetchAgentStats(team, agentName) {
  const r = await fetch(`/teams/${team}/agents/${agentName}/stats`);
  return r.ok ? r.json() : null;
}

export async function fetchAllAgentStats(team) {
  const r = await fetch(`/teams/${team}/agents/stats`);
  return r.ok ? r.json() : {};
}

export async function fetchFileContent(team, path, opts = {}) {
  const r = await fetch(`/teams/${team}/files/content?path=${encodeURIComponent(path)}`, { signal: opts.signal });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to load file");
  }
  return r.json();
}

// --- Magic Commands ---

export async function execShell(team, command, cwd) {
  const r = await fetch(`/teams/${team}/exec/shell`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, cwd: cwd || undefined }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

export async function saveCommand(team, command, result) {
  const r = await fetch(`/teams/${team}/commands`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, result }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

export async function fetchCostSummary(team) {
  const r = await fetch(`/teams/${team}/cost-summary`);
  return r.ok ? r.json() : null;
}

// --- Global task endpoints (no team context needed) ---

export async function fetchTaskDiff(taskId) {
  const r = await fetch(`/api/tasks/${taskId}/diff`);
  return r.ok ? r.json() : { diff: {}, branch: "" };
}

export async function fetchTaskStats(taskId) {
  const r = await fetch(`/api/tasks/${taskId}/stats`);
  return r.ok ? r.json() : null;
}

export async function fetchTaskActivity(taskId, limit = 50) {
  const url = `/api/tasks/${taskId}/activity${limit ? `?limit=${limit}` : ''}`;
  const r = await fetch(url);
  return r.ok ? r.json() : [];
}

export async function fetchTaskComments(taskId) {
  const r = await fetch(`/api/tasks/${taskId}/comments`);
  return r.ok ? r.json() : [];
}

export async function postTaskComment(taskId, author, body) {
  const r = await fetch(`/api/tasks/${taskId}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ author, body }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

export async function fetchTaskMergePreview(taskId) {
  const r = await fetch(`/api/tasks/${taskId}/merge-preview`);
  return r.ok ? r.json() : { diff: {}, branch: "" };
}

export async function fetchTaskCommits(taskId) {
  const r = await fetch(`/api/tasks/${taskId}/commits`);
  return r.ok ? r.json() : { commit_diffs: {} };
}

export async function retryMerge(taskId) {
  const r = await fetch(`/api/tasks/${taskId}/retry-merge`, {
    method: "POST",
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

export async function cancelTask(taskId) {
  const r = await fetch(`/api/tasks/${taskId}/cancel`, {
    method: "POST",
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

export async function fetchReviews(taskId) {
  const r = await fetch(`/api/tasks/${taskId}/reviews`);
  return r.ok ? r.json() : [];
}

export async function fetchCurrentReview(taskId) {
  const r = await fetch(`/api/tasks/${taskId}/reviews/current`);
  return r.ok ? r.json() : { attempt: 0, verdict: null, summary: "", comments: [] };
}

export async function postReviewComment(taskId, { file, line, body }) {
  const r = await fetch(`/api/tasks/${taskId}/reviews/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file, line: line || null, body }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

export async function updateReviewComment(taskId, commentId, body) {
  const r = await fetch(`/api/tasks/${taskId}/reviews/comments/${commentId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

export async function deleteReviewComment(taskId, commentId) {
  const r = await fetch(`/api/tasks/${taskId}/reviews/comments/${commentId}`, {
    method: "DELETE",
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

export async function approveTask(taskId, summary = "") {
  const r = await fetch(`/api/tasks/${taskId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ summary }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

export async function rejectTask(taskId, reason, summary = "") {
  const r = await fetch(`/api/tasks/${taskId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason || "(no reason)", summary: summary || reason || "(no reason)" }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

// --- File Upload ---

export async function uploadFiles(team, files, onProgress) {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const xhr = new XMLHttpRequest();
  return new Promise((resolve, reject) => {
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new Error(xhr.responseText || `Upload failed: ${xhr.status}`));
      }
    };
    xhr.onerror = () => reject(new Error("Upload failed: network error"));
    xhr.open("POST", `/teams/${team}/uploads`);
    xhr.send(formData);
  });
}
