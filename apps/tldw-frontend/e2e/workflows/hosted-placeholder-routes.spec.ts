import { test, expect, assertNoCriticalErrors } from "../utils/fixtures"

const HOSTED_PLACEHOLDER_ROUTES = [
  {
    path: "/account",
    title: /Hosted Account Pages Live In The Private Distribution/i,
  },
  {
    path: "/billing",
    title: /Hosted Billing Lives In The Private Distribution/i,
  },
  {
    path: "/billing/success",
    title: /Hosted Billing Redirects Live In The Private Distribution/i,
  },
  {
    path: "/billing/cancel",
    title: /Hosted Billing Redirects Live In The Private Distribution/i,
  },
  {
    path: "/signup",
    title: /Signup Is Not Part Of The OSS Web Surface/i,
  },
  {
    path: "/auth/reset-password",
    title: /Password Reset Is Not Active Here/i,
  },
]

test.describe("Hosted placeholder routes", () => {
  for (const route of HOSTED_PLACEHOLDER_ROUTES) {
    test(`${route.path} renders its OSS placeholder`, async ({
      authedPage,
      diagnostics,
    }) => {
      await authedPage.goto(route.path, { waitUntil: "domcontentloaded" })

      await expect(
        authedPage.getByTestId("route-placeholder-panel")
      ).toBeVisible({ timeout: 15_000 })
      await expect(
        authedPage.getByRole("heading", { name: route.title })
      ).toBeVisible({ timeout: 15_000 })

      const loginLink = authedPage.getByRole("link", { name: /^Open Login$/i })
      await expect(loginLink).toHaveCount(1)
      await expect(loginLink).toHaveAttribute("href", "/login")

      await assertNoCriticalErrors(diagnostics)
    })
  }
})
