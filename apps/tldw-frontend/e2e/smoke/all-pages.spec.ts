/**
 * Smoke tests for all pages in tldw-frontend
 *
 * These tests visit each page and verify:
 * - Page loads without error boundaries
 * - No uncaught JavaScript errors
 * - No critical console errors
 * - Network requests complete (or fail gracefully)
 *
 * Run with: npm run e2e:smoke
 */

import { test, expect, seedAuth, getCriticalIssues } from "./smoke.setup"
import { PAGES, PageEntry, getActivePages, PAGE_COUNT, ACTIVE_PAGE_COUNT } from "./page-inventory"

// Test configuration
const LOAD_TIMEOUT = 30_000 // 30s max for page load
const ELEMENT_TIMEOUT = 15_000 // 15s max for element visibility
const VERBOSE_CONSOLE = process.env.TLDW_SMOKE_VERBOSE_CONSOLE === "1"
const KEY_NAV_TARGETS = [
  "/chat",
  "/media",
  "/knowledge",
  "/notes",
  "/prompts",
  "/settings/tldw"
]
const WAYFINDING_404_PATH = "/__wayfinding-missing-route__"

const keyNavEntries: PageEntry[] = KEY_NAV_TARGETS.map(
  (targetPath) => PAGES.find((entry) => entry.path === targetPath)
).filter((entry): entry is PageEntry => Boolean(entry))

/**
 * Format diagnostics for console output
 */
function formatDiagnostics(
  entry: PageEntry,
  issues: ReturnType<typeof getCriticalIssues>
): string {
  const lines: string[] = []

  if (issues.pageErrors.length) {
    lines.push(`  PAGE ERRORS (${issues.pageErrors.length}):`)
    issues.pageErrors.forEach((e) => {
      lines.push(`    - ${e.message}`)
      if (e.stack) {
        const firstStackLine = e.stack.split("\n")[1]?.trim()
        if (firstStackLine) lines.push(`      ${firstStackLine}`)
      }
    })
  }

  if (issues.consoleErrors.length) {
    lines.push(`  CONSOLE ERRORS (${issues.consoleErrors.length}):`)
    issues.consoleErrors.forEach((c) => {
      const text = VERBOSE_CONSOLE
        ? c.text
        : c.text.length > 200
          ? c.text.slice(0, 200) + "..."
          : c.text
      lines.push(`    - ${text}`)
    })
  }

  if (issues.requestFailures.length) {
    lines.push(`  REQUEST FAILURES (${issues.requestFailures.length}):`)
    issues.requestFailures.forEach((r) => {
      lines.push(`    - ${r.url} (${r.errorText})`)
    })
  }

  return lines.length ? `\n${entry.path}:\n${lines.join("\n")}` : ""
}

test.describe("Smoke Tests - All Pages", () => {
  test.describe.configure({ mode: "parallel" })

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  // Log test suite info
  test.beforeAll(() => {
    console.log(`\nSmoke test suite: ${ACTIVE_PAGE_COUNT} pages (${PAGE_COUNT - ACTIVE_PAGE_COUNT} skipped)\n`)
  })

  // Generate a test for each active page
  for (const entry of getActivePages()) {
    test(`${entry.name} (${entry.path})`, async ({ page, diagnostics }) => {
      // Navigate to the page
      const response = await page.goto(entry.path, {
        waitUntil: "domcontentloaded",
        timeout: LOAD_TIMEOUT
      })

      // Wait for network to settle (but don't fail if it times out)
      await page.waitForLoadState("networkidle", { timeout: LOAD_TIMEOUT }).catch(() => {
        // Network didn't settle, that's okay - we'll check for errors
      })

      // Check HTTP response status
      const status = response?.status()
      if (status && status >= 400 && status !== 404) {
        // 404 is handled separately, other 4xx/5xx are issues
        console.warn(`HTTP ${status} for ${entry.path}`)
      }

      // Check for error boundary UI patterns
      const errorBoundaryVisible = await page
        .getByTestId("error-boundary")
        .first()
        .isVisible()
        .catch(() => false)

      const errorTextVisible = await page
        .getByText(/something went wrong/i)
        .first()
        .isVisible()
        .catch(() => false)

      // If page has an expected test ID, verify it's visible
      if (entry.expectedTestId) {
        await expect(page.getByTestId(entry.expectedTestId)).toBeVisible({
          timeout: ELEMENT_TIMEOUT
        })
      }

      // Get critical issues from diagnostics
      const issues = getCriticalIssues(diagnostics)

      // Log any issues found (useful for debugging)
      const diagnosticOutput = formatDiagnostics(entry, issues)
      if (diagnosticOutput) {
        console.log(diagnosticOutput)
      }

      // Assertions
      expect(
        errorBoundaryVisible,
        `Error boundary [data-testid="error-boundary"] triggered on ${entry.path}`
      ).toBeFalsy()

      expect(
        errorTextVisible,
        `"Something went wrong" text visible on ${entry.path}`
      ).toBeFalsy()

      // Page errors are hard failures
      expect(
        issues.pageErrors,
        `Uncaught page errors on ${entry.path}: ${issues.pageErrors.map((e) => e.message).join(", ")}`
      ).toHaveLength(0)

      // Console errors are soft warnings in development but tracked
      // Uncomment to make console errors fail the test:
      // expect(
      //   issues.consoleErrors,
      //   `Console errors on ${entry.path}`
      // ).toHaveLength(0)
    })
  }
})

