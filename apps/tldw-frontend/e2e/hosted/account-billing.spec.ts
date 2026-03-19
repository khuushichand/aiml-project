import { expect, test, type Page } from "@playwright/test"

async function seedHostedConfig(page: Page) {
  await page.addInitScript(() => {
    const config = {
      serverUrl: window.location.origin,
      authMode: "multi-user",
      orgId: 42,
    }

    window.localStorage.setItem("tldwConfig", JSON.stringify(config))
    window.localStorage.setItem("__tldw_first_run_complete", "true")
  })
}

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

test.describe("hosted account and billing", () => {
  test.beforeEach(async ({ page }) => {
    await seedHostedConfig(page)
    await mockHostedSession(page)
  })

  test("account page loads profile data", async ({ page }) => {
    await page.route("**/api/proxy/users/me/profile", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          profile_version: "2026-03-18",
          user: {
            id: 7,
            username: "hosted-user",
            email: "user@example.com",
            role: "user",
            is_active: true,
            is_verified: true,
            last_login: "2026-03-17T12:00:00Z",
            storage_quota_mb: 2048,
            storage_used_mb: 512,
          },
          memberships: [
            {
              org_id: 42,
              org_name: "Personal workspace",
              role: "owner",
              is_default: true,
            },
          ],
          security: {
            verified: true,
            mfa_enabled: false,
          },
          quotas: {
            storage_quota_mb: 2048,
            storage_used_mb: 512,
          },
        }),
      })
    })

    await page.goto("/account", { waitUntil: "domcontentloaded" })

    await expect(
      page.getByRole("heading", { name: /your hosted account/i })
    ).toBeVisible()
    await expect(page.getByText("user@example.com")).toBeVisible()
    await expect(page.getByText("Personal workspace")).toBeVisible()
    await expect(
      page.getByRole("link", { name: /open billing/i })
    ).toBeVisible()
  })

  test("billing page loads plan and usage state", async ({ page }) => {
    await page.route("**/api/proxy/billing/subscription", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          org_id: 42,
          plan_name: "starter",
          plan_display_name: "Starter",
          status: "active",
          billing_cycle: "monthly",
          current_period_end: "2026-04-18T00:00:00Z",
          cancel_at_period_end: false,
        }),
      })
    })

    await page.route("**/api/proxy/billing/usage", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          org_id: 42,
          plan_name: "starter",
          limits: {
            messages_per_month: 200,
            storage_mb: 1024,
          },
          usage: {
            messages_per_month: 120,
            storage_mb: 512,
          },
          limit_checks: {
            messages_per_month: {
              usage: 120,
              limit: 200,
              exceeded: false,
            },
            storage_mb: {
              usage: 512,
              limit: 1024,
              exceeded: false,
            },
          },
          has_warnings: false,
          has_exceeded: false,
        }),
      })
    })

    await page.route("**/api/proxy/billing/invoices", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              id: 101,
              org_id: 42,
              amount_cents: 2900,
              amount_display: "$29.00",
              status: "paid",
              description: "March invoice",
              created_at: "2026-03-01T00:00:00Z",
              invoice_pdf_url: "https://app.example.com/invoices/101.pdf",
            },
          ],
          total: 1,
        }),
      })
    })

    await page.route("**/api/proxy/billing/plans", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          plans: [
            {
              name: "starter",
              display_name: "Starter",
              description: "Core hosted access",
              price_usd_monthly: 29,
              price_usd_yearly: 290,
              limits: {
                messages_per_month: 200,
                storage_mb: 1024,
              },
            },
            {
              name: "pro",
              display_name: "Pro",
              description: "Higher usage ceilings",
              price_usd_monthly: 79,
              price_usd_yearly: 790,
              limits: {
                messages_per_month: 1000,
                storage_mb: 8192,
              },
            },
          ],
        }),
      })
    })

    await page.goto("/billing", { waitUntil: "domcontentloaded" })

    await expect(
      page.getByRole("heading", { name: /hosted plan and usage/i })
    ).toBeVisible()
    await expect(page.getByRole("heading", { name: /^starter$/i })).toBeVisible()
    await expect(page.getByText(/^120 \/ 200$/).first()).toBeVisible()
    await expect(page.getByText("March invoice")).toBeVisible()
    await expect(
      page.getByRole("button", { name: /choose pro/i })
    ).toBeVisible()
  })
})
