import AxeBuilder from "@axe-core/playwright"
import { test, expect, seedAuth, getCriticalIssues } from "./smoke.setup"
import { waitForAppShell, waitForVisualSettle } from "../utils/helpers"

const LOAD_TIMEOUT = 30_000
const HOSTED_MODE =
  String(process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE || "").trim().toLowerCase() ===
  "hosted"

type HighRiskRoute = {
  path: string
  name: string
  acceptablePaths?: string[]
  requiresSeededAuth?: boolean
  mayRedirectWhenUnavailable?: boolean
}

const HIGH_RISK_ROUTES: HighRiskRoute[] = [
  { path: "/", name: "Home" },
  {
    path: "/login",
    name: "Login",
    acceptablePaths: HOSTED_MODE ? ["/login"] : ["/login", "/settings/tldw"],
    requiresSeededAuth: false
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

function isTransientAxeNavigationError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error)
  return /Execution context was destroyed|Frame was detached/i.test(message)
}

async function runStage4AxeScan(page: Parameters<typeof seedAuth>[0]) {
  let lastError: unknown

  for (let attempt = 0; attempt < 3; attempt += 1) {
    await waitForVisualSettle(page, LOAD_TIMEOUT)

    try {
      return await new AxeBuilder({ page })
        .withRules(STAGE4_A11Y_RULES)
        .disableRules(["color-contrast"])
        .analyze()
    } catch (error) {
      lastError = error
      if (!isTransientAxeNavigationError(error) || attempt === 2) {
        throw error
      }
    }
  }

  throw lastError ?? new Error("Stage 4 Axe scan failed without a captured error.")
}

async function waitForHighRiskRouteReady(
  page: Parameters<typeof seedAuth>[0],
  route: HighRiskRoute
): Promise<void> {
  if (route.path !== "/login") return

  await expect
    .poll(
      async () => {
        const loginHeadingVisible = await page
          .getByRole("heading", { name: /^sign in$/i })
          .isVisible()
          .catch(() => false)
        const serverUrlVisible = await page
          .getByLabel(/server url/i)
          .isVisible()
          .catch(() => false)
        const apiKeyVisible = await page
          .getByLabel(/api key/i)
          .isVisible()
          .catch(() => false)
        const loginButtonVisible = await page
          .getByRole("button", { name: /^(login|sign in|verify & login)$/i })
          .isVisible()
          .catch(() => false)

        return (
          loginHeadingVisible ||
          serverUrlVisible ||
          apiKeyVisible ||
          loginButtonVisible
        )
      },
      {
        timeout: LOAD_TIMEOUT,
        message:
          "Login route did not render either the hosted sign-in form or the shared tldw settings form."
      }
    )
    .toBe(true)
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
      await waitForVisualSettle(page, LOAD_TIMEOUT)

      const status = response?.status() ?? 0
      test.skip(status >= 400, `Route unavailable in smoke runtime (status ${status})`)

      const acceptablePaths = route.acceptablePaths ?? [route.path]
      const finalPath = new URL(page.url()).pathname
      if (route.mayRedirectWhenUnavailable && !acceptablePaths.includes(finalPath)) {
        test.skip(
          `Route ${route.path} redirected to ${finalPath}; feature is unavailable in this runtime`
        )
      }
      expect(
        acceptablePaths,
        `Route ${route.path} resolved to unexpected path ${finalPath}`
      ).toContain(finalPath)
      await waitForHighRiskRouteReady(page, route)

      const issues = getCriticalIssues(diagnostics)
      expect(
        issues.pageErrors,
        `Uncaught page errors while scanning ${route.path}`
      ).toHaveLength(0)

      const results = await runStage4AxeScan(page)

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
