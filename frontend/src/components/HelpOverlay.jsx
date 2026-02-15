import { helpOverlayOpen } from "../state.js";

export function HelpOverlay() {
  const isOpen = helpOverlayOpen.value;

  if (!isOpen) return null;

  const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

  const navigationShortcuts = [
    { key: "c", description: "Go to Chat" },
    { key: "t", description: "Go to Tasks" },
    { key: "a", description: "Go to Agents" },
    { key: "s", description: "Toggle sidebar" },
    { key: "n", description: "Toggle notifications" },
    { key: isMac ? "Cmd+K" : "Ctrl+K", description: "Switch team" },
  ];

  const actionShortcuts = [
    { key: "r", description: "Focus chat input" },
    { key: "/", description: "Search messages" },
    { key: "m", description: "Toggle microphone" },
    { key: isMac ? "Cmd+Down" : "Ctrl+End", description: "Scroll to bottom" },
    { key: "Esc", description: "Close / defocus" },
    { key: "?", description: "This help" },
  ];

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      helpOverlayOpen.value = false;
    }
  };

  return (
    <>
      <div class="help-backdrop open" onClick={handleBackdropClick} />
      <div class="help-overlay open">
        <div class="help-overlay-header">
          <h2 class="help-overlay-title">Keyboard Shortcuts</h2>
        </div>
        <div class="help-overlay-body">
          <div class="help-overlay-column">
            <h3 class="help-column-title">Navigation</h3>
            {navigationShortcuts.map(({ key, description }) => (
              <div class="help-shortcut-row" key={key}>
                <kbd class="help-shortcut-key">{key}</kbd>
                <span class="help-shortcut-desc">{description}</span>
              </div>
            ))}
          </div>
          <div class="help-overlay-column">
            <h3 class="help-column-title">Actions</h3>
            {actionShortcuts.map(({ key, description }) => (
              <div class="help-shortcut-row" key={key}>
                <kbd class="help-shortcut-key">{key}</kbd>
                <span class="help-shortcut-desc">{description}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
