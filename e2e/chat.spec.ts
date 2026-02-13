import { test, expect } from "@playwright/test";

/**
 * Chat interaction tests.
 *
 * Seed data includes:
 *   - 5 messages (boss↔manager, manager↔alice)
 *   - 2 system events referencing T0001 and T0002
 *   - Message "Great, also check T0002 status." contains T0002 in body
 *   - Message "Please kick off the project." has task_id=T0001 badge in header
 */

const TEAM = "testteam";

test.describe("Chat interactions", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/${TEAM}/chat`);
    // Wait for messages to load
    await expect(page.locator(".msg, .msg-event").first()).toBeVisible({
      timeout: 5_000,
    });
  });

  test("task ID link in chat message body opens task panel", async ({ page }) => {
    // The message "Great, also check T0002 status." contains T0002 as a clickable link
    const msg = page.locator(".msg-content", { hasText: "T0002 status" });
    await expect(msg).toBeVisible();

    // Click the T0002 link inside the message
    const taskLink = msg.locator("[data-task-id='2']");
    await expect(taskLink).toBeVisible();
    await taskLink.click();

    // Task panel should open with T0002
    const panel = page.locator(".task-panel");
    await expect(panel).toBeVisible({ timeout: 3_000 });
    await expect(panel.locator(".task-panel-id")).toContainText("T0002");
  });

  test("system event task link opens task panel", async ({ page }) => {
    // System event: "Alice started working on T0001"
    const event = page.locator(".msg-event", { hasText: "Alice started working on" });
    await expect(event).toBeVisible();

    // Click the T0001 link in the event
    const taskLink = event.locator("[data-task-id='1']");
    await expect(taskLink).toBeVisible();
    await taskLink.click();

    // Task panel should open with T0001
    const panel = page.locator(".task-panel");
    await expect(panel).toBeVisible({ timeout: 3_000 });
    await expect(panel.locator(".task-panel-id")).toContainText("T0001");
  });

  test("message sender name opens agent panel", async ({ page }) => {
    // Click on "Edison" sender name in a message header
    const sender = page.locator(".msg-sender", { hasText: "Edison" }).first();
    await expect(sender).toBeVisible();
    await sender.click();

    // Agent/diff panel should open for edison
    const panel = page.locator(".diff-panel");
    await expect(panel).toBeVisible({ timeout: 3_000 });
    await expect(panel.locator(".diff-panel-title")).toContainText("Edison");
  });

  test("message header task badge opens task panel", async ({ page }) => {
    // Find a message with a task badge in the header (messages with task_id)
    const badge = page.locator(".msg-task-badge", { hasText: "T0001" }).first();
    await expect(badge).toBeVisible();
    await badge.click();

    // Task panel should open with T0001
    const panel = page.locator(".task-panel");
    await expect(panel).toBeVisible({ timeout: 3_000 });
    await expect(panel.locator(".task-panel-id")).toContainText("T0001");
  });
});
