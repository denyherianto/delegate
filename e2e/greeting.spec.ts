import { test, expect } from "@playwright/test";

/**
 * Greeting / welcome message tests.
 *
 * Verifies that the team-scoped `last-greeted-{team}` localStorage key
 * correctly tracks greeting state per team, not globally.
 *
 * Bug (pre-fix): `getLastGreeted()` used a single installation-scoped key.
 * Visiting testteam would mark greetings as done globally, causing otherteam
 * to skip its greeting even on a first visit.
 *
 * Fix: `getLastGreeted(team)` / `updateLastGreeted(team)` use per-team keys
 * (`delegate-{bootstrapId}-last-greeted-{team}`), so each team's greeting
 * state is tracked independently.
 *
 * Seed data: two teams — "testteam" (manager: edison) and "otherteam"
 * (manager: charlie). Both have messages so neither triggers the first-run
 * greeting path; both trigger the regular greeting path when last-greeted is
 * absent or stale.
 */

const TEAM2 = "otherteam";

test.describe("Greeting — team-scoped localStorage", () => {
  test("greeting fires for a second team even after the first team was greeted", async ({
    page,
  }) => {
    // 1. Load the app and wait for it to be ready.
    await page.goto("/chat");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.locator(".sb-nav-btn").first()).toBeVisible({
      timeout: 10_000,
    });
    // Wait for initial chat to render
    await expect(page.locator(".chat-log")).toBeVisible({ timeout: 5_000 });

    // 2. Mark testteam as "just greeted" so the app won't send another greeting
    //    when we switch back, and clear any prior otherteam greeting state.
    //    We manipulate localStorage directly to avoid depending on the greetTeam
    //    API having actually fired during this test run.
    await page.evaluate(() => {
      // Find the delegate key prefix (bootstrapId-scoped)
      const prefix = Object.keys(localStorage).find(
        (k) => k.includes("last-greeted-testteam") || k.startsWith("delegate-")
      );
      const basePrefix = prefix
        ? prefix.replace(/last-greeted.*$/, "")
        : "delegate-";

      // Stamp testteam as recently greeted (right now)
      localStorage.setItem(
        `${basePrefix}last-greeted-testteam`,
        new Date().toISOString()
      );

      // Remove any existing otherteam greeting timestamp so it looks fresh
      const otherKey = `${basePrefix}last-greeted-otherteam`;
      localStorage.removeItem(otherKey);
    });

    // 3. Switch to otherteam via the Cmd+K team switcher.
    const modifier = process.platform === "darwin" ? "Meta" : "Control";
    await page.keyboard.press(`${modifier}+KeyK`);
    await expect(page.locator(".team-switcher-backdrop")).toBeVisible({
      timeout: 3_000,
    });

    await page
      .locator(".team-switcher-item-name", { hasText: "Otherteam" })
      .click();

    // Modal should close
    await expect(page.locator(".team-switcher-backdrop")).not.toBeVisible({
      timeout: 3_000,
    });

    // 4. Wait for chat to load for otherteam.
    await expect(page.locator(".chat-log")).toBeVisible({ timeout: 5_000 });

    // 5. The greeting should fire: a message from charlie (otherteam manager)
    //    to the human should appear in the chat log.
    //    We wait up to 10s for SSE polling to pick up the greeting message.
    await expect(
      page.locator(".msg-sender", { hasText: /charlie/i }).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("greeting does NOT fire again for a recently-greeted team", async ({
    page,
  }) => {
    // 1. Load the app.
    await page.goto("/chat");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.locator(".sb-nav-btn").first()).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.locator(".chat-log")).toBeVisible({ timeout: 5_000 });

    // 2. Count existing messages from the manager (edison) on testteam.
    const initialCount = await page
      .locator(".msg-sender", { hasText: /edison/i })
      .count();

    // 3. Mark testteam as greeted one minute ago (well within GREETING_THRESHOLD).
    //    This simulates the correct post-fix behavior where a recent greeting
    //    suppresses the next one.
    await page.evaluate(() => {
      const prefix = Object.keys(localStorage).find((k) =>
        k.includes("last-greeted-")
      );
      const basePrefix = prefix
        ? prefix.replace(/last-greeted.*$/, "")
        : "delegate-";
      // One minute ago — within the 30-minute threshold
      const oneMinuteAgo = new Date(Date.now() - 60_000).toISOString();
      localStorage.setItem(
        `${basePrefix}last-greeted-testteam`,
        oneMinuteAgo
      );
    });

    // 4. Reload the page (simulates returning to the app).
    await page.reload();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.locator(".sb-nav-btn").first()).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.locator(".chat-log")).toBeVisible({ timeout: 5_000 });

    // 5. Wait a moment for any potential greeting to fire.
    await page.waitForTimeout(3_000);

    // 6. Message count from edison should NOT have increased.
    const afterCount = await page
      .locator(".msg-sender", { hasText: /edison/i })
      .count();
    expect(afterCount).toBe(initialCount);
  });
});
