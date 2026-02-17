/**
 * Playwright global setup — runs once before all tests.
 *
 * Seeding is done at config-eval time (in playwright.config.ts) to
 * avoid a race with the webServer.  This file now only logs the
 * test-run configuration.
 */

async function globalSetup() {
  const tmpDir = process.env.DELEGATE_E2E_HOME;
  if (!tmpDir) {
    throw new Error("DELEGATE_E2E_HOME not set — config should have set it");
  }

  console.log(
    `\n  E2E setup: home=${tmpDir}, port=${process.env.DELEGATE_E2E_PORT}\n`
  );
}

export default globalSetup;
