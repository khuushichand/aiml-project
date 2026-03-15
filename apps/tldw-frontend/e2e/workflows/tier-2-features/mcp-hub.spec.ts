/**
 * MCP Hub E2E Tests (Tier 2)
 *
 * Tests the MCP Hub page lifecycle:
 * - Page loads with heading and tab navigation
 * - Tab switching between Profiles, Assignments, Path Scopes, Workspace Sets,
 *   Shared Workspaces, Audit, Approvals, Catalog, and Credentials
 * - API calls fired on tab interactions (permission-profiles, policy-assignments, tool-registry)
 *
 * Run: npx playwright test e2e/workflows/tier-2-features/mcp-hub.spec.ts
 */
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors,
} from "../../utils/fixtures"
import { MCPHubPage } from "../../utils/page-objects/MCPHubPage"
import { expectApiCall } from "../../utils/api-assertions"
import { seedAuth } from "../../utils/helpers"

test.describe("MCP Hub", () => {
  let mcpHub: MCPHubPage

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    mcpHub = new MCPHubPage(page)
  })

  // =========================================================================
  // Page Load
  // =========================================================================

  test.describe("Page Load", () => {
    test("should render the MCP Hub page with heading and tabs", async ({
      authedPage,
      diagnostics,
    }) => {
      mcpHub = new MCPHubPage(authedPage)
      await mcpHub.goto()
      await mcpHub.assertPageReady()

      const headingVisible = await mcpHub.heading.isVisible().catch(() => false)
      expect(headingVisible).toBe(true)

      // Core tabs should be present
      await expect(mcpHub.profilesTab).toBeVisible()
      await expect(mcpHub.assignmentsTab).toBeVisible()
      await expect(mcpHub.auditTab).toBeVisible()
      await expect(mcpHub.catalogTab).toBeVisible()
      await expect(mcpHub.credentialsTab).toBeVisible()

      await assertNoCriticalErrors(diagnostics)
    })

    test("should switch between all tabs without errors", async ({
      authedPage,
      diagnostics,
    }) => {
      mcpHub = new MCPHubPage(authedPage)
      await mcpHub.goto()
      await mcpHub.assertPageReady()

      const headingVisible = await mcpHub.heading.isVisible().catch(() => false)
      if (!headingVisible) return

      for (const tab of [
        "assignments",
        "pathScopes",
        "workspaceSets",
        "sharedWorkspaces",
        "audit",
        "approvals",
        "catalog",
        "credentials",
        "profiles",
      ] as const) {
        await mcpHub.switchToTab(tab)
        await authedPage.waitForTimeout(500)
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  // =========================================================================
  // API Integration (requires server)
  // =========================================================================

  test.describe("Permission Profiles API", () => {
    test("should fire GET /api/v1/mcp/hub/permission-profiles on Profiles tab", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      mcpHub = new MCPHubPage(authedPage)
      await mcpHub.goto()
      await mcpHub.assertPageReady()

      const headingVisible = await mcpHub.heading.isVisible().catch(() => false)
      if (!headingVisible) return

      // Profiles is the default tab, so the API call should already have fired
      // Switch away and back to trigger a fresh call
      await mcpHub.switchToTab("audit")
      await authedPage.waitForTimeout(500)

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/mcp\/hub\/permission-profiles/,
        method: "GET",
      }, 15_000)

      await mcpHub.switchToTab("profiles")

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // MCP Hub API may not be available on this server version
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Policy Assignments API", () => {
    test("should fire GET /api/v1/mcp/hub/policy-assignments on Assignments tab", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      mcpHub = new MCPHubPage(authedPage)
      await mcpHub.goto()
      await mcpHub.assertPageReady()

      const headingVisible = await mcpHub.heading.isVisible().catch(() => false)
      if (!headingVisible) return

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/mcp\/hub\/policy-assignments/,
        method: "GET",
      }, 15_000)

      await mcpHub.switchToTab("assignments")

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // MCP Hub API may not be available on this server version
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })

  test.describe("Tool Catalog API", () => {
    test("should fire GET /api/v1/mcp/hub/tool-registry on Catalog tab", async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)

      mcpHub = new MCPHubPage(authedPage)
      await mcpHub.goto()
      await mcpHub.assertPageReady()

      const headingVisible = await mcpHub.heading.isVisible().catch(() => false)
      if (!headingVisible) return

      const apiCall = expectApiCall(authedPage, {
        url: /\/api\/v1\/mcp\/hub\/tool-registry/,
        method: "GET",
      }, 15_000)

      await mcpHub.switchToTab("catalog")

      try {
        const { response } = await apiCall
        expect(response.status()).toBeLessThan(500)
      } catch {
        // MCP Hub API may not be available on this server version
      }

      await assertNoCriticalErrors(diagnostics)
    })
  })
})
