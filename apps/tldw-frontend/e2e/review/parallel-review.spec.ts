/**
 * Parallel Page Review Smoke Tests
 *
 * Automated smoke tests that complement the interactive review.
 * Tests WebUI and Extension pages for basic loading and error states.
 *
 * Run with: npx playwright test e2e/review/parallel-review.spec.ts
 */

import { test, expect, seedAuth, getCriticalIssues, DiagnosticsData } from "../smoke/smoke.setup"
import { Page } from "@playwright/test"
import { waitForAppShell } from "../utils/helpers"
import {
  PAGE_MAPPINGS,
  WEBUI_ONLY_PAGES,
  ReviewPriority,
  getPagesBySession
} from "../page-mapping"

// Configuration
const LOAD_TIMEOUT = 30_000
const NETWORK_TIMEOUT = 15_000

// ═══════════════════════════════════════════════════════════════════════════
// Test Helpers
// ═══════════════════════════════════════════════════════════════════════════

async function testPageLoads(
  page: Page,
  path: string,
  diagnostics: DiagnosticsData
): Promise<void> {
  // Navigate
  const response = await page.goto(path, {
    waitUntil: "domcontentloaded",
    timeout: LOAD_TIMEOUT
  })

  await waitForAppShell(page, NETWORK_TIMEOUT)

  // Check HTTP status
  const status = response?.status()
  if (status && status >= 400 && status !== 404) {
    console.warn(`HTTP ${status} for ${path}`)
  }

  // Check for error boundary
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

  // Get critical issues
  const issues = getCriticalIssues(diagnostics)

  // Assertions
  expect(
    errorBoundaryVisible,
    `Error boundary triggered on ${path}`
  ).toBeFalsy()

  expect(
    errorTextVisible,
    `"Something went wrong" visible on ${path}`
  ).toBeFalsy()

  expect(
    issues.pageErrors,
    `Uncaught errors on ${path}: ${issues.pageErrors.map((e) => e.message).join(", ")}`
  ).toHaveLength(0)
}

// ═══════════════════════════════════════════════════════════════════════════
// Test Suites by Session
// ═══════════════════════════════════════════════════════════════════════════

const sessionDescriptions: Record<ReviewPriority, string> = {
  1: "Critical Paths",
  2: "Core Settings",
  3: "Knowledge & Content",
  4: "Workspace Tools",
  5: "Audio & Advanced",
  6: "Admin & Connectors",
  7: "Extension-Specific & Playgrounds"
}

// Generate test suites for each session
for (let session = 1; session <= 7; session++) {
  const sessionNum = session as ReviewPriority
  const pages = getPagesBySession(sessionNum)

  test.describe(`Session ${session}: ${sessionDescriptions[sessionNum]}`, () => {
    test.describe.configure({ mode: "parallel" })

    test.beforeEach(async ({ page }) => {
      await seedAuth(page)
    })

    for (const mapping of pages) {
      if (mapping.webuiPath) {
        test(`[WebUI] ${mapping.name} (${mapping.webuiPath})`, async ({ page, diagnostics }) => {
          await testPageLoads(page, mapping.webuiPath, diagnostics)
        })
      }

      // Test extension options path if exists
      if (mapping.extensionOptionsPath) {
        test.skip(`[Ext:Options] ${mapping.name} (${mapping.extensionOptionsPath})`, async () => {
          // Extension testing requires different setup - skip for now
          // These are tested via the interactive review or extension-specific tests
        })
      }

      // Test extension sidepanel path if exists
      if (mapping.extensionSidepanelPath) {
        test.skip(`[Ext:Sidepanel] ${mapping.name} (${mapping.extensionSidepanelPath})`, async () => {
          // Sidepanel testing requires extension context
        })
      }
    }
  })
}

// ═══════════════════════════════════════════════════════════════════════════
// WebUI-Only Pages
// ═══════════════════════════════════════════════════════════════════════════

test.describe("WebUI-Only Pages", () => {
  test.describe.configure({ mode: "parallel" })

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  for (const mapping of WEBUI_ONLY_PAGES) {
    test(`${mapping.name} (${mapping.webuiPath})`, async ({ page, diagnostics }) => {
      await testPageLoads(page, mapping.webuiPath, diagnostics)
    })
  }
})

// ═══════════════════════════════════════════════════════════════════════════
// Category-Based Suites
// ═══════════════════════════════════════════════════════════════════════════

const categories = ["chat", "settings", "media", "workspace", "knowledge", "audio", "admin"] as const

for (const category of categories) {
  const categoryPages = [...PAGE_MAPPINGS, ...WEBUI_ONLY_PAGES].filter(
    (p) => p.category === category
  )

  if (categoryPages.length > 0) {
    test.describe(`Category: ${category}`, () => {
      test.describe.configure({ mode: "parallel" })

      test.beforeEach(async ({ page }) => {
        await seedAuth(page)
      })

  for (const mapping of categoryPages) {
    test(`${mapping.name}`, async ({ page, diagnostics }) => {
      if (!mapping.webuiPath) return
      await testPageLoads(page, mapping.webuiPath, diagnostics)
    })
  }
    })
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Shared Component Parity Check
// ═══════════════════════════════════════════════════════════════════════════

test.describe("Shared Components - Basic Load", () => {
  test.describe.configure({ mode: "parallel" })

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  const sharedComponentPages = PAGE_MAPPINGS.filter((p) => p.sharedComponent !== null)

  for (const mapping of sharedComponentPages) {
    test(`${mapping.sharedComponent} via WebUI (${mapping.webuiPath})`, async ({
      page,
      diagnostics
    }) => {
      await testPageLoads(page, mapping.webuiPath, diagnostics)

      // Additional check: verify no infinite loading states
      const loadingSpinners = await page.locator("[data-testid='loading-spinner'], .ant-spin-spinning").count()

      let stillLoading = loadingSpinners
      if (loadingSpinners > 0) {
        await expect
          .poll(
            async () => page.locator("[data-testid='loading-spinner'], .ant-spin-spinning").count(),
            { timeout: 2_000 }
          )
          .not.toBe(loadingSpinners)
          .catch(() => {})
        stillLoading = await page.locator("[data-testid='loading-spinner'], .ant-spin-spinning").count()
      }

      // If there are fewer spinners now, loading is progressing
      // If spinners persist, might be stuck
      if (stillLoading > 0 && stillLoading === loadingSpinners) {
        console.warn(
          `Possible infinite loading on ${mapping.webuiPath} (${stillLoading} spinners)`
        )
      }
    })
  }
})
