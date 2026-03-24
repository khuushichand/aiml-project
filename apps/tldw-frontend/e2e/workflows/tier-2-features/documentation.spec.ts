import { test, expect, assertNoCriticalErrors } from "../../utils/fixtures"

test.describe("Documentation", () => {
  test("loads published server docs instead of the fallback placeholder", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/documentation", { waitUntil: "domcontentloaded" })

    const serverTab = authedPage.getByRole("tab", { name: /tldw_server \(/i })
    await expect(serverTab).toBeVisible({ timeout: 15_000 })
    await expect(serverTab).toHaveAttribute("aria-selected", "true")

    const authGuideButton = authedPage.getByRole("button", {
      name: /AuthNZ API Guide/i,
    })
    await expect(authGuideButton).toBeVisible({ timeout: 15_000 })
    await authGuideButton.click()

    await expect(
      authedPage.getByText(
        /The AuthNZ module provides authentication and authorization/
      )
    ).toBeVisible({ timeout: 15_000 })

    await expect(
      authedPage.getByText(/Documentation files were not auto-discovered/i)
    ).toHaveCount(0)

    await assertNoCriticalErrors(diagnostics)
  })
})
