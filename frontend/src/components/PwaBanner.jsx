import { signal } from "@preact/signals";
import { lsKey } from "../state.js";

// Tracks the deferred beforeinstallprompt event so we can call .prompt() later
let deferredInstallEvent = null;

// Whether the install banner is visible (set to true when beforeinstallprompt fires)
const showInstallBanner = signal(false);

// Whether the "use the app" banner is visible (per-session, resets on page load)
const showUseAppBanner = signal(false);

// Are we in standalone (PWA) mode?
function isStandalone() {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true
  );
}

// Set up the beforeinstallprompt listener once at module load time so we
// capture the event even if PwaBanner hasn't mounted yet.
if (!isStandalone()) {
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredInstallEvent = e;
    // Only show if user hasn't permanently dismissed
    if (!localStorage.getItem(lsKey("pwa-banner-dismissed"))) {
      showInstallBanner.value = true;
      // Install banner takes priority — hide the "use the app" banner
      showUseAppBanner.value = false;
    }
  });
}

// Determine initial "use the app" banner visibility on load.
// Shown when: PWA was previously installed, we're in browser mode, and not
// dismissed this session. The install banner (if it appears) overrides this.
function initUseAppBanner() {
  if (isStandalone()) return;
  if (localStorage.getItem(lsKey("pwa-installed")) !== "true") return;
  // Per-session dismiss: use a sessionStorage flag
  if (sessionStorage.getItem("pwa-use-app-dismissed")) return;
  showUseAppBanner.value = true;
}

initUseAppBanner();

export function PwaBanner() {
  // Install banner handlers
  function handleInstall() {
    if (!deferredInstallEvent) return;
    deferredInstallEvent.prompt();
    deferredInstallEvent.userChoice.then((choice) => {
      if (choice.outcome === "accepted") {
        localStorage.setItem(lsKey("pwa-installed"), "true");
      }
      deferredInstallEvent = null;
      showInstallBanner.value = false;
    });
  }

  function handleInstallDismiss() {
    localStorage.setItem(lsKey("pwa-banner-dismissed"), "true");
    showInstallBanner.value = false;
  }

  // "Use the app" banner handler
  function handleUseAppDismiss() {
    sessionStorage.setItem("pwa-use-app-dismissed", "true");
    showUseAppBanner.value = false;
  }

  if (showInstallBanner.value) {
    return (
      <div class="pwa-banner">
        <span>Install Delegate as a desktop app for the best experience</span>
        <div>
          <button class="pwa-install-btn" onClick={handleInstall}>Install</button>
          <button class="pwa-dismiss-btn" onClick={handleInstallDismiss}>&#x2715;</button>
        </div>
      </div>
    );
  }

  if (showUseAppBanner.value && !isStandalone()) {
    return (
      <div class="pwa-banner">
        <span>Delegate is installed as a desktop app — for the best experience, open it from your Dock or Spotlight.</span>
        <button class="pwa-dismiss-btn" onClick={handleUseAppDismiss}>&#x2715;</button>
      </div>
    );
  }

  return null;
}
