import fs from "node:fs"
import path from "node:path"
import type { Page } from "@playwright/test"
import {
  test,
  expect,
  assertNoCriticalErrors,
  skipIfServerUnavailable,
} from "../utils/fixtures"
import { TEST_CONFIG, waitForConnection } from "../utils/helpers"

type ViewportTarget = {
  label: "desktop" | "mobile"
  width: number
  height: number
}

type OnboardingEvidenceStep = {
  viewport: ViewportTarget["label"]
  step: string
  screenshot: string
  note: string
}

function sanitizeEvidenceTag(rawTag: string): string {
  const normalized = rawTag.trim().replace(/[^a-zA-Z0-9._-]/g, "_")
  return normalized.length > 0 ? normalized : "local"
}

function defaultEvidenceTag(): string {
  return new Date().toISOString().slice(0, 10).replace(/-/g, "_")
}

function formatEvidenceDate(tag: string): string | null {
  return /^\d{4}_\d{2}_\d{2}$/.test(tag) ? tag.split("_").join("-") : null
}

const EVIDENCE_TAG = sanitizeEvidenceTag(
  process.env.TLDW_ONBOARDING_EVIDENCE_TAG || defaultEvidenceTag()
)
const EVIDENCE_DIR = path.resolve(
  process.cwd(),
  `../../Docs/Product/WebUI/evidence/m4_3_onboarding_${EVIDENCE_TAG}`
)

const VIEWPORTS: ViewportTarget[] = [
  { label: "desktop", width: 1440, height: 900 },
  { label: "mobile", width: 375, height: 812 },
]

function ensureEvidenceDirectory(): void {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true })
}

function writeViewportEvidence(
  viewport: ViewportTarget["label"],
  rows: OnboardingEvidenceStep[]
): void {
  fs.writeFileSync(
    path.join(EVIDENCE_DIR, `${viewport}-onboarding-results.json`),
    `${JSON.stringify(rows, null, 2)}\n`,
    "utf8"
  )
}

function readViewportEvidence(
  viewport: ViewportTarget["label"]
): OnboardingEvidenceStep[] {
  const filePath = path.join(EVIDENCE_DIR, `${viewport}-onboarding-results.json`)
  if (!fs.existsSync(filePath)) return []
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8")) as OnboardingEvidenceStep[]
  } catch {
    return []
  }
}

function toMarkdownRows(rows: OnboardingEvidenceStep[]): string {
  return rows
    .map(
      (row) =>
        `| ${row.viewport} | ${row.step} | \`${row.screenshot}\` | ${row.note} |`
    )
    .join("\n")
}

function writeEvidenceReadme(): void {
  const desktopRows = readViewportEvidence("desktop")
  const mobileRows = readViewportEvidence("mobile")
  const evidenceDate = formatEvidenceDate(EVIDENCE_TAG)
  const markdown = [
    "# M4.3 Onboarding Ingestion-First Evidence",
    "",
    `Evidence Tag: ${EVIDENCE_TAG}`,
    evidenceDate ? `Date: ${evidenceDate}` : null,
    "",
    "## Desktop (1440x900)",
    "",
    "| Viewport | Step | Screenshot | Notes |",
    "|---|---|---|---|",
    toMarkdownRows(desktopRows),
    "",
    "## Mobile (375x812)",
    "",
    "| Viewport | Step | Screenshot | Notes |",
    "|---|---|---|---|",
    toMarkdownRows(mobileRows),
    "",
  ]
    .filter((line): line is string => line !== null)
    .join("\n")
  fs.writeFileSync(path.join(EVIDENCE_DIR, "README.md"), markdown, "utf8")
}

async function captureStep(
  page: Page,
  rows: OnboardingEvidenceStep[],
  viewport: ViewportTarget["label"],
  step: string,
  note: string
) {
  const screenshot = `${viewport}-${step}.png`
  await page.screenshot({
    path: path.join(EVIDENCE_DIR, screenshot),
    fullPage: true,
  })
  rows.push({
    viewport,
    step,
    screenshot,
    note,
  })
}

async function assertCardOrder(page: Page) {
  const ingest = page.getByTestId("onboarding-success-ingest")
  const media = page.getByTestId("onboarding-success-media")
  const chat = page.getByTestId("onboarding-success-chat")
  const [ingestBox, mediaBox, chatBox] = await Promise.all([
    ingest.boundingBox(),
    media.boundingBox(),
    chat.boundingBox(),
  ])
  expect(ingestBox).toBeTruthy()
  expect(mediaBox).toBeTruthy()
  expect(chatBox).toBeTruthy()
  expect((ingestBox?.y ?? 0) < (mediaBox?.y ?? 0)).toBeTruthy()
  expect((mediaBox?.y ?? 0) < (chatBox?.y ?? 0)).toBeTruthy()
}

async function openOnboardingSuccessScreen(
  page: Page
): Promise<"connected-now" | "already-connected"> {
  await page.goto("/setup", { waitUntil: "domcontentloaded" })

  const connect = page.getByTestId("onboarding-connect")
  const success = page.getByTestId("onboarding-success-screen")

  await Promise.race([
    connect.waitFor({ state: "visible", timeout: 15_000 }),
    success.waitFor({ state: "visible", timeout: 15_000 }),
  ])

  const needsConnect = await connect.isVisible().catch(() => false)
  if (needsConnect) {
    await connect.click()
  }

  await expect(success).toBeVisible({ timeout: 20_000 })
  return needsConnect ? "connected-now" : "already-connected"
}

