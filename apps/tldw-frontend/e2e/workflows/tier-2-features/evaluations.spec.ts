/**
 * Evaluations Workflow E2E Tests (Tier-2 Features)
 *
 * Tests the evaluations workflow:
 * - Page loads and renders expected elements (title, tabs)
 * - Run evaluation fires API call to /api/v1/evaluations
 */
import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"
import { EvaluationsPage } from "../../utils/page-objects"

test.describe("Evaluations", () => {
  let evaluations: EvaluationsPage

  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
    evaluations = new EvaluationsPage(authedPage)
    await evaluations.goto()
  })

  test("page loads with expected elements", async ({ diagnostics }) => {
    await evaluations.assertPageReady()

    // Verify all tabs are visible
    await expect(evaluations.evaluationsTab).toBeVisible()
    await expect(evaluations.runsTab).toBeVisible()
    await expect(evaluations.datasetsTab).toBeVisible()
    await expect(evaluations.webhooksTab).toBeVisible()
    await expect(evaluations.historyTab).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("run evaluation fires API", async ({ authedPage, diagnostics }) => {
    await evaluations.assertPageReady()

    const apiCall = expectApiCall(authedPage, {
      url: "/api/v1/evaluations",
    })

    await evaluations.runEvaluation()

    const { response } = await apiCall
    expect(response.status()).toBeLessThan(500)

    await assertNoCriticalErrors(diagnostics)
  })
})
