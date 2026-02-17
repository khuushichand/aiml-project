import { test as base, expect, Page } from "@playwright/test"

/**
 * Diagnostics data collected during page visits
 */
export interface DiagnosticsData {
  console: Array<{ type: string; text: string; location?: { url: string; lineNumber: number } }>
  pageErrors: Array<{ message: string; stack: string }>
  requestFailures: Array<{ url: string; errorText: string }>
}

export type SmokeAllowlistScope = "console" | "request"

export interface SmokeHardGateAllowlistRule {
  id: string
  scope: SmokeAllowlistScope
  pattern: RegExp
  routes?: string[]
  rationale: string
  owner: string
  expiresOn: string
}

type ConsoleIssue = { type: string; text: string }
type RequestIssue = { url: string; errorText: string }

export interface ClassifiedSmokeIssues {
  pageErrors: Array<{ message: string; stack: string }>
  allowlistedConsoleErrors: Array<{ entry: ConsoleIssue; rule: SmokeHardGateAllowlistRule }>
  unexpectedConsoleErrors: ConsoleIssue[]
  allowlistedRequestFailures: Array<{
    entry: RequestIssue
    rule: SmokeHardGateAllowlistRule
  }>
  unexpectedRequestFailures: RequestIssue[]
}

/**
 * Extended test fixture that automatically collects diagnostics
 */
export const test = base.extend<{ diagnostics: DiagnosticsData }>({
  diagnostics: async ({ page }, use) => {
    const data: DiagnosticsData = {
      console: [],
      pageErrors: [],
      requestFailures: []
    }

    // Collect console messages
    page.on("console", (msg) => {
      const location = msg.location()
      data.console.push({
        type: msg.type(),
        text: msg.text(),
        location: location.url ? { url: location.url, lineNumber: location.lineNumber } : undefined
      })
    })

    // Collect page errors (uncaught exceptions)
    page.on("pageerror", (err) => {
      data.pageErrors.push({
        message: err.message,
        stack: err.stack || ""
      })
    })

    // Collect failed network requests
    page.on("requestfailed", (req) => {
      data.requestFailures.push({
        url: req.url(),
        errorText: req.failure()?.errorText || ""
      })
    })

    await use(data)
  }
})

export { expect }

/**
 * Auth configuration for smoke tests
 */
export const AUTH_CONFIG = {
  serverUrl: process.env.TLDW_SERVER_URL || "http://127.0.0.1:8000",
  apiKey: process.env.TLDW_API_KEY || "THIS-IS-A-SECURE-KEY-123-FAKE-KEY",
  allowOffline: process.env.TLDW_E2E_ALLOW_OFFLINE !== "0"
}

type SeedAuthOverrides = {
  serverUrl?: string
  authMode?: "single-user" | "multi-user"
  apiKey?: string
  accessToken?: string
  allowOffline?: boolean
}

/**
 * Seed authentication config in localStorage before page loads
 * Pattern from login.spec.ts:35-44 and playwright-login.mjs:118-137
 */
export async function seedAuth(
  page: Page,
  overrides: SeedAuthOverrides = {}
): Promise<void> {
  const cfg = {
    serverUrl: overrides.serverUrl || AUTH_CONFIG.serverUrl,
    authMode: overrides.authMode || "single-user",
    apiKey: overrides.apiKey || AUTH_CONFIG.apiKey,
    accessToken: overrides.accessToken || "",
    allowOffline:
      typeof overrides.allowOffline === "boolean"
        ? overrides.allowOffline
        : AUTH_CONFIG.allowOffline
  }

  await page.addInitScript(
    (cfg) => {
      try {
        localStorage.setItem(
          "tldwConfig",
          JSON.stringify({
            serverUrl: cfg.serverUrl,
            authMode: cfg.authMode,
            apiKey: cfg.apiKey,
            accessToken: cfg.accessToken
          })
        )
      } catch {}
      try {
        localStorage.setItem("__tldw_first_run_complete", "true")
      } catch {}
      try {
        if (cfg.allowOffline) {
          localStorage.setItem("__tldw_allow_offline", "true")
        } else {
          localStorage.removeItem("__tldw_allow_offline")
        }
      } catch {}
    },
    cfg
  )
}

/**
 * Seed a deterministic admin fixture profile for smoke tests:
 * - keeps auth in single-user mode
 * - points serverUrl at the running WebUI base URL so Playwright route
 *   intercepts can fully own admin API responses.
 */
export async function seedAdminFixtureProfile(
  page: Page,
  baseURL?: string
): Promise<void> {
  const targetServerUrl =
    (typeof baseURL === "string" && baseURL.length > 0
      ? baseURL
      : process.env.TLDW_WEB_URL) || AUTH_CONFIG.serverUrl

  await seedAuth(page, {
    serverUrl: targetServerUrl,
    authMode: "single-user",
    apiKey: AUTH_CONFIG.apiKey,
    allowOffline: false
  })
}

