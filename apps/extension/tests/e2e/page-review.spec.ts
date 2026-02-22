import { test, expect, type Page, type BrowserContext } from "@playwright/test"
import { launchWithExtensionOrSkip } from "./utils/real-server"
import path from "node:path"
import fs from "node:fs"

import { launchWithExtension } from "./utils/extension"
import { OPTION_ROUTES, SIDEPANEL_ROUTES } from "./page-inventory"

const EXT_PATH = path.resolve("build/chrome-mv3")
const LOAD_TIMEOUT = 30_000
const ELEMENT_TIMEOUT = 15_000
const BOOTSTRAP_TIMEOUT = 120_000
const CAPTURE = process.env.TLDW_PAGE_REVIEW_CAPTURE === "1"
const STRICT_CONSOLE = process.env.TLDW_PAGE_REVIEW_STRICT === "1"
const ARTIFACTS_DIR = path.resolve("playwright-mcp-artifacts/extension-page-review")

const BENIGN_PATTERNS = [
  /ResizeObserver loop/i,
  /Non-Error promise rejection/i,
  /net::ERR_ABORTED/i,
  /chrome-extension/i,
  /Failed to load resource/i,
  /favicon\.ico.*404/i,
  /Executing inline script violates the following Content Security Policy directive/i,
  /Refused to execute inline script/i,
  /Content Security Policy directive/i
]

const isBenign = (text: string) => BENIGN_PATTERNS.some((p) => p.test(text))

type Diagnostics = {
  pageErrors: Array<{ message: string; stack?: string }>
  consoleErrors: Array<{ text: string }>
  requestFailures: Array<{ url: string; errorText: string }>
}

const createDiagnostics = (page: Page) => {
  const data: Diagnostics = {
    pageErrors: [],
    consoleErrors: [],
    requestFailures: []
  }

  page.on("pageerror", (err) => {
    data.pageErrors.push({ message: err.message, stack: err.stack })
  })

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      data.consoleErrors.push({ text: msg.text() })
    }
  })

  page.on("requestfailed", (req) => {
    data.requestFailures.push({
      url: req.url(),
      errorText: req.failure()?.errorText || ""
    })
  })

  return {
    data,
    reset() {
      data.pageErrors.length = 0
      data.consoleErrors.length = 0
      data.requestFailures.length = 0
    },
    critical() {
      return {
        pageErrors: data.pageErrors.filter((e) => !isBenign(e.message)),
        consoleErrors: data.consoleErrors.filter((e) => !isBenign(e.text)),
        requestFailures: data.requestFailures.filter(
          (e) => !isBenign(e.url) && !isBenign(e.errorText)
        )
      }
    }
  }
}

const slugify = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")

const buildUrl = (base: string, routePath: string) => {
  const normalized = routePath.startsWith("/") ? routePath : `/${routePath}`
  return `${base}#${normalized}`
}

test.describe("Extension page review", () => {
  test.describe.configure({ mode: "serial", timeout: BOOTSTRAP_TIMEOUT })

  let context: BrowserContext
  let optionsUrl = ""
  let sidepanelUrl = ""

  const visitRoute = async (
    page: Page,
    diagnostics: ReturnType<typeof createDiagnostics>,
    baseUrl: string,
    label: string,
    routePath: string
  ) => {
    diagnostics.reset()
    const url = buildUrl(baseUrl, routePath)
    const response = await page.goto(url, {
      waitUntil: "domcontentloaded",
      timeout: LOAD_TIMEOUT
    })

    await page.waitForLoadState("networkidle", { timeout: LOAD_TIMEOUT }).catch(() => {})
    await page.waitForSelector("#root", { timeout: ELEMENT_TIMEOUT }).catch(() => {})
    await page.waitForTimeout(250)

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

    if (routePath === "/persona") {
      await expect(
        page.getByTestId("persona-route-root"),
        "Persona route marker should render on /persona"
      ).toBeVisible({ timeout: ELEMENT_TIMEOUT })
    }

    if (CAPTURE) {
      const slug = slugify(routePath === "/" ? "root" : routePath)
      const fileName = `${label}-${slug || "root"}.png`
      await page.screenshot({
        path: path.join(ARTIFACTS_DIR, fileName),
        fullPage: true
      })
    }

    const issues = diagnostics.critical()
    if (issues.consoleErrors.length && !STRICT_CONSOLE) {
      console.log(
        `[extension page review] console errors on ${routePath}:`,
        issues.consoleErrors.map((e) => e.text)
      )
    }

    expect(
      errorBoundaryVisible,
      `Error boundary visible on ${routePath}`
    ).toBeFalsy()
    expect(
      errorTextVisible,
      `"Something went wrong" visible on ${routePath}`
    ).toBeFalsy()
    expect(
      issues.pageErrors,
      `Page errors on ${routePath}: ${issues.pageErrors
        .map((e) => e.message)
        .join(", ")}`
    ).toHaveLength(0)

    if (STRICT_CONSOLE) {
      expect(
        issues.consoleErrors,
        `Console errors on ${routePath}`
      ).toHaveLength(0)
    }

    const status = response?.status()
    if (status && status >= 400 && status !== 404) {
      console.warn(`[extension page review] HTTP ${status} for ${routePath}`)
    }
  }

  test.beforeAll(async ({}, testInfo) => {
    testInfo.setTimeout(BOOTSTRAP_TIMEOUT)
    const launch = await launchWithExtensionOrSkip(test, EXT_PATH, {
      seedConfig: {
        __tldw_first_run_complete: true,
        __tldw_allow_offline: true
      }
    })
    context = launch.context
    optionsUrl = launch.optionsUrl
    sidepanelUrl = launch.sidepanelUrl
    await launch.page.close()

    if (CAPTURE) {
      fs.mkdirSync(ARTIFACTS_DIR, { recursive: true })
    }
  })

  test.afterAll(async () => {
    await context?.close()
  })

  for (const route of OPTION_ROUTES) {
    test(`options ${route.path}`, async () => {
      const page = await context.newPage()
      const diagnostics = createDiagnostics(page)
      await visitRoute(page, diagnostics, optionsUrl, "options", route.path)
      await page.close()
    })
  }

  for (const route of SIDEPANEL_ROUTES) {
    test(`sidepanel ${route.path}`, async () => {
      const page = await context.newPage()
      const diagnostics = createDiagnostics(page)
      await visitRoute(page, diagnostics, sidepanelUrl, "sidepanel", route.path)
      await page.close()
    })
  }
})
