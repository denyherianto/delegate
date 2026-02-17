import { useState, useCallback, useRef, useEffect } from "preact/hooks";
import { projectModalOpen, teams, navigate } from "../state.js";
import * as api from "../api.js";

// ---------------------------------------------------------------------------
// NewProjectModal
// ---------------------------------------------------------------------------

export function NewProjectModal() {
  const isOpen = projectModalOpen.value;
  const [name, setName] = useState("");
  const [repoPath, setRepoPath] = useState("");
  const [agentCount, setAgentCount] = useState(2);
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
      setAgentCount(2);
      setModel("sonnet");
      setError("");
      setSubmitting(false);
    }
  }, [isOpen]);

  const close = useCallback(() => {
    projectModalOpen.value = false;
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

    setSubmitting(true);
    try {
      const result = await api.createProject({
        name: trimmed,
        repoPath: repoPath.trim(),
        agentCount,
        model,
      });
      // Refresh teams list
      const updatedTeams = await api.fetchTeams();
      teams.value = updatedTeams;
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
          <h2 class="npm-title">New Project</h2>
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
            <input
              id="npm-repo"
              class="npm-input"
              type="text"
              placeholder="/Users/you/dev/my-project"
              value={repoPath}
              onInput={(e) => setRepoPath(e.target.value)}
              disabled={submitting}
              autocomplete="off"
            />
            <span class="npm-hint">Absolute path to a local git repository</span>
          </div>

          {/* Agent count + Model (side by side) */}
          <div class="npm-row">
            <div class="npm-field npm-field-half">
              <label class="npm-label" for="npm-agents">Agents</label>
              <div class="npm-stepper">
                <button
                  type="button"
                  class="npm-stepper-btn"
                  onClick={() => setAgentCount(Math.max(1, agentCount - 1))}
                  disabled={submitting || agentCount <= 1}
                >-</button>
                <span class="npm-stepper-value">{agentCount}</span>
                <button
                  type="button"
                  class="npm-stepper-btn"
                  onClick={() => setAgentCount(Math.min(8, agentCount + 1))}
                  disabled={submitting || agentCount >= 8}
                >+</button>
              </div>
            </div>

            <div class="npm-field npm-field-half">
              <label class="npm-label" for="npm-model">Model</label>
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
