import { expect, test, type Page } from "@playwright/test"

async function mockHostedSession(page: Page) {
  await page.route("**/api/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: true,
        user: {
          id: 7,
          username: "hosted-user",
          email: "user@example.com",
          role: "user",
          is_active: true,
        },
      }),
    })
  })
}

test.describe("hosted launch funnel", () => {
  test("signup page loads and shows verification messaging after registration", async ({
    page,
  }) => {
    let requestBody = ""

    await page.route("**/api/auth/register", async (route) => {
      requestBody = route.request().postData() || ""
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ requires_verification: true }),
      })
    })

    await page.goto("/signup", { waitUntil: "domcontentloaded" })

    await expect(
      page.getByRole("heading", { name: /create your hosted account/i })
    ).toBeVisible()

    await page.getByLabel(/username/i).fill("hosted-user")
    await page.getByLabel(/^email$/i).fill("user@example.com")
    await page.getByLabel(/^password$/i).fill("HostedPass123!")
    await page.getByLabel(/registration code/i).fill("launch-beta")
    await page.getByRole("button", { name: /create account/i }).click()

    await expect(
      page.getByText(/check your email to verify your account before signing in\./i)
    ).toBeVisible()

    expect(JSON.parse(requestBody)).toEqual({
      username: "hosted-user",
      email: "user@example.com",
      password: "HostedPass123!",
      registration_code: "launch-beta",
    })
  })

  test("magic-link request flow returns success messaging", async ({ page }) => {
    let email = ""

    await page.route("**/api/auth/magic-link/request", async (route) => {
      email = JSON.parse(route.request().postData() || "{}").email || ""
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      })
    })

    await page.goto("/login", { waitUntil: "domcontentloaded" })
    await page.getByLabel(/^email$/i).fill("user@example.com")
    await page.getByRole("button", { name: /email me a sign-in link/i }).click()

    await expect(
      page.getByText(/sign-in link sent\. check your inbox for the hosted magic link\./i)
    ).toBeVisible()
    expect(email).toBe("user@example.com")
  })

  test("password login lands in the hosted app without browser bearer tokens", async ({
    page,
  }) => {
    let loginFormBody = ""

    await mockHostedSession(page)

    await page.route("**/api/auth/login", async (route) => {
      loginFormBody = route.request().postData() || ""
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "server-managed",
          refresh_token: "server-managed-refresh",
          token_type: "bearer",
          expires_in: 1800,
        }),
      })
    })

    await page.route("**/api/proxy/orgs", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [{ id: 42, name: "Personal workspace" }],
        }),
      })
    })

    await page.goto("/login", { waitUntil: "domcontentloaded" })
    await page.getByLabel(/account identifier/i).fill("user@example.com")
    await page.getByLabel(/^password$/i).fill("HostedPass123!")
    await page.getByRole("button", { name: /^sign in$/i }).click()

    await page.waitForURL(/\/chat/)

    const storedConfig = await page.evaluate(() => {
      const raw = window.localStorage.getItem("tldwConfig")
      return raw ? JSON.parse(raw) : null
    })

    expect(Object.fromEntries(new URLSearchParams(loginFormBody))).toEqual({
      username: "user@example.com",
      password: "HostedPass123!",
    })
    expect(storedConfig).toMatchObject({
      authMode: "multi-user",
      orgId: 42,
    })
    expect(storedConfig?.accessToken ?? "").toBe("")
    expect(storedConfig?.refreshToken ?? "").toBe("")
  })
})
