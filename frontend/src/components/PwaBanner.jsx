import { useEffect } from "preact/hooks";
import { signal } from "@preact/signals";
import { lsKey } from "../state.js";

// Tracks the deferred beforeinstallprompt event so we can call .prompt() later
let deferredInstallEvent = null;

// Whether the install banner is visible (set to true when beforeinstallprompt fires)
const showInstallBanner = signal(false);

// Whether the "use the app" banner is visible (per-session, resets on page load)
const showUseAppBanner = signal(false);

// Are we in standalone (PWA) mode?
// Covers standalone, minimal-ui, and fullscreen display modes — all mean
// the app is running outside the browser tab. navigator.standalone is
// Safari-only; matchMedia covers Chrome/Edge.
function isStandalone() {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.matchMedia("(display-mode: minimal-ui)").matches ||
    window.matchMedia("(display-mode: fullscreen)").matches ||
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

  // Track successful installs via the appinstalled event (more reliable than
  // userChoice callback since it fires when Chrome actually finishes installing).
  window.addEventListener("appinstalled", () => {
    localStorage.setItem(lsKey("pwa-installed"), "true");
  });

  // When the app transitions out of standalone mode (display-mode: standalone
  // changes to false), the PWA was uninstalled. Clear the dismissed and
  // installed flags so the banner can reappear on the next visit.
  const standaloneQuery = window.matchMedia("(display-mode: standalone)");
  standaloneQuery.addEventListener("change", (e) => {
    if (!e.matches) {
      // Transitioned out of standalone — PWA was uninstalled
      localStorage.removeItem(lsKey("pwa-banner-dismissed"));
      localStorage.removeItem(lsKey("pwa-installed"));
    }
  });
}

// Determine initial "use the app" banner visibility.
// Shown when: PWA was previously installed, we're in browser mode, and the
// user hasn't dismissed it this session.
// Called after mount (via useEffect) to ensure the display-mode media query
// is checked after the browser has fully initialized the display context.
function initUseAppBanner() {
  if (isStandalone()) return;
  if (localStorage.getItem(lsKey("pwa-installed")) !== "true") return;
  if (sessionStorage.getItem("pwa-use-app-dismissed")) return;
  showUseAppBanner.value = true;
}

export function PwaBanner() {
  // Defer initUseAppBanner() to after mount so the browser has fully
  // resolved the display-mode media query before we check isStandalone().
  useEffect(() => {
    initUseAppBanner();
  }, []);

  // Install banner handlers
  function handleInstall() {
    if (!deferredInstallEvent) return;
    deferredInstallEvent.prompt();
    deferredInstallEvent.userChoice.then(() => {
      deferredInstallEvent = null;
      showInstallBanner.value = false;
    });
  }

  function handleInstallDismiss() {
    localStorage.setItem(lsKey("pwa-banner-dismissed"), "true");
    showInstallBanner.value = false;
  }

  // "Use the app" banner handler — per-session dismiss only
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
