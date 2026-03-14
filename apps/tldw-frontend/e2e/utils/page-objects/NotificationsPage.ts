/**
 * Page Object for Notifications page
 */
import { type Page, type Locator, expect } from "@playwright/test"
import { BasePage, type InteractiveElement } from "./BasePage"
import { waitForConnection } from "../helpers"

export class NotificationsPage extends BasePage {
  readonly heading: Locator
  readonly refreshButton: Locator
  readonly notificationsList: Locator
  readonly emptyState: Locator
  readonly loadingState: Locator
  readonly errorBanner: Locator
  readonly unreadLabel: Locator

  constructor(page: Page) {
    super(page)
    this.heading = page.getByRole("heading", { name: /notifications/i })
    this.refreshButton = page.getByRole("button", { name: /refresh/i })
    this.notificationsList = page.locator("ul.space-y-3")
    this.emptyState = page.getByText("No notifications yet.")
    this.loadingState = page.getByText("Loading notifications...")
    this.errorBanner = page.locator(".text-danger")
    this.unreadLabel = page.getByText(/Unread:/)
  }

  async goto(): Promise<void> {
    await this.page.goto("/notifications", { waitUntil: "domcontentloaded" })
    await waitForConnection(this.page)
  }

  async assertPageReady(): Promise<void> {
    await expect(this.heading).toBeVisible({ timeout: 15_000 })
  }

  async waitForLoaded(): Promise<void> {
    // Wait until loading state disappears (either empty state or list appears)
    await expect(this.heading).toBeVisible({ timeout: 15_000 })
    await expect(this.loadingState).toBeHidden({ timeout: 15_000 }).catch(() => {})
  }

  async getNotificationItems(): Promise<Locator> {
    return this.page.locator("ul.space-y-3 > li")
  }

  async getNotificationCount(): Promise<number> {
    const items = this.page.locator("ul.space-y-3 > li")
    return items.count()
  }

  async getInteractiveElements(): Promise<InteractiveElement[]> {
    return [
      {
        name: "Refresh inbox",
        locator: this.refreshButton,
        expectation: { type: "api_call", apiPattern: "/notifications", method: "GET" },
      },
    ]
  }
}
