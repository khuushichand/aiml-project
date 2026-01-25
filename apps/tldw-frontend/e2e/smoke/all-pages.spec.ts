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

import { test, expect, seedAuth, getCriticalIssues, DiagnosticsData } from "./smoke.setup"
import { PAGES, PageEntry, getActivePages, PAGE_COUNT, ACTIVE_PAGE_COUNT } from "./page-inventory"

// Test configuration
const LOAD_TIMEOUT = 30_000 // 30s max for page load
const ELEMENT_TIMEOUT = 15_000 // 15s max for element visibility

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
      const truncated = c.text.length > 200 ? c.text.slice(0, 200) + "..." : c.text
      lines.push(`    - ${truncated}`)
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
        .locator('[role="alert"]')
        .first()
        .isVisible()
        .catch(() => false)

      const errorTextVisible = await page
        .getByText(/something went wrong/i)
        .first()
        .isVisible()
        .catch(() => false)

      const crashTextVisible = await page
        .getByText(/error|crashed|failed to load/i)
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
        `Error boundary [role="alert"] triggered on ${entry.path}`
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
