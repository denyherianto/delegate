import { useState, useCallback, useRef, useEffect } from "preact/hooks";
import { projectModalOpen, teams, navigate, updateLastGreeted } from "../state.js";
import * as api from "../api.js";
import { FileAutocomplete } from "./FileAutocomplete.jsx";

// ---------------------------------------------------------------------------
// NewProjectModal
// ---------------------------------------------------------------------------

export function NewProjectModal() {
  const isOpen = projectModalOpen.value;
  const [name, setName] = useState("");
  const [repoPath, setRepoPath] = useState("");
  const [agentCount, setAgentCount] = useState(5);
  const [model, setModel] = useState("sonnet");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const nameRef = useRef(null);

  // Auto-focus name field when modal opens
  useEffect(() => {
    if (isOpen && nameRef.current) {
      nameRef.current.focus();
    }
    if (isOpen) {
      // Reset form
      setName("");
      setRepoPath("");
      setAgentCount(5);
      setModel("sonnet");
      setError("");
      setSubmitting(false);
    }
  }, [isOpen]);

  const close = useCallback(() => {
    projectModalOpen.value = false;
  }, []);

  // Fetch path completions for the repo path FileAutocomplete.
  // Only show directories (repos must be directories). Return { path, hasGit }
  // objects so FileAutocomplete can render the git badge.
  const fetchRepoPaths = useCallback(async (q) => {
    const entries = await api.completeFiles(q);
    return entries
      .filter(e => e.is_dir)
      .map(e => ({ path: e.path + "/", hasGit: e.has_git }));
  }, []);

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    setError("");

    const trimmed = name.trim().toLowerCase().replace(/\s+/g, "-");
    if (!trimmed) {
      setError("Project name is required");
      return;
    }
    if (!repoPath.trim()) {
      setError("Repository path is required");
      return;
    }

    const count = parseInt(agentCount, 10);
    if (!count || count < 1) {
      setError("Agent count must be at least 1");
      return;
    }

    setSubmitting(true);
    try {
      const result = await api.createProject({
        name: trimmed,
        repoPath: repoPath.trim(),
        agentCount: count,
        model,
      });
      // Refresh teams list
      const updatedTeams = await api.fetchTeams();
      teams.value = updatedTeams;
      // Seed the lastGreeted timestamp so the team-switch greeting
      // logic knows the welcome was already handled (server sends
      // the first-run welcome during project creation).
      updateLastGreeted(result.name);
      // Navigate to the new project's chat
      navigate(result.name, "chat");
      close();
    } catch (err) {
      setError(err.message || "Failed to create project");
    } finally {
      setSubmitting(false);
    }
  }, [name, repoPath, agentCount, model, close]);

  // Handle Escape key
  const handleKeyDown = useCallback((e) => {
    if (e.key === "Escape") close();
  }, [close]);

  if (!isOpen) return null;

  return (
    <div class="modal-overlay" onClick={close} onKeyDown={handleKeyDown}>
      <div class="npm-modal" onClick={(e) => e.stopPropagation()}>
        <div class="npm-header">
          <h2 class="npm-title">{!teams.value || teams.value.length === 0 ? "Create your first project" : "New Project"}</h2>
          <button class="npm-close" onClick={close} title="Close">&times;</button>
        </div>

        <form class="npm-form" onSubmit={handleSubmit}>
          {/* Project name */}
          <div class="npm-field">
            <label class="npm-label" for="npm-name">Project name</label>
            <input
              ref={nameRef}
              id="npm-name"
              class="npm-input"
              type="text"
              placeholder="my-project"
              value={name}
              onInput={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9-_]/g, "-"))}
              disabled={submitting}
              autocomplete="off"
            />
            <span class="npm-hint">Lowercase, hyphens and underscores only</span>
          </div>

          {/* Repository path */}
          <div class="npm-field">
            <label class="npm-label" for="npm-repo">Repository path</label>
            <FileAutocomplete
              value={repoPath}
              onChange={setRepoPath}
              onSelect={setRepoPath}
              onCancel={() => {}}
              fetchSuggestions={fetchRepoPaths}
              placeholder="/Users/you/dev/my-project"
              className="npm-repo-ac"
              autoFocus={false}
            />
            <span class="npm-hint">Absolute path to a local git repository</span>
          </div>

          {/* Agent count + Model (side by side) */}
          <div class="npm-row">
            <div class="npm-field npm-field-half">
              <label class="npm-label" for="npm-agents">Agents</label>
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                id="npm-agents"
                class="npm-agents-input"
                value={agentCount}
                onInput={(e) => {
                  const raw = e.target.value.replace(/[^0-9]/g, "");
                  setAgentCount(raw === "" ? "" : Math.max(1, parseInt(raw, 10)));
                }}
                onBlur={() => {
                  const n = parseInt(agentCount, 10);
                  if (!n || n < 1) setAgentCount(5);
                }}
                disabled={submitting}
                autocomplete="off"
              />
              <span class="npm-field-hint">You can always add more agents later.</span>
            </div>

            <div class="npm-field npm-field-half">
              <label class="npm-label" for="npm-model">Model</label>
              <div class="npm-select-wrap">
                <select
                  id="npm-model"
                  class="npm-select"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  disabled={submitting}
                >
                  <option value="sonnet">Sonnet</option>
                  <option value="opus">Opus</option>
                </select>
              </div>
              <span class="npm-hint">You can change the model later</span>
            </div>
          </div>

          {/* Error message */}
          {error && <div class="npm-error">{error}</div>}

          {/* Actions */}
          <div class="npm-actions">
            <button
              type="button"
              class="npm-btn npm-btn-cancel"
              onClick={close}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              class="npm-btn npm-btn-create"
              disabled={submitting}
            >
              {submitting ? "Creating..." : "Create Project"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