/**
 * Patterns for console/error messages that are benign and should be ignored
 */
export const BENIGN_PATTERNS = [
  // ResizeObserver warnings are common and harmless
  /ResizeObserver loop/,
  // Non-Error promise rejections (often from cancelled requests)
  /Non-Error promise rejection/,
  // Aborted requests (navigation away, etc.)
  /net::ERR_ABORTED/,
  // Chrome extension errors
  /chrome-extension/,
  // React DevTools
  /Download the React DevTools/,
  // Hot reload messages
  /Fast Refresh/,
  /\[HMR\]/,
  // Favicon not found (common in dev)
  /favicon\.ico.*404/,
  // Source map warnings
  /Failed to load source map/,
  // Ant Design deprecation warnings
  /Warning.*findDOMNode is deprecated/,
  // Next.js hydration warnings that are often false positives
  /Hydration failed/,
  /There was an error while hydrating/
]

/**
 * Temporary allowlist for non-fatal console/request noise observed in full all-pages smoke.
 * These entries are intentionally narrow and route-scoped where possible.
 */
export const SMOKE_HARD_GATE_ALLOWLIST: SmokeHardGateAllowlistRule[] = [
  {
    id: "m5-chat-history-rate-limit",
    scope: "console",
    pattern: /rate_limited\s+\(GET\s+\/api\/v1\/chats\/\?limit=\d+&offset=\d+&ordering=-updated_at\)/i,
    rationale: "Chat history request bursts can hit server-side 429 in dense all-pages sweeps.",
    owner: "WebUI",
    expiresOn: "2026-03-31"
  },
  {
    id: "m5-http-429-resource",
    scope: "console",
    pattern: /Failed to load resource: the server responded with a status of 429/i,
    rationale: "Known rate-limit noise while traversing all routes in parallel; triaged separately.",
    owner: "Platform",
    expiresOn: "2026-03-31"
  },
  {
    id: "m5-react-key-prop-spread-warning",
    scope: "console",
    pattern: /A props object containing a "key" prop is being spread into JSX/i,
    rationale: "Known React warning in connectors/settings surfaces; no runtime crash.",
    owner: "WebUI",
    expiresOn: "2026-03-31",
    routes: ["/connectors", "/connectors/browse", "/connectors/jobs", "/connectors/sources", "/settings", "/config", "/profile", "/privileges"]
  },
  {
    id: "m5-react-non-boolean-attribute-warning",
    scope: "console",
    pattern: /Received `%s` for a non-boolean attribute `%s`/i,
    rationale: "Known non-breaking attribute warning in flashcards render path.",
    owner: "WebUI",
    expiresOn: "2026-03-31",
    routes: ["/flashcards"]
  },
  {
    id: "m5-rc-collapse-children-deprecation",
    scope: "console",
    pattern: /\[rc-collapse\]\s+`children`\s+will be removed/i,
    rationale: "AntD dependency deprecation notice; no user-facing regression in smoke.",
    owner: "WebUI",
    expiresOn: "2026-03-31",
    routes: ["/settings/quick-ingest"]
  },
  {
    id: "m5-media-max-update-depth-warning",
    scope: "console",
    pattern: /Maximum update depth exceeded/i,
    rationale:
      "Known media route warning remains scoped to legacy review/media surfaces; Stage 3 critical audited routes are enforced separately.",
    owner: "WebUI",
    expiresOn: "2026-03-31",
    routes: ["/media", "/media/*", "/media-multi"]
  },
  {
    id: "m5-optional-resource-404-noise",
    scope: "console",
    pattern: /Failed to load resource: the server responded with a status of 404/i,
    rationale: "Known optional static/resource fetch misses in selected routes during dev runtime.",
    owner: "WebUI",
    expiresOn: "2026-03-31",
    routes: ["/review", "/media-multi", "/prompt-studio", "/settings/about", "/__wayfinding-missing-route__"]
  },
  {
    id: "m5-route-boundary-forced-react-overlay-warning",
    scope: "console",
    pattern: /The above error occurred in the <ForcedRouteErrorProbe> component/i,
    rationale: "Expected React error-overlay emission when route boundary fixture intentionally throws.",
    owner: "WebUI",
    expiresOn: "2026-03-31",
    routes: [
      "/admin/server",
      "/admin/llamacpp",
      "/admin/mlx",
      "/content-review",
      "/data-tables",
      "/kanban",
      "/chunking-playground",
      "/moderation-playground",
      "/collections",
      "/world-books",
      "/dictionaries",
      "/characters",
      "/items",
      "/document-workspace",
      "/speech"
    ]
  },
  {
    id: "m5-route-boundary-forced-error-log",
    scope: "console",
    pattern: /\[RouteErrorBoundary:[^\]]+\]\s+Error:\s+Forced route boundary error/i,
    rationale: "Route boundary fixture emits deterministic forced-error log to confirm recovery branch.",
    owner: "WebUI",
    expiresOn: "2026-03-31",
    routes: [
      "/admin/server",
      "/admin/llamacpp",
      "/admin/mlx",
      "/content-review",
      "/data-tables",
      "/kanban",
      "/chunking-playground",
      "/moderation-playground",
      "/collections",
      "/world-books",
      "/dictionaries",
      "/characters",
      "/items",
      "/document-workspace",
      "/speech"
    ]
  },
  {
    id: "m5-admin-optional-endpoint-500",
    scope: "console",
    pattern: /Failed to load resource: the server responded with a status of 500/i,
    rationale: "Admin pages hit optional backend endpoints unavailable in minimal smoke profile.",
    owner: "Platform",
    expiresOn: "2026-03-31",
    routes: ["/admin", "/admin/server", "/admin/orgs", "/admin/data-ops", "/admin/watchlists-items", "/admin/watchlists-runs", "/admin/maintenance"]
  },
  {
    id: "m5-llamacpp-unavailable-503",
    scope: "console",
    pattern: /Failed to load resource: the server responded with a status of 503/i,
    rationale: "Expected when llama.cpp backend is not configured in smoke environment.",
    owner: "Platform",
    expiresOn: "2026-03-31",
    routes: ["/admin/llamacpp"]
  }
]

