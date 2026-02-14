import type { Page } from "@playwright/test"
import { test, expect, AUTH_CONFIG, getCriticalIssues } from "./smoke.setup"

const LOAD_TIMEOUT = 30_000
const RUNTIME_OVERLAY_PATTERNS = [
  /Runtime(?:\s+\w+)?\s+Error/i,
  /Runtime SyntaxError/i,
  /Invalid or unexpected token/i,
  /Objects are not valid as a React child/i,
  /message\.error is not a function/i
]

const hasRuntimeOverlaySignal = (input: string): boolean =>
  RUNTIME_OVERLAY_PATTERNS.some((pattern) => pattern.test(input))

async function assertNoRuntimeOverlay(
  page: Page,
  issues: ReturnType<typeof getCriticalIssues>,
  context: string
): Promise<void> {
  const runtimeConsoleErrors = issues.consoleErrors
    .map((entry) => entry.text)
    .filter(hasRuntimeOverlaySignal)

  const overlaySnapshot = await page.evaluate(() => ({
    bodyText: document.body?.innerText ?? ""
  }))
  const bodyHasRuntimeSignal = hasRuntimeOverlaySignal(overlaySnapshot.bodyText)
  const bodySnippet = bodyHasRuntimeSignal
    ? overlaySnapshot.bodyText.replace(/\s+/g, " ").trim().slice(0, 220)
    : ""
  const hasRuntimeOverlay = runtimeConsoleErrors.length > 0 || bodyHasRuntimeSignal

  expect(
    hasRuntimeOverlay,
    [
      `Runtime overlay detected on ${context}.`,
      `Console matches: ${runtimeConsoleErrors.length}`,
      bodySnippet ? `Body snippet: ${bodySnippet}` : ""
    ]
      .filter(Boolean)
      .join(" ")
  ).toBeFalsy()
}

test.describe("Smoke Tests - Auth Error Degradation", () => {
  test("invalid API key on chat load does not trigger runtime overlay", async ({
    page,
    diagnostics
  }) => {
    await page.addInitScript(
      (cfg) => {
        try {
          localStorage.setItem(
            "tldwConfig",
            JSON.stringify({
              serverUrl: cfg.serverUrl,
              authMode: "single-user",
              apiKey: "INVALID-KEY-E2E"
            })
          )
        } catch {}

        try {
          localStorage.setItem("__tldw_first_run_complete", "true")
        } catch {}

        try {
          localStorage.removeItem("__tldw_allow_offline")
        } catch {}
      },
      { serverUrl: AUTH_CONFIG.serverUrl }
    )

    const response = await page.goto("/chat", {
      waitUntil: "domcontentloaded",
      timeout: LOAD_TIMEOUT
    })
    await page.waitForLoadState("networkidle", { timeout: LOAD_TIMEOUT }).catch(() => {})

    const issues = getCriticalIssues(diagnostics)
    await assertNoRuntimeOverlay(page, issues, "/chat?invalid-api-key")

    const status = response?.status() ?? 0
    expect(
      status === 0 || status < 500,
      `Expected /chat to stay available with invalid API key (status: ${status})`
    ).toBeTruthy()
    await expect(page.getByTestId("chat-sidebar")).toBeVisible()
    expect(
      issues.pageErrors,
      "Uncaught page errors should not occur when API key is invalid"
    ).toHaveLength(0)
  })
})
