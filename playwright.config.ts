import { defineConfig, devices } from "@playwright/test";
import { execSync } from "child_process";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

/**
 * Playwright config for Delegate E2E tests.
 *
 * IMPORTANT: Both the temp dir creation AND seeding happen here at
 * config-eval time.  Playwright starts globalSetup and webServer in
 * parallel, so if the seed runs inside globalSetup it races with the
 * webServer.  When the server wins it caches an empty team-map and
 * every subsequent team-UUID lookup returns a fallback value, causing
 * all task / message queries to return zero rows.
 *
 * By seeding at config-eval time we guarantee the DB is fully
 * populated before the webServer process is spawned.
 */

// Find the git common directory (main repo) to access .venv
// This handles both regular repos and git worktrees
let repoRoot = __dirname;
const gitFile = path.join(__dirname, ".git");
if (fs.existsSync(gitFile) && fs.statSync(gitFile).isFile()) {
  const gitContent = fs.readFileSync(gitFile, "utf-8").trim();
  if (gitContent.startsWith("gitdir: ")) {
    // This is a worktree — extract main repo path
    const gitDir = gitContent.replace("gitdir: ", "");
    // gitDir is something like /path/to/repo/.git/worktrees/T0047
    // We want /path/to/repo, which is 3 levels up
    repoRoot = path.resolve(gitDir, "../../..");
  }
}

const venvPython = path.join(repoRoot, ".venv", "bin", "python");

// Use a stable temp dir so that `reuseExistingServer` can work
// across consecutive local runs.  A random dir would mismatch
// the already-running server's DELEGATE_HOME.
const tmpDir =
  process.env.DELEGATE_E2E_HOME ||
  path.join(os.tmpdir(), "delegate-e2e-stable");

// Wipe and recreate so each run starts from a clean state.
if (!process.env.DELEGATE_E2E_HOME) {
  fs.rmSync(tmpDir, { recursive: true, force: true });
  fs.mkdirSync(tmpDir, { recursive: true });
}

// Seed test data BEFORE the webServer starts (see comment above).
// Guard with a marker file to prevent re-seeding if the config is
// evaluated more than once (Playwright may re-import it per worker).
const seedMarker = path.join(tmpDir, ".seeded");
const seedScript = path.resolve(__dirname, "e2e", "seed.py");
if (!fs.existsSync(seedMarker)) {
  try {
    execSync(`${venvPython} ${seedScript} ${tmpDir}`, {
      cwd: __dirname,
      stdio: "pipe",
      env: { ...process.env, PYTHONPATH: __dirname },
    });
    fs.writeFileSync(seedMarker, new Date().toISOString());
  } catch (err: any) {
    console.error("Seed script failed:");
    console.error(err.stderr?.toString() || err.message);
    throw err;
  }
}

// Use a fixed high port unlikely to collide (avoids async port-finding)
const port = Number(process.env.DELEGATE_E2E_PORT) || 13548;
const baseURL = `http://127.0.0.1:${port}`;

// Make these available to globalSetup, globalTeardown, and tests
process.env.DELEGATE_E2E_HOME = tmpDir;
process.env.DELEGATE_E2E_PORT = String(port);
process.env.DELEGATE_E2E_BASE_URL = baseURL;

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",

  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",

  use: {
    baseURL,
    trace: "on-first-retry",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
    },
  ],

  webServer: {
    command: `${repoRoot}/.venv/bin/python -m uvicorn delegate.web:create_app --factory --host 127.0.0.1 --port ${port}`,
    port,
    // Always start a fresh server — the seed wipes and re-creates the
    // temp dir at config-eval time so any cached server would be stale.
    reuseExistingServer: false,
    cwd: __dirname,
    env: {
      ...process.env,
      DELEGATE_HOME: tmpDir,
      PYTHONPATH: __dirname, // Ensure delegate package loads from worktree
    },
    timeout: 15_000,
  },
});