/**
 * Check if an error/warning message is benign
 */
export function isBenign(text: string): boolean {
  return BENIGN_PATTERNS.some((p) => p.test(text))
}

/**
 * Filter diagnostics to only critical issues
 */
export function getCriticalIssues(diagnostics: DiagnosticsData): {
  pageErrors: Array<{ message: string; stack: string }>
  consoleErrors: Array<{ type: string; text: string }>
  requestFailures: Array<{ url: string; errorText: string }>
} {
  return {
    pageErrors: diagnostics.pageErrors.filter((e) => !isBenign(e.message)),
    consoleErrors: diagnostics.console.filter(
      (c) => c.type === "error" && !isBenign(c.text)
    ),
    requestFailures: diagnostics.requestFailures.filter(
      (r) => !isBenign(r.url) && !isBenign(r.errorText)
    )
  }
}

function findAllowlistRule(
  scope: SmokeAllowlistScope,
  text: string,
  routePath: string
): SmokeHardGateAllowlistRule | null {
  const normalizedRoutePath = normalizeRoutePath(routePath)
  for (const rule of SMOKE_HARD_GATE_ALLOWLIST) {
    if (rule.scope !== scope) continue
    if (
      rule.routes &&
      !rule.routes.some((candidate) => routePatternMatches(candidate, normalizedRoutePath))
    ) {
      continue
    }
    if (rule.pattern.test(text)) {
      return rule
    }
  }
  return null
}

function normalizeRoutePath(routePath: string): string {
  try {
    if (routePath.startsWith("http://") || routePath.startsWith("https://")) {
      return new URL(routePath).pathname
    }
  } catch {}
  return routePath.split("?")[0]?.split("#")[0] || routePath
}

function routePatternMatches(pattern: string, routePath: string): boolean {
  if (pattern.endsWith("*")) {
    const prefix = pattern.slice(0, -1)
    return routePath.startsWith(prefix)
  }
  return pattern === routePath
}

export function classifySmokeIssues(
  routePath: string,
  issues: ReturnType<typeof getCriticalIssues>
): ClassifiedSmokeIssues {
  const classified: ClassifiedSmokeIssues = {
    pageErrors: issues.pageErrors,
    allowlistedConsoleErrors: [],
    unexpectedConsoleErrors: [],
    allowlistedRequestFailures: [],
    unexpectedRequestFailures: []
  }

  for (const entry of issues.consoleErrors) {
    const match = findAllowlistRule("console", entry.text, routePath)
    if (match) {
      classified.allowlistedConsoleErrors.push({ entry, rule: match })
    } else {
      classified.unexpectedConsoleErrors.push(entry)
    }
  }

  for (const entry of issues.requestFailures) {
    const requestText = `${entry.url} (${entry.errorText})`
    const match = findAllowlistRule("request", requestText, routePath)
    if (match) {
      classified.allowlistedRequestFailures.push({ entry, rule: match })
    } else {
      classified.unexpectedRequestFailures.push(entry)
    }
  }

  return classified
}