// Category-specific test suites for selective running
test.describe("Smoke Tests - Chat", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  for (const entry of PAGES.filter((p) => p.category === "chat" && !p.skip)) {
    test(`${entry.name}`, async ({ page, diagnostics }) => {
      await page.goto(entry.path, { waitUntil: "domcontentloaded" })
      await page.waitForLoadState("networkidle", { timeout: LOAD_TIMEOUT }).catch(() => {})

      const issues = getCriticalIssues(diagnostics)
      expect(issues.pageErrors).toHaveLength(0)
    })
  }
})

test.describe("Smoke Tests - Settings", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  for (const entry of PAGES.filter((p) => p.category === "settings" && !p.skip)) {
    test(`${entry.name}`, async ({ page, diagnostics }) => {
      await page.goto(entry.path, { waitUntil: "domcontentloaded" })
      await page.waitForLoadState("networkidle", { timeout: LOAD_TIMEOUT }).catch(() => {})

      const issues = getCriticalIssues(diagnostics)
      expect(issues.pageErrors).toHaveLength(0)
    })
  }
})

test.describe("Smoke Tests - Admin", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  for (const entry of PAGES.filter((p) => p.category === "admin" && !p.skip)) {
    test(`${entry.name}`, async ({ page, diagnostics }) => {
      await page.goto(entry.path, { waitUntil: "domcontentloaded" })
      await page.waitForLoadState("networkidle", { timeout: LOAD_TIMEOUT }).catch(() => {})

      const issues = getCriticalIssues(diagnostics)
      expect(issues.pageErrors).toHaveLength(0)
    })
  }
})

test.describe("Smoke Tests - Workspace", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  for (const entry of PAGES.filter((p) => p.category === "workspace" && !p.skip)) {
    test(`${entry.name}`, async ({ page, diagnostics }) => {
      await page.goto(entry.path, { waitUntil: "domcontentloaded" })
      await page.waitForLoadState("networkidle", { timeout: LOAD_TIMEOUT }).catch(() => {})

      const issues = getCriticalIssues(diagnostics)
      expect(issues.pageErrors).toHaveLength(0)
    })
  }
})

test.describe("Smoke Tests - Knowledge", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  for (const entry of PAGES.filter((p) => p.category === "knowledge" && !p.skip)) {
    test(`${entry.name}`, async ({ page, diagnostics }) => {
      await page.goto(entry.path, { waitUntil: "domcontentloaded" })
      await page.waitForLoadState("networkidle", { timeout: LOAD_TIMEOUT }).catch(() => {})

      const issues = getCriticalIssues(diagnostics)
      expect(issues.pageErrors).toHaveLength(0)
    })
  }
})

test.describe("Smoke Tests - Audio", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  for (const entry of PAGES.filter((p) => p.category === "audio" && !p.skip)) {
    test(`${entry.name}`, async ({ page, diagnostics }) => {
      await page.goto(entry.path, { waitUntil: "domcontentloaded" })
      await page.waitForLoadState("networkidle", { timeout: LOAD_TIMEOUT }).catch(() => {})

      const issues = getCriticalIssues(diagnostics)
      expect(issues.pageErrors).toHaveLength(0)
    })
  }
})

