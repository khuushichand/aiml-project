/**
 * Evaluations Workflow E2E Tests (Tier-2 Features)
 *
 * Tests the evaluations workflow:
 * - Page loads and renders expected elements (title, tabs)
 * - New evaluation opens the create-evaluation flow
 */
import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../../utils/fixtures"
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

  test("new evaluation opens create modal", async ({ diagnostics }) => {
    await evaluations.assertPageReady()

    await evaluations.openCreateEvaluation()
    await expect(evaluations.createEvaluationModal).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })
})
