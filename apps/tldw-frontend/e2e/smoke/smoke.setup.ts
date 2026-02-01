import { test as base, expect, Page } from "@playwright/test"

/**
 * Diagnostics data collected during page visits
 */
export interface DiagnosticsData {
  console: Array<{ type: string; text: string; location?: { url: string; lineNumber: number } }>
  pageErrors: Array<{ message: string; stack: string }>
  requestFailures: Array<{ url: string; errorText: string }>
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

/**
 * Seed authentication config in localStorage before page loads
 * Pattern from login.spec.ts:35-44 and playwright-login.mjs:118-137
 */
export async function seedAuth(page: Page): Promise<void> {
  await page.addInitScript(
    (cfg) => {
      try {
        localStorage.setItem(
          "tldwConfig",
          JSON.stringify({
            serverUrl: cfg.serverUrl,
            authMode: "single-user",
            apiKey: cfg.apiKey
          })
        )
      } catch {}
      try {
        localStorage.setItem("__tldw_first_run_complete", "true")
      } catch {}
      try {
        if (cfg.allowOffline) {
          localStorage.setItem("__tldw_allow_offline", "true")
        }
      } catch {}
    },
    AUTH_CONFIG
  )
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
