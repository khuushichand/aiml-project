import * as fs from "fs"
import * as path from "path"

import type { Page } from "@playwright/test"
import { dismissModals, fetchWithApiKey, waitForConnection } from "../utils/helpers"
import {
  classifySmokeIssues,
  getCriticalIssues,
  test,
  expect,
  seedAuth,
  type DiagnosticsData
} from "../smoke/smoke.setup"

const AUDIT_ROOT = path.resolve(__dirname, "../../output/playwright/presentation-studio-ux-audit")
const SCREENSHOTS_DIR = path.join(AUDIT_ROOT, "screenshots")
const DATA_DIR = path.join(AUDIT_ROOT, "data")

type ViewportConfig = {
  key: "desktop" | "mobile"
  width: number
  height: number
}

type PresentationStudioAuditData = {
  route: string
  finalUrl: string
  redirected: boolean
  httpStatus: number | null
  timestamp: string
  newFlow: {
    succeeded: boolean
    finalUrl: string
    screenshot: string | null
    visibleText: string | null
  }
  detailFlow: {
    editorVisible: boolean
    finalUrl: string
    screenshot: string | null
    visibleText: string | null
    lastRequestError: string | null
    requestErrors: string | null
  }
  screenshots: Record<string, string>
  diagnostics: {
    pageErrors: DiagnosticsData["pageErrors"]
    unexpectedConsoleErrors: ReturnType<typeof classifySmokeIssues>["unexpectedConsoleErrors"]
    unexpectedRequestFailures: ReturnType<typeof classifySmokeIssues>["unexpectedRequestFailures"]
    allowlistedConsoleErrors: Array<{ text: string; ruleId: string }>
    allowlistedRequestFailures: Array<{ url: string; ruleId: string }>
  }
  performance: {
    domContentLoaded: number | null
    firstContentfulPaint: number | null
    resourceCount: number
  }
  accessibility: {
    headingStructure: string[]
    landmarkCount: number
    imagesWithoutAlt: number
    focusableElements: number
  }
  uiSnapshot: {
    slideCount: number
    slideTitles: string[]
    selectedSlideTitle: string | null
    buttonLabels: string[]
    fieldLabels: string[]
    statusSummary: string[]
    horizontalOverflow: Record<string, boolean>
    overflowOffenders: Record<string, string[]>
  }
}

const VIEWPORTS: ViewportConfig[] = [
  { key: "desktop", width: 1440, height: 900 },
  { key: "mobile", width: 390, height: 844 }
]

fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true })
fs.mkdirSync(DATA_DIR, { recursive: true })

const setLightMode = async (page: Page) => {
  await page.evaluate(() => {
    document.documentElement.classList.remove("dark")
    document.documentElement.classList.add("light")
  })
}

const captureViewportState = async (
  page: Page,
  viewport: ViewportConfig
): Promise<{
  screenshot: string
  hasHorizontalOverflow: boolean
  overflowOffenders: string[]
}> => {
  await page.setViewportSize({ width: viewport.width, height: viewport.height })
  await setLightMode(page)
  await page.waitForTimeout(500)

  const screenshotName = `presentation-studio-${viewport.key}.png`
  const screenshotPath = path.join(SCREENSHOTS_DIR, screenshotName)
  await page.screenshot({ path: screenshotPath, fullPage: true })

  const { hasHorizontalOverflow, overflowOffenders } = await page.evaluate(() => {
    const scrollingRoot = document.scrollingElement || document.documentElement
    const offenders = Array.from(document.querySelectorAll("body *"))
      .map((element) => {
        const rect = element.getBoundingClientRect()
        if (rect.right <= window.innerWidth + 1 && rect.left >= -1) {
          return null
        }
        const htmlElement = element as HTMLElement
        const className =
          typeof htmlElement.className === "string" ? htmlElement.className.trim() : ""
        const testId = htmlElement.dataset?.testid

        return `${htmlElement.tagName.toLowerCase()}${testId ? `[data-testid="${testId}"]` : ""}${className ? `.${className.replace(/\s+/g, ".")}` : ""} (${Math.round(rect.left)}-${Math.round(rect.right)})`
      })
      .filter(Boolean)
      .slice(0, 10) as string[]

    return {
      hasHorizontalOverflow: scrollingRoot.scrollWidth > window.innerWidth + 1,
      overflowOffenders: offenders
    }
  })

  return {
    screenshot: screenshotName,
    hasHorizontalOverflow,
    overflowOffenders
  }
}

