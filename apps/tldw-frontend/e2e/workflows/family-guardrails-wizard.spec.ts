import { assertNoCriticalErrors, expect, test } from "../utils/fixtures"
import { seedAuth } from "../utils/helpers"

test.describe("Family Guardrails Wizard Workflow", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("family wizard route is present and reachable", async ({
    authedPage,
    diagnostics
  }) => {
    await authedPage.goto("/settings/family-guardrails")
    await expect(authedPage).toHaveURL(/\/settings\/family-guardrails/)
    await expect(
      authedPage.getByRole("heading", { name: /Family Guardrails Wizard/i })
    ).toBeVisible()
    await expect(authedPage.getByText("Household Basics")).toBeVisible()
    await expect(authedPage.getByText("Invite + Acceptance Tracker")).toBeVisible()
    await expect(
      authedPage.getByRole("button", { name: /Save & Continue/i })
    ).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("can progress from household basics to guardian setup step", async ({
    authedPage,
    diagnostics
  }) => {
    await authedPage.goto("/settings/family-guardrails")
    await authedPage.getByRole("button", { name: /Save & Continue/i }).click()
    await expect(authedPage.getByText("Add every guardian who can manage alerts and safety settings.")).toBeVisible()
    await expect(authedPage.getByRole("button", { name: /Add Guardian/i })).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })
})
