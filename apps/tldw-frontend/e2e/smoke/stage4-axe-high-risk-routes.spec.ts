import AxeBuilder from "@axe-core/playwright"
import { test, expect, seedAuth, getCriticalIssues } from "./smoke.setup"
import { waitForAppShell } from "../utils/helpers"

const LOAD_TIMEOUT = 30_000

type HighRiskRoute = {
  path: string
  name: string
  requiresSeededAuth?: boolean
  mayRedirectWhenUnavailable?: boolean
}

const HIGH_RISK_ROUTES: HighRiskRoute[] = [
  { path: "/", name: "Home" },
  {
    path: "/login",
    name: "Login",
    requiresSeededAuth: false,
    mayRedirectWhenUnavailable: true
  },
  { path: "/chat", name: "Chat" },
  {
    path: "/persona",
    name: "Persona",
    mayRedirectWhenUnavailable: true
  },
  { path: "/document-workspace", name: "Document Workspace" },
  { path: "/workflow-editor", name: "Workflow Editor" },
  { path: "/collections", name: "Collections" },
  { path: "/data-tables", name: "Data Tables" },
  { path: "/watchlists", name: "Watchlists" },
  { path: "/evaluations", name: "Evaluations" },
  { path: "/knowledge", name: "Knowledge QA" },
  { path: "/companion", name: "Companion" },
  { path: "/admin/mlx", name: "Admin MLX" },
  { path: "/quick-chat-popout", name: "Quick Chat Popout" },
  { path: "/workspace-playground", name: "Workspace Playground" },
  { path: "/settings/image-generation", name: "Image Generation Settings" }
]

const STAGE4_A11Y_RULES = [
  "landmark-one-main",
  "region",
  "link-name",
  "image-alt",
  "input-image-alt",
  "select-name",
  "aria-command-name",
  "aria-toggle-field-name"
]

async function waitForRouteToSettle(
  page: Parameters<typeof seedAuth>[0],
  expectedPath: string,
  mayRedirectWhenUnavailable: boolean | undefined
): Promise<void> {
  if (mayRedirectWhenUnavailable) {
    try {
      await page.waitForURL(
        (url) => new URL(url.toString()).pathname !== expectedPath,
        { timeout: 1_500 }
      )
    } catch {}
  }

  try {
    await page.waitForLoadState("networkidle", { timeout: 1_500 })
  } catch {}

  await page.waitForTimeout(250)
}

async function analyzeA11yWithRetry(
  page: Parameters<typeof seedAuth>[0],
  routePath: string
) {
  let lastError: unknown
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      return await new AxeBuilder({ page })
        .withRules(STAGE4_A11Y_RULES)
        .disableRules(["color-contrast"])
        .analyze()
    } catch (error) {
      lastError = error
      const message = error instanceof Error ? error.message : String(error)
      if (!message.includes("Execution context was destroyed") || attempt === 1) {
        throw error
      }

      await waitForAppShell(page, LOAD_TIMEOUT)
      await waitForRouteToSettle(page, routePath, true)
    }
  }

  throw lastError instanceof Error
    ? lastError
    : new Error(`Axe scan failed for ${routePath}`)
}

async function clearSeededAuth(page: Parameters<typeof seedAuth>[0]): Promise<void> {
  await page.addInitScript(() => {
    try {
      localStorage.removeItem("tldwConfig")
      localStorage.removeItem("__tldw_first_run_complete")
      localStorage.removeItem("__tldw_allow_offline")
    } catch {}
  })
}

function formatAxeViolations(routePath: string, violations: Awaited<ReturnType<AxeBuilder["analyze"]>>["violations"]): string {
  if (violations.length === 0) return `${routePath}: no violations`
  return [
    `${routePath}: ${violations.length} serious/critical Axe violations`,
    ...violations.map((violation) => {
      const nodes = violation.nodes
        .slice(0, 3)
        .map((node) => node.target.join(" "))
        .join(" | ")
      return `- ${violation.id} [${violation.impact ?? "unknown"}] -> ${nodes}`
    })
  ].join("\n")
}

test.describe("Stage 4 Axe high-risk routes", () => {
  for (const route of HIGH_RISK_ROUTES) {
    test(`${route.name} (${route.path}) passes Stage 4 Axe checks`, async ({
      page,
      diagnostics
    }) => {
      if (route.requiresSeededAuth === false) {
        await clearSeededAuth(page)
      } else {
        await seedAuth(page)
      }

      const response = await page.goto(route.path, {
        waitUntil: "domcontentloaded",
        timeout: LOAD_TIMEOUT
      })
      await waitForAppShell(page, LOAD_TIMEOUT)
      await waitForRouteToSettle(
        page,
        route.path,
        route.mayRedirectWhenUnavailable
      )

      const status = response?.status() ?? 0
      test.skip(status >= 400, `Route unavailable in smoke runtime (status ${status})`)

      const finalPath = new URL(page.url()).pathname
      if (route.mayRedirectWhenUnavailable && finalPath !== route.path) {
        test.skip(
          `Route ${route.path} redirected to ${finalPath}; feature is unavailable in this runtime`
        )
      }

      const issues = getCriticalIssues(diagnostics)
      expect(
        issues.pageErrors,
        `Uncaught page errors while scanning ${route.path}`
      ).toHaveLength(0)

      const results = await analyzeA11yWithRetry(page, route.path)

      const blockingViolations = results.violations.filter((violation) =>
        violation.impact === "serious" || violation.impact === "critical"
      )

      expect(
        blockingViolations,
        formatAxeViolations(route.path, blockingViolations)
      ).toEqual([])
    })
  }
})