const collectSnapshot = async (page: Page) =>
  page.evaluate(() => {
    const slideButtons = Array.from(
      document.querySelectorAll("[data-testid='presentation-studio-slide-card']")
    )
    const slideTitles = slideButtons
      .map((button) => button.textContent?.trim() || "")
      .filter(Boolean)
    const selectedSlideTitle =
      document.querySelector(
        "[data-testid='presentation-studio-slide-card'].border-slate-900 .mt-3.text-sm.font-semibold"
      )
        ?.textContent
        ?.trim() || null
    const buttonLabels = Array.from(document.querySelectorAll("button"))
      .map((button) => button.textContent?.trim() || "")
      .filter(Boolean)
    const fieldLabels = Array.from(document.querySelectorAll("label"))
      .map((label) => label.textContent?.trim() || "")
      .filter(Boolean)
    const statusSummary = Array.from(
      document.querySelectorAll("[data-testid='presentation-studio-media-rail'] dt, [data-testid='presentation-studio-media-rail'] dd")
    )
      .map((node) => node.textContent?.trim() || "")
      .filter(Boolean)

    return {
      slideCount: slideTitles.length,
      slideTitles,
      selectedSlideTitle,
      buttonLabels,
      fieldLabels,
      statusSummary
    }
  })

const writeAuditData = (data: PresentationStudioAuditData) => {
  fs.writeFileSync(
    path.join(DATA_DIR, "presentation-studio.json"),
    `${JSON.stringify(data, null, 2)}\n`,
    "utf8"
  )
}

const createSeedProject = async () => {
  const serverUrl = process.env.TLDW_SERVER_URL || "http://127.0.0.1:8000"
  const apiKey = process.env.TLDW_API_KEY || "THIS-IS-A-SECURE-KEY-123-FAKE-KEY"
  const uniqueId = Date.now()
  const response = await fetchWithApiKey(`${serverUrl}/api/v1/slides/presentations`, apiKey, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      title: `Presentation Studio Audit ${uniqueId}`,
      description: null,
      theme: "black",
      studio_data: {
        origin: "blank",
        entry_surface: "playwright_audit"
      },
      slides: [
        {
          order: 0,
          layout: "title",
          title: "Title slide",
          content: "",
          speaker_notes: "",
          metadata: {
            studio: {
              slideId: `audit-slide-${uniqueId}`,
              audio: { status: "missing" },
              image: { status: "missing" }
            }
          }
        }
      ]
    })
  })

  if (!response.ok) {
    throw new Error(`seed_project_failed_${response.status}`)
  }

  return (await response.json()) as { id: string }
}

