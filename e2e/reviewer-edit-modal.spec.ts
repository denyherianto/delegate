import { test, expect, Page } from "@playwright/test";

/**
 * Smoke tests for ReviewerEditModal.
 *
 * These tests require:
 *   - The seeded test env (T0002 has changed files in_review status assigned to testboss)
 *   - T0126 backend endpoints merged (GET /api/tasks/{id}/file, POST /api/tasks/{id}/reviewer-edits)
 *   - ReviewerEditModal wired into TaskSidePanel's Changes tab with an "Edit files" button
 *
 * Until that wiring is in place (a later milestone), the tests are skipped.
 * To enable: remove the `test.skip(...)` calls.
 *
 * API routes are mocked with page.route() so no real git operations run.
 */

const MOCK_FILE_CONTENT = `def hello():\n    print("Hello, World!")\n\nhello()\n`;
const MOCK_HEAD_SHA = "abc1234abc1234abc1234abc1234abc1234abc1234";
const MOCK_NEW_SHA  = "def5678def5678def5678def5678def5678def5678";

/** Set up mocked routes for the reviewer-edit API endpoints. */
async function mockReviewerEditRoutes(page: Page, taskId: number) {
  // Mock GET /api/tasks/{taskId}/file
  await page.route(`/api/tasks/${taskId}/file*`, async (route) => {
    const url = new URL(route.request().url());
    const filePath = url.searchParams.get("path") || "";
    if (filePath === "src/missing.py") {
      await route.fulfill({ status: 404, body: "Not found" });
    } else {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ content: MOCK_FILE_CONTENT, head_sha: MOCK_HEAD_SHA }),
      });
    }
  });

  // Mock POST /api/tasks/{taskId}/reviewer-edits
  await page.route(`/api/tasks/${taskId}/reviewer-edits`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ new_sha: MOCK_NEW_SHA }),
    });
  });
}

/** Open the task panel for T0002 (in_review) and navigate to Changes tab. */
async function openChangesTab(page: Page) {
  await page.goto("/tasks");
  await expect(page.locator(".task-row").first()).toBeVisible({ timeout: 5_000 });
  await page.locator(".task-row", { hasText: "Implement design system" }).click();
  const panel = page.locator(".task-panel");
  await expect(panel).toBeVisible({ timeout: 3_000 });
  await panel.locator(".task-panel-tab", { hasText: "Changes" }).click();
  return panel;
}

test.describe("ReviewerEditModal", () => {
  test.skip(() => true, "Requires T0126 backend + TaskSidePanel wiring (later milestone)");

  test("modal renders tabs for changed files and shows first file loaded", async ({ page }) => {
    await mockReviewerEditRoutes(page, 2);
    const panel = await openChangesTab(page);

    // Click "Edit files" button to open the modal
    await panel.locator("button", { hasText: "Edit files" }).click();

    // Modal overlay should be visible
    const modal = page.locator(".rem-overlay");
    await expect(modal).toBeVisible({ timeout: 3_000 });

    // Header should show the task ID
    await expect(modal.locator(".rem-header-title")).toContainText("T0002");

    // Tab bar should have at least one tab
    await expect(modal.locator(".rem-tab").first()).toBeVisible();

    // Editor should not be empty (first file auto-loaded)
    const textarea = modal.locator(".rem-editor-textarea");
    await expect(textarea).toBeVisible();
    await expect(textarea).not.toBeEmpty();

    // Done and Discard buttons present
    await expect(modal.locator(".rem-btn-done")).toBeVisible();
    await expect(modal.locator(".rem-btn-discard")).toBeVisible();
  });

  test("Discard button calls onDiscard and closes modal", async ({ page }) => {
    await mockReviewerEditRoutes(page, 2);
    const panel = await openChangesTab(page);
    await panel.locator("button", { hasText: "Edit files" }).click();

    const modal = page.locator(".rem-overlay");
    await expect(modal).toBeVisible({ timeout: 3_000 });

    await modal.locator(".rem-btn-discard").click();

    // Modal should be gone
    await expect(modal).not.toBeVisible({ timeout: 2_000 });
  });

  test("Escape key triggers Discard", async ({ page }) => {
    await mockReviewerEditRoutes(page, 2);
    const panel = await openChangesTab(page);
    await panel.locator("button", { hasText: "Edit files" }).click();

    const modal = page.locator(".rem-overlay");
    await expect(modal).toBeVisible({ timeout: 3_000 });

    await page.keyboard.press("Escape");

    await expect(modal).not.toBeVisible({ timeout: 2_000 });
  });

  test("Done with no edits skips POST and calls onDone", async ({ page }) => {
    const postCalled = { value: false };
    await page.route("**/reviewer-edits", async (route) => {
      postCalled.value = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ new_sha: MOCK_NEW_SHA }),
      });
    });
    await mockReviewerEditRoutes(page, 2);
    const panel = await openChangesTab(page);
    await panel.locator("button", { hasText: "Edit files" }).click();

    const modal = page.locator(".rem-overlay");
    await expect(modal).toBeVisible({ timeout: 3_000 });

    // Wait for file to load, then click Done without editing
    await expect(modal.locator(".rem-editor-textarea")).not.toBeEmpty({ timeout: 3_000 });
    await modal.locator(".rem-btn-done").click();

    // POST should NOT have been called (no edits)
    expect(postCalled.value).toBe(false);

    // Modal should close (onDone fired)
    await expect(modal).not.toBeVisible({ timeout: 2_000 });
  });

  test("Open file... shows input, Enter fetches file and adds new tab", async ({ page }) => {
    await mockReviewerEditRoutes(page, 2);
    const panel = await openChangesTab(page);
    await panel.locator("button", { hasText: "Edit files" }).click();

    const modal = page.locator(".rem-overlay");
    await expect(modal).toBeVisible({ timeout: 3_000 });

    const tabsBefore = await modal.locator(".rem-tab:not(.rem-tab-open)").count();

    // Click "Open file..." button
    await modal.locator(".rem-tab-open").click();

    // Input should appear
    const input = modal.locator(".rem-open-file-input");
    await expect(input).toBeVisible({ timeout: 1_000 });

    // Type a path and press Enter
    await input.fill("src/other.py");
    await input.press("Enter");

    // A new tab should be added
    await expect(modal.locator(".rem-tab:not(.rem-tab-open)")).toHaveCount(tabsBefore + 1, {
      timeout: 3_000,
    });
  });

  test("Open file... shows error for missing file", async ({ page }) => {
    await mockReviewerEditRoutes(page, 2);
    const panel = await openChangesTab(page);
    await panel.locator("button", { hasText: "Edit files" }).click();

    const modal = page.locator(".rem-overlay");
    await expect(modal).toBeVisible({ timeout: 3_000 });

    await modal.locator(".rem-tab-open").click();
    const input = modal.locator(".rem-open-file-input");
    await expect(input).toBeVisible();

    await input.fill("src/missing.py");
    await input.press("Enter");

    // Error message should show
    await expect(modal.locator(".rem-open-file-error")).toContainText("File not found", {
      timeout: 2_000,
    });
  });
});
