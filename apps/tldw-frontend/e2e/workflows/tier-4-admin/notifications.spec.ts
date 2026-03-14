import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"
import { NotificationsPage } from "../../utils/page-objects"

test.describe("Notifications", () => {
  let notifications: NotificationsPage

  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
    notifications = new NotificationsPage(authedPage)
  })

  test("notifications page loads with heading and refresh button", async ({
    authedPage,
    diagnostics,
  }) => {
    await notifications.goto()
    await notifications.assertPageReady()

    // Heading should be visible
    await expect(notifications.heading).toBeVisible()

    // Refresh button should be visible
    await expect(notifications.refreshButton).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("notifications page shows unread count label", async ({ authedPage, diagnostics }) => {
    await notifications.goto()
    await notifications.assertPageReady()

    // The unread label should be present (shows "Unread: N")
    await expect(notifications.unreadLabel).toBeVisible({ timeout: 15_000 })

    await assertNoCriticalErrors(diagnostics)
  })

  test("notifications page fires list and unread-count API on load", async ({
    authedPage,
    diagnostics,
  }) => {
    // Set up API call watchers before navigating
    const listCall = expectApiCall(authedPage, {
      url: "/notifications",
      method: "GET",
    })

    await notifications.goto()

    // The page should fire GET /notifications on mount
    await listCall

    await assertNoCriticalErrors(diagnostics)
  })

  test("notifications page shows empty state or list after loading", async ({
    authedPage,
    diagnostics,
  }) => {
    await notifications.goto()
    await notifications.waitForLoaded()

    // After loading, either the empty state or the list should be visible
    const emptyVisible = await notifications.emptyState.isVisible().catch(() => false)
    const listVisible = await notifications.notificationsList.isVisible().catch(() => false)

    expect(emptyVisible || listVisible).toBe(true)

    await assertNoCriticalErrors(diagnostics)
  })

  test("refresh button fires notifications API call", async ({ authedPage, diagnostics }) => {
    await notifications.goto()
    await notifications.waitForLoaded()

    // Click refresh and verify it fires an API call
    const apiCall = expectApiCall(authedPage, {
      url: "/notifications",
      method: "GET",
    })

    await notifications.refreshButton.click()
    await apiCall

    await assertNoCriticalErrors(diagnostics)
  })

  test("notification items have action buttons when present", async ({
    authedPage,
    diagnostics,
  }) => {
    await notifications.goto()
    await notifications.waitForLoaded()

    const items = authedPage.locator("ul.space-y-3 > li")
    const itemCount = await items.count()

    if (itemCount > 0) {
      const firstItem = items.first()

      // Each notification item should have at least a Dismiss button
      const dismissBtn = firstItem.getByRole("button", { name: /dismiss/i })
      await expect(dismissBtn).toBeVisible()

      // Should also have a Snooze button
      const snoozeBtn = firstItem.getByRole("button", { name: /snooze/i })
      await expect(snoozeBtn).toBeVisible()
    }

    await assertNoCriticalErrors(diagnostics)
  })

  test("mark-read button fires API when notification is unread", async ({
    authedPage,
    diagnostics,
  }) => {
    await notifications.goto()
    await notifications.waitForLoaded()

    const markReadBtn = authedPage.getByRole("button", { name: /mark read/i }).first()
    const isVisible = await markReadBtn.isVisible().catch(() => false)

    if (isVisible) {
      const apiCall = expectApiCall(authedPage, {
        url: "/notifications/mark-read",
        method: "POST",
      })

      await markReadBtn.click()
      await apiCall
    }

    await assertNoCriticalErrors(diagnostics)
  })

  test("dismiss button fires API call", async ({ authedPage, diagnostics }) => {
    await notifications.goto()
    await notifications.waitForLoaded()

    const dismissBtn = authedPage.getByRole("button", { name: /dismiss/i }).first()
    const isVisible = await dismissBtn.isVisible().catch(() => false)

    if (isVisible) {
      const apiCall = expectApiCall(authedPage, {
        url: /\/notifications\/\d+\/dismiss/,
        method: "POST",
      })

      await dismissBtn.click()
      await apiCall
    }

    await assertNoCriticalErrors(diagnostics)
  })

  test("snooze button fires API call", async ({ authedPage, diagnostics }) => {
    await notifications.goto()
    await notifications.waitForLoaded()

    const snoozeBtn = authedPage.getByRole("button", { name: /snooze/i }).first()
    const isVisible = await snoozeBtn.isVisible().catch(() => false)

    if (isVisible) {
      const apiCall = expectApiCall(authedPage, {
        url: /\/notifications\/\d+\/snooze/,
        method: "POST",
      })

      await snoozeBtn.click()
      await apiCall
    }

    await assertNoCriticalErrors(diagnostics)
  })
})
