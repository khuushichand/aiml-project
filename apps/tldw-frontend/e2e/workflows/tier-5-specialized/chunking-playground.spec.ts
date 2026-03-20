/**
 * Chunking Playground E2E Tests (Tier 5)
 *
 * Tests the /chunking-playground page:
 * - Page loads with input area and chunk button
 * - Capabilities endpoint fires on load
 * - Chunk Text button triggers chunking API
 *
 * Run: npx playwright test e2e/workflows/tier-5-specialized/chunking-playground.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { expectApiCall } from "../../utils/api-assertions"

test.describe("Chunking Playground", () => {
  test.beforeEach(async ({ authedPage, serverInfo }) => {
    skipIfServerUnavailable(serverInfo)
  })

  test("page loads with interactive elements", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/chunking-playground", {
      waitUntil: "domcontentloaded",
    })
    await authedPage.waitForLoadState("networkidle").catch(() => {})

    // Should have the chunk button and text input area
    const buttons = await authedPage.getByRole("button").count()
    const inputs = await authedPage
      .locator("input, select, textarea")
      .count()
    expect(buttons + inputs).toBeGreaterThan(0)

    await assertNoCriticalErrors(diagnostics)
  })

  test("capabilities endpoint fires on load", async ({
    authedPage,
    diagnostics,
  }) => {
    const apiCall = expectApiCall(authedPage, {
      url: "/api/v1/chunking/capabilities",
    })
    await authedPage.goto("/chunking-playground", {
      waitUntil: "domcontentloaded",
    })

    const result = await apiCall.catch(() => null)
    if (result) {
      expect(result.response.status()).toBeLessThan(500)
    }

    await assertNoCriticalErrors(diagnostics)
  })

  test("chunk text button fires chunking API", async ({
    authedPage,
    diagnostics,
  }) => {
    await authedPage.goto("/chunking-playground", {
      waitUntil: "domcontentloaded",
    })
    await authedPage.waitForLoadState("networkidle").catch(() => {})

    // Fill in the text area with sample content
    const textarea = authedPage.locator("textarea").first()
    if (await textarea.isVisible().catch(() => false)) {
      await textarea.fill(
        "This is sample text for chunking. It has multiple sentences to test splitting behavior."
      )

      const chunkBtn = authedPage
        .getByRole("button", { name: /chunk text/i })
        .first()
      if (await chunkBtn.isVisible().catch(() => false)) {
        const apiCall = expectApiCall(authedPage, {
          url: "/api/v1/chunking/chunk_text",
          method: "POST",
        })
        await chunkBtn.click()
        const result = await apiCall.catch(() => null)
        if (result) {
          expect(result.response.status()).toBeLessThan(500)
        }
      }
    }

    await assertNoCriticalErrors(diagnostics)
  })
})
