import { expect, getCriticalIssues, test } from "../utils/fixtures"
import type { Page } from "@playwright/test"

import { runCompanionHomeParityContract } from "../../../test-utils/companion-home.contract"
import {
  COMPANION_HOME_PARITY_OPENAPI_SPEC,
} from "../../../test-utils/companion-home.fixtures"
import { resolveCompanionHomeWebMock } from "./companion-home.web-mocks"

const DESKTOP_VIEWPORT = { width: 1440, height: 900 }

const installCompanionHomeWebMocks = async (
  page: Page,
  unhandledApiRequests: string[]
): Promise<void> => {
  await page.route("**/openapi.json", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(COMPANION_HOME_PARITY_OPENAPI_SPEC)
    })
  })

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const pathname = url.pathname
    const method = request.method().toUpperCase()
    const mock = resolveCompanionHomeWebMock(method, pathname)
    if (mock.kind === "unhandled") {
      unhandledApiRequests.push(`${method} ${pathname}`)
    }
    await route.fulfill(mock.response)
  })
}

test.describe("Companion Home parity (WebUI)", () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.setViewportSize(DESKTOP_VIEWPORT)
  })

  test("passes baseline + deterministic home dashboard parity contract", async ({
    authedPage,
    diagnostics
  }) => {
    const unhandledApiRequests: string[] = []
    await installCompanionHomeWebMocks(authedPage, unhandledApiRequests)

    await runCompanionHomeParityContract({
      platform: "web",
      page: authedPage
    })

    const critical = getCriticalIssues(diagnostics)

    expect(unhandledApiRequests).toEqual([])
    expect(critical.pageErrors).toEqual([])
    expect(critical.consoleErrors).toEqual([])
    expect(critical.requestFailures).toEqual([])
  })
})
