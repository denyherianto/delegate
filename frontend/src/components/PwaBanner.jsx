import { useEffect } from "preact/hooks";
import { signal } from "@preact/signals";
import { lsKey } from "../state.js";

// Tracks the deferred beforeinstallprompt event so we can call .prompt() later
let deferredInstallEvent = null;

// Whether the install banner is visible (set to true when beforeinstallprompt fires)
const showInstallBanner = signal(false);

// Whether the "use the app" banner is visible (persists dismiss via localStorage)
const showUseAppBanner = signal(false);

// Are we in standalone (PWA) mode?
// Mac/Chrome PWAs may use window-controls-overlay instead of standalone.
// navigator.standalone is Safari-only; matchMedia covers Chrome/Edge.
function isStandalone() {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.matchMedia("(display-mode: window-controls-overlay)").matches ||
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

// Determine initial "use the app" banner visibility.
// Shown when: PWA was previously installed, we're in browser mode, and user
// hasn't permanently dismissed it.
// Called after mount (via useEffect) so bootstrapId is set and lsKey() is
// consistent between this read and the dismiss write.
function initUseAppBanner() {
  if (isStandalone()) return;
  if (localStorage.getItem(lsKey("pwa-installed")) !== "true") return;
  if (localStorage.getItem(lsKey("pwa-use-app-banner-dismissed")) === "true") return;
  showUseAppBanner.value = true;
}

export function PwaBanner() {
  // Initialize the "use the app" banner after mount so bootstrapId is set
  // and lsKey() produces the same key in both initUseAppBanner (read) and
  // handleUseAppDismiss (write).
  useEffect(() => {
    initUseAppBanner();
  }, []);

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
    localStorage.setItem(lsKey("pwa-use-app-banner-dismissed"), "true");
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