async function clickOnboardingCtaAndExpectRoute(
  page: Page,
  ctaTestId: string,
  expectedUrl: RegExp
): Promise<void> {
  const cta = page.getByTestId(ctaTestId)
  let lastError: unknown

  for (let attempt = 0; attempt < 2; attempt += 1) {
    await expect(cta).toBeVisible({ timeout: 15_000 })
    await cta.click()
    try {
      await expect(page).toHaveURL(expectedUrl, { timeout: 10_000 })
      return
    } catch (error) {
      lastError = error
    }
  }

  throw lastError
}

test.describe("Onboarding Ingestion-First Journey", () => {
  test.beforeEach(async ({ authedPage }) => {
    ensureEvidenceDirectory()
    await authedPage.addInitScript((cfg) => {
      try {
        localStorage.setItem("ff_newOnboarding", JSON.stringify(true))
      } catch {}
      try {
        localStorage.setItem(
          "tldwConfig",
          JSON.stringify({
            serverUrl: cfg.serverUrl,
            authMode: "single-user",
            apiKey: cfg.apiKey,
          })
        )
      } catch {}
      try {
        localStorage.removeItem("__tldw_first_run_complete")
      } catch {}
    }, TEST_CONFIG)
  })

  for (const viewport of VIEWPORTS) {
    test(`connects then guides ingest -> verify -> chat (${viewport.label})`, async ({
      authedPage,
      serverInfo,
      diagnostics,
    }) => {
      skipIfServerUnavailable(serverInfo)
      const evidenceRows: OnboardingEvidenceStep[] = []

      await authedPage.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      })

      const initialConnectState = await openOnboardingSuccessScreen(authedPage)
      await ensureOnboardingSuccessScreen(authedPage)
      await captureStep(
        authedPage,
        evidenceRows,
        viewport.label,
        "01-setup-connect",
        initialConnectState === "connected-now"
          ? "Connected via onboarding from setup."
          : "Onboarding success already visible from prior connected state."
      )

      await expect(authedPage.getByTestId("onboarding-success-screen")).toHaveAttribute(
        "data-ingest-status",
        "idle"
      )
      await expect(authedPage.getByTestId("onboarding-ingest-status")).toContainText(
        "Start"
      )
      await expect(authedPage.getByTestId("onboarding-success-ingest")).toBeVisible()
      await expect(authedPage.getByTestId("onboarding-success-media")).toBeVisible()
      await expect(authedPage.getByTestId("onboarding-success-chat")).toBeVisible()
      await assertCardOrder(authedPage)
      await captureStep(
        authedPage,
        evidenceRows,
        viewport.label,
        "02-success-idle",
        "Idle onboarding recommendation state with CTA ordering."
      )

      await authedPage.evaluate(() => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const store = (window as any).__tldw_useQuickIngestStore
        store?.getState?.().recordRunSuccess({
          totalCount: 1,
          successCount: 1,
          failedCount: 0,
          firstMediaId: "m4-e2e-media-id",
          primarySourceLabel: "https://example.com/m4-e2e"
        })
      })
      await expect(authedPage.getByTestId("onboarding-success-screen")).toHaveAttribute(
        "data-ingest-status",
        "success"
      )
      await expect(authedPage.getByTestId("onboarding-ingest-status")).toContainText(
        "Completed"
      )
      await expect(authedPage.getByTestId("onboarding-success-media")).toContainText(
        "successful item"
      )
      await assertCardOrder(authedPage)
      await captureStep(
        authedPage,
        evidenceRows,
        viewport.label,
        "03-success-post-ingest",
        "Post-ingest recommendation state prioritizes media verification."
      )

      await clickOnboardingCtaAndExpectRoute(
        authedPage,
        "onboarding-success-media",
        /\/media(?:[/?#].*)?$/
      )
      await captureStep(
        authedPage,
        evidenceRows,
        viewport.label,
        "04-media-route",
        "Media verification route reached from onboarding CTA."
      )

      await openOnboardingSuccessScreen(authedPage)
      await ensureOnboardingSuccessScreen(authedPage)

      await authedPage
        .getByTestId("onboarding-success-ingest")
        .evaluate((el: HTMLElement) => el.click())
      const quickIngestDialog = authedPage
        .getByRole("dialog", { name: /quick ingest/i })
        .first()
      await expect(quickIngestDialog).toBeVisible({ timeout: 15_000 })
      await captureStep(
        authedPage,
        evidenceRows,
        viewport.label,
        "05-quick-ingest-modal",
        "Quick Ingest modal reachable from onboarding ingest CTA."
      )

      const quickIngestClose = quickIngestDialog
        .locator(".ant-modal-close")
        .first()
      if (await quickIngestClose.isVisible().catch(() => false)) {
        await quickIngestClose.evaluate((el: HTMLElement) => el.click())
      } else {
        await authedPage.keyboard.press("Escape")
      }
      await expect(quickIngestDialog).toBeHidden({ timeout: 10_000 })

      await ensureOnboardingSuccessScreen(authedPage)

      await authedPage.evaluate(() => {
        try {
          localStorage.setItem("__tldw_first_run_complete", "true")
        } catch {
          // Non-blocking; CTA should still handle completion in-app.
        }
      })

      await authedPage
        .getByTestId("onboarding-success-chat")
        .evaluate((el: HTMLElement) => el.click())
      await expect(authedPage).toHaveURL(/\/chat(?:[/?#].*)?$/, {
        timeout: 20_000,
      })
      await expect(authedPage.getByTestId("chat-input")).toBeVisible({
        timeout: 15_000,
      })
      await captureStep(
        authedPage,
        evidenceRows,
        viewport.label,
        "06-chat-route",
        "Chat route reached from onboarding CTA."
      )

      writeViewportEvidence(viewport.label, evidenceRows)
      writeEvidenceReadme()
      await assertNoCriticalErrors(diagnostics)
    })
  }
})