test.describe("Smoke Tests - Key Navigation Targets", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("inventory contains all key nav routes", () => {
    expect(keyNavEntries).toHaveLength(KEY_NAV_TARGETS.length)
  })

  for (const entry of keyNavEntries) {
    test(`${entry.name} (${entry.path})`, async ({ page, diagnostics }) => {
      const response = await page.goto(entry.path, {
        waitUntil: "domcontentloaded",
        timeout: LOAD_TIMEOUT
      })
      await page.waitForLoadState("networkidle", { timeout: LOAD_TIMEOUT }).catch(() => {})

      const issues = getCriticalIssues(diagnostics)
      const status = response?.status() ?? 0

      expect(
        status === 0 || status < 400,
        `Expected key target ${entry.path} to load successfully (status: ${status})`
      ).toBeTruthy()
      expect(
        issues.pageErrors,
        `Uncaught page errors on key nav target ${entry.path}`
      ).toHaveLength(0)
    })
  }
})

test.describe("Smoke Tests - Wayfinding", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("settings route shows active location context", async ({ page, diagnostics }) => {
    const response = await page.goto("/settings/tldw", {
      waitUntil: "domcontentloaded",
      timeout: LOAD_TIMEOUT
    })
    await page.waitForLoadState("networkidle", { timeout: LOAD_TIMEOUT }).catch(() => {})

    const status = response?.status() ?? 0
    test.skip(
      status >= 400,
      `Settings wayfinding markers unavailable in this runtime (status: ${status})`
    )

    await expect(page.getByTestId("settings-navigation")).toBeVisible()
    await expect(page.getByTestId("settings-current-section")).toBeVisible()

    const activeSettingsLink = page.locator(
      '[data-testid^="settings-nav-link-"][aria-current="page"]'
    )
    await expect(activeSettingsLink.first()).toBeVisible()

    const issues = getCriticalIssues(diagnostics)
    expect(
      issues.pageErrors,
      "Uncaught page errors while validating settings wayfinding"
    ).toHaveLength(0)
  })

  test("legacy alias redirects to canonical destination with params preserved", async ({
    page,
    diagnostics
  }) => {
    const response = await page.goto("/search?q=wayfinding-smoke", {
      waitUntil: "domcontentloaded",
      timeout: LOAD_TIMEOUT
    })
    const status = response?.status() ?? 0
    test.skip(
      status >= 400,
      `Alias redirect path unavailable in this runtime (status: ${status})`
    )

    await page.waitForURL(/\/knowledge\?q=wayfinding-smoke/, {
      timeout: LOAD_TIMEOUT
    })
    await page.waitForLoadState("networkidle", { timeout: LOAD_TIMEOUT }).catch(() => {})

    const issues = getCriticalIssues(diagnostics)
    expect(
      issues.pageErrors,
      "Uncaught page errors while validating alias redirect wayfinding"
    ).toHaveLength(0)
  })

  test("404 recovery controls keep predictable keyboard order", async ({
    page,
    diagnostics
  }) => {
    await page.goto(WAYFINDING_404_PATH, {
      waitUntil: "domcontentloaded",
      timeout: LOAD_TIMEOUT
    })
    await page.waitForLoadState("networkidle", { timeout: LOAD_TIMEOUT }).catch(() => {})

    const hasWayfindingPanel =
      (await page.getByTestId("not-found-recovery-panel").count()) > 0
    test.skip(
      !hasWayfindingPanel,
      "Wayfinding-specific 404 recovery panel not available in this runtime target"
    )

    await expect(page.getByRole("heading", { name: "We could not find that route" })).toBeVisible()
    await expect(page.getByTestId("not-found-recovery-panel")).toBeVisible()

    const controlOrder = await page
      .locator("[data-testid='not-found-recovery-panel'] [data-testid]")
      .evaluateAll((elements) =>
        elements.map((element) => element.getAttribute("data-testid"))
      )

    expect(controlOrder).toEqual([
      "not-found-go-chat",
      "not-found-open-knowledge",
      "not-found-open-media",
      "not-found-open-settings",
      "not-found-go-back"
    ])

    const goChatButton = page.getByTestId("not-found-go-chat")
    await goChatButton.focus()
    await expect(goChatButton).toBeFocused()
    await page.keyboard.press("Tab")
    await expect(page.getByTestId("not-found-open-knowledge")).toBeFocused()

    const issues = getCriticalIssues(diagnostics)
    expect(
      issues.pageErrors,
      "Uncaught page errors while validating 404 recovery wayfinding"
    ).toHaveLength(0)
  })
})
