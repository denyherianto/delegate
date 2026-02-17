import { teams, projectModalOpen } from "../state.js";

export function NoTeamsModal() {
  // Only show when teams array is loaded AND empty
  // Need to distinguish "not yet fetched" from "fetched but empty"
  if (teams.value === null || teams.value.length > 0) return null;

  return (
    <div class="no-teams-backdrop">
      <div class="no-teams-modal">
        <div class="no-teams-header">
          <h2>No projects configured</h2>
        </div>
        <div class="no-teams-body">
          <p>Create a project to get started:</p>
          <div class="no-teams-commands">
            <button
              class="npm-btn npm-btn-create"
              onClick={() => { projectModalOpen.value = true; }}
            >
              + New Project
            </button>
          </div>
          <p class="no-teams-hint">Or from the CLI:</p>
          <div class="no-teams-commands">
            <code>delegate team add &lt;name&gt;</code>
          </div>
          <p class="no-teams-hint">The page will update automatically once a project is created.</p>
        </div>
      </div>
    </div>
  );
}
