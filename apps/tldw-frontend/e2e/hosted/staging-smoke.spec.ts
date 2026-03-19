import { expect, test } from "@playwright/test"

const stagingUserEmail = (process.env.TLDW_STAGING_USER_EMAIL || "").trim()
const stagingUserPassword = (process.env.TLDW_STAGING_USER_PASSWORD || "").trim()
const hasCredentials = Boolean(stagingUserEmail && stagingUserPassword)

test.describe("hosted staging smoke", () => {
  test("public hosted auth pages and billing plans are reachable", async ({
    page,
    request,
  }) => {
    await page.goto("/login", { waitUntil: "domcontentloaded" })
    await expect(
      page.getByRole("heading", { name: /^sign in$/i })
    ).toBeVisible()
    await expect(page.getByText(/hosted tldw keeps the first-run path focused/i)).toBeVisible()
    await expect(page.getByText(/server url/i)).toHaveCount(0)

    await page.goto("/signup", { waitUntil: "domcontentloaded" })
    await expect(
      page.getByRole("heading", { name: /create your hosted account/i })
    ).toBeVisible()
    await expect(
      page.getByText(/start with a single-user subscription flow now/i)
    ).toBeVisible()

    const billingPlansResponse = await request.get("/api/v1/billing/plans")
    expect(billingPlansResponse.ok()).toBe(true)
  })

  test("signed-in hosted account and billing routes load", async ({ page }) => {
    test.skip(!hasCredentials, "Set TLDW_STAGING_USER_EMAIL and TLDW_STAGING_USER_PASSWORD to run signed-in smoke checks.")

    await page.goto("/login", { waitUntil: "domcontentloaded" })
    await page.getByLabel(/account identifier/i).fill(stagingUserEmail)
    await page.getByLabel(/^password$/i).fill(stagingUserPassword)
    await page.getByRole("button", { name: /^sign in$/i }).click()

    await page.waitForURL(/\/(chat|account|billing)/)

    await page.goto("/account", { waitUntil: "domcontentloaded" })
    await expect(
      page.getByRole("heading", { name: /your hosted account/i })
    ).toBeVisible()

    await page.goto("/billing", { waitUntil: "domcontentloaded" })
    await expect(
      page.getByRole("heading", { name: /hosted plan and usage/i })
    ).toBeVisible()
  })
})