test.describe("Presentation Studio UX Audit", () => {
  test("captures Presentation Studio creation flow for heuristic review", async ({
    page,
    diagnostics
  }) => {
    test.setTimeout(120_000)

    await seedAuth(page)

    const response = await page.goto("/presentation-studio/new", {
      waitUntil: "domcontentloaded",
      timeout: 30_000
    })
    await waitForConnection(page, 30_000)

    let newFlowSucceeded = false
    try {
      await page.waitForFunction(
        () => {
          const pathname = window.location.pathname
          return /^\/presentation-studio\/[^/]+$/.test(pathname) && pathname !== "/presentation-studio/new"
        },
        undefined,
        { timeout: 20_000 }
      )
      newFlowSucceeded = true
    } catch {
      newFlowSucceeded = false
    }

    let newFlowScreenshot: string | null = null
    let newFlowVisibleText: string | null = null
    if (!newFlowSucceeded) {
      newFlowScreenshot = "presentation-studio-new-flow-stuck.png"
      await setLightMode(page)
      await page.screenshot({
        path: path.join(SCREENSHOTS_DIR, newFlowScreenshot),
        fullPage: true
      })
      newFlowVisibleText = await page.locator("main").textContent()

      const seededProject = await createSeedProject()
      await page.goto(`/presentation-studio/${seededProject.id}`, {
        waitUntil: "domcontentloaded",
        timeout: 30_000
      })
    }

    await dismissModals(page)
    await page.waitForTimeout(1500)

    const slideRail = page.getByTestId("presentation-studio-slide-rail")
    let editorVisible = false
    try {
      await slideRail.waitFor({ state: "visible", timeout: 15_000 })
      editorVisible = true
    } catch {
      editorVisible = false
    }

    let detailFlowScreenshot: string | null = null
    let detailFlowVisibleText: string | null = null
    if (editorVisible) {
      await expect(page.getByTestId("presentation-studio-slide-editor")).toBeVisible()
      await expect(page.getByTestId("presentation-studio-media-rail")).toBeVisible()

      await page.getByRole("button", { name: "Add slide" }).click()
      await expect(page.getByTestId("presentation-studio-slide-card")).toHaveCount(2)

      await page.getByLabel("Slide title").fill("Problem framing")
      await page
        .getByLabel("Slide content")
        .fill("Summarize the core problem, constraints, and target audience.")
      await page
        .getByLabel("Narration script")
        .fill("Open with the core problem, then explain who the presentation is for.")
      await page.getByLabel("Transition").selectOption("wipe")
      await page.getByLabel("Duration mode").selectOption("manual")
      await page.getByLabel("Manual duration (seconds)").fill("45")

      await expect(page.getByTestId("presentation-studio-media-rail")).toContainText("Wipe")
      await expect(page.getByTestId("presentation-studio-media-rail")).toContainText(
        "Effective duration"
      )
      await expect(page.getByTestId("presentation-studio-media-rail")).toContainText("45s")

      const firstHandle = page.getByTestId("presentation-studio-slide-handle").nth(0)
      const secondCard = page.getByTestId("presentation-studio-slide-card").nth(1)
      const firstHandleBox = await firstHandle.boundingBox()
      const secondCardBox = await secondCard.boundingBox()

      if (firstHandleBox && secondCardBox) {
        await page.mouse.move(
          firstHandleBox.x + firstHandleBox.width / 2,
          firstHandleBox.y + firstHandleBox.height / 2
        )
        await page.mouse.down()
        await page.mouse.move(
          secondCardBox.x + secondCardBox.width / 2,
          secondCardBox.y + secondCardBox.height / 2,
          { steps: 12 }
        )
        await page.mouse.up()
      }

      await expect(page.getByTestId("presentation-studio-slide-card").nth(0)).toContainText(
        "Problem framing"
      )

      await page.waitForTimeout(1800)
    } else {
      detailFlowScreenshot = "presentation-studio-detail-loading.png"
      await setLightMode(page)
      await page.screenshot({
        path: path.join(SCREENSHOTS_DIR, detailFlowScreenshot),
        fullPage: true
      })
      detailFlowVisibleText = await page.locator("main").textContent()
    }

    const requestErrorState = await page.evaluate(() => ({
      lastRequestError: localStorage.getItem("__tldwLastRequestError"),
      requestErrors: localStorage.getItem("__tldwRequestErrors")
    }))

    const screenshots: Record<string, string> = {}
    const overflowByViewport: Record<string, boolean> = {}
    const overflowOffenders: Record<string, string[]> = {}
    for (const viewport of VIEWPORTS) {
      const artifact = await captureViewportState(page, viewport)
      screenshots[viewport.key] = artifact.screenshot
      overflowByViewport[viewport.key] = artifact.hasHorizontalOverflow
      overflowOffenders[viewport.key] = artifact.overflowOffenders
    }

    const criticalIssues = getCriticalIssues(diagnostics)
    const classified = classifySmokeIssues("/presentation-studio/[projectId]", criticalIssues)

    const performance = await page.evaluate(() => {
      const navigation = performance.getEntriesByType("navigation")[0] as
        | PerformanceNavigationTiming
        | undefined
      const paint = performance.getEntriesByType("paint")
      const fcp = paint.find((entry) => entry.name === "first-contentful-paint")
      return {
        domContentLoaded: navigation?.domContentLoadedEventEnd ?? null,
        firstContentfulPaint: fcp?.startTime ?? null,
        resourceCount: performance.getEntriesByType("resource").length
      }
    })

    const accessibility = await page.evaluate(() => ({
      headingStructure: Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, h6")).map(
        (heading) => heading.tagName.toLowerCase()
      ),
      landmarkCount: document.querySelectorAll(
        "main, nav, header, footer, aside, [role='main'], [role='navigation'], [role='banner'], [role='contentinfo'], [role='complementary']"
      ).length,
      imagesWithoutAlt: document.querySelectorAll("img:not([alt])").length,
      focusableElements: document.querySelectorAll(
        "a[href], button, input, select, textarea, [tabindex]:not([tabindex='-1'])"
      ).length
    }))

    const snapshot = await collectSnapshot(page)

    writeAuditData({
      route: "/presentation-studio/new",
      finalUrl: page.url(),
      redirected: page.url().includes("/presentation-studio/") && !page.url().endsWith("/new"),
      httpStatus: response?.status() ?? null,
      timestamp: new Date().toISOString(),
      newFlow: {
        succeeded: newFlowSucceeded,
        finalUrl: newFlowSucceeded ? page.url() : page.url(),
        screenshot: newFlowScreenshot,
        visibleText: newFlowVisibleText
      },
      detailFlow: {
        editorVisible,
        finalUrl: page.url(),
        screenshot: detailFlowScreenshot,
        visibleText: detailFlowVisibleText,
        lastRequestError: requestErrorState.lastRequestError,
        requestErrors: requestErrorState.requestErrors
      },
      screenshots,
      diagnostics: {
        pageErrors: classified.pageErrors,
        unexpectedConsoleErrors: classified.unexpectedConsoleErrors,
        unexpectedRequestFailures: classified.unexpectedRequestFailures,
        allowlistedConsoleErrors: classified.allowlistedConsoleErrors.map((entry) => ({
          text: entry.entry.text,
          ruleId: entry.rule.id
        })),
        allowlistedRequestFailures: classified.allowlistedRequestFailures.map((entry) => ({
          url: entry.entry.url,
          ruleId: entry.rule.id
        }))
      },
      performance,
      accessibility,
      uiSnapshot: {
        ...snapshot,
        horizontalOverflow: overflowByViewport,
        overflowOffenders
      }
    })
  })
})
