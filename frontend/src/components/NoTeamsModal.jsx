import { useEffect } from "preact/hooks";
import { teams, projectModalOpen } from "../state.js";

// When no projects exist, open NewProjectModal directly — no intermediate step.
export function NoTeamsModal() {
  const isEmpty = teams.value !== null && teams.value.length === 0;

  useEffect(() => {
    if (isEmpty) {
      projectModalOpen.value = true;
    }
  }, [isEmpty]);

  return null;
}
