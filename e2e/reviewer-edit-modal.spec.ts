import { test, expect, Page } from "@playwright/test";

/**
 * Tests for the Edit button in the approval bar (TaskSidePanel) and the
 * ReviewerEditModal it opens.
 *
 * Seed data:
 *   - T0003: in_approval, assigned to testboss — has the Edit button visible
 *
 * API routes for reviewer-edit endpoints are mocked with page.route() so no
 * real git operations run.
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

  // Mock POST /api/tasks/{taskId}/approve
  await page.route(`/api/tasks/${taskId}/approve`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });
}

/** Open the task panel for T0003 (in_approval). */
async function openT0003(page: Page) {
  await page.goto("/tasks");
  await expect(page.locator(".task-row").first()).toBeVisible({ timeout: 5_000 });
  await page.locator(".task-row", { hasText: "Write README" }).click();
  const panel = page.locator(".task-panel");
  await expect(panel).toBeVisible({ timeout: 3_000 });
  return panel;
}

test.describe("Edit button in approval bar", () => {
  test("Edit button renders for in_approval task", async ({ page }) => {
    const panel = await openT0003(page);

    // The approval bar should show an Edit button
    const editBtn = panel.locator(".task-approval-bar button", { hasText: "Edit" });
    await expect(editBtn).toBeVisible({ timeout: 3_000 });
  });

  test("clicking Edit opens ReviewerEditModal", async ({ page }) => {
    await mockReviewerEditRoutes(page, 3);
    const panel = await openT0003(page);

    await panel.locator(".task-approval-bar button", { hasText: "Edit" }).click();

    // Modal overlay should appear
    const modal = page.locator(".rem-overlay");
    await expect(modal).toBeVisible({ timeout: 3_000 });
  });

  test("Discard button closes modal without approving", async ({ page }) => {
    let approveCalled = false;
    await page.route("/api/tasks/3/approve", async (route) => {
      approveCalled = true;
      await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
    });
    await mockReviewerEditRoutes(page, 3);
    const panel = await openT0003(page);

    await panel.locator(".task-approval-bar button", { hasText: "Edit" }).click();
    const modal = page.locator(".rem-overlay");
    await expect(modal).toBeVisible({ timeout: 3_000 });

    // Click the Discard button inside the modal
    await modal.locator(".rem-btn-discard").click();

    // Modal should close
    await expect(modal).not.toBeVisible({ timeout: 2_000 });
    // Approve must NOT have been called
    expect(approveCalled).toBe(false);
  });
});

test.describe("ReviewerEditModal (via Edit button)", () => {
  test("modal renders file tabs and editor", async ({ page }) => {
    await mockReviewerEditRoutes(page, 3);
    const panel = await openT0003(page);

    await panel.locator(".task-approval-bar button", { hasText: "Edit" }).click();

    const modal = page.locator(".rem-overlay");
    await expect(modal).toBeVisible({ timeout: 3_000 });

    // Header should show task ID
    await expect(modal.locator(".rem-header-title")).toContainText("T0003");

    // Done and Discard buttons present
    await expect(modal.locator(".rem-btn-done")).toBeVisible();
    await expect(modal.locator(".rem-btn-discard")).toBeVisible();
  });

  test("Escape key triggers Discard (closes modal)", async ({ page }) => {
    await mockReviewerEditRoutes(page, 3);
    const panel = await openT0003(page);

    await panel.locator(".task-approval-bar button", { hasText: "Edit" }).click();

    const modal = page.locator(".rem-overlay");
    await expect(modal).toBeVisible({ timeout: 3_000 });

    await page.keyboard.press("Escape");

    await expect(modal).not.toBeVisible({ timeout: 2_000 });
  });

  test("Open file... input adds a new tab", async ({ page }) => {
    await mockReviewerEditRoutes(page, 3);
    const panel = await openT0003(page);

    await panel.locator(".task-approval-bar button", { hasText: "Edit" }).click();

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
    await mockReviewerEditRoutes(page, 3);
    const panel = await openT0003(page);

    await panel.locator(".task-approval-bar button", { hasText: "Edit" }).click();

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
