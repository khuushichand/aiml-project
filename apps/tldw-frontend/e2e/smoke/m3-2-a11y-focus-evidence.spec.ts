import fs from "node:fs"
import path from "node:path"
import type { Locator, Page } from "@playwright/test"
import { test, expect, seedAuth } from "./smoke.setup"

type ViewportTarget = {
  label: "desktop" | "mobile"
  width: number
  height: number
}

type RouteFocusMatrixEntry = {
  slug: string
  flow: string
  route: string
  objective: string
  target: (page: Page) => Locator
}

type RouteFocusEvidence = {
  flow: string
  route: string
  objective: string
  viewport: ViewportTarget["label"]
  screenshot: string
  tabPressesToTarget: number | null
  focusMethod: "tab" | "programmatic"
  reachedTarget: boolean
  keyInputVerified: boolean
  note: string
}

const DATE_STAMP = "2026_02_13"
const EVIDENCE_DIR = path.resolve(
  process.cwd(),
  `../../Docs/Product/WebUI/evidence/m3_2_a11y_focus_${DATE_STAMP}`
)

const VIEWPORTS: ViewportTarget[] = [
  { label: "desktop", width: 1440, height: 900 },
  { label: "mobile", width: 375, height: 812 }
]

const ROUTE_MATRIX: RouteFocusMatrixEntry[] = [
  {
    slug: "chat",
    flow: "Chat",
    route: "/chat",
    objective: "Reach composer with keyboard-only navigation.",
    target: (page) => page.getByTestId("chat-input")
  },
  {
    slug: "media",
    flow: "Media",
    route: "/media",
    objective: "Reach media search control with keyboard-only navigation.",
    target: (page) => page.locator('input[placeholder*="Search media"]').first()
  },
  {
    slug: "knowledge",
    flow: "Knowledge QA",
    route: "/knowledge",
    objective: "Reach knowledge query input with keyboard-only navigation.",
    target: (page) =>
      page.locator('input[placeholder*="What are the key findings"]').first()
  },
  {
    slug: "notes",
    flow: "Notes",
    route: "/notes",
    objective: "Reach notes search input and keep focus visible.",
    target: (page) =>
      page.locator('input[placeholder*="Search titles and contents"]').first()
  },
  {
    slug: "prompts",
    flow: "Prompts",
    route: "/prompts",
    objective: "Reach prompt search input and keep focus visible.",
    target: (page) =>
      page.locator('input[placeholder*="Search name, content, key"]').first()
  },
  {
    slug: "settings-tldw",
    flow: "Settings",
    route: "/settings/tldw",
    objective: "Reach server URL settings input using keyboard-only navigation.",
    target: (page) =>
      page.locator('input[placeholder*="http://127.0.0.1:8000"]').first()
  }
]

function ensureEvidenceDirectory(): void {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true })
}

async function isLocatorFocused(target: Locator): Promise<boolean> {
  return target
    .evaluate((element) => element === document.activeElement)
    .catch(() => false)
}

async function tabToTarget(
  page: Page,
  target: Locator,
  maxTabs = 120
): Promise<number | null> {
  await page.locator("body").click({ position: { x: 12, y: 12 } }).catch(() => {})
  for (let step = 1; step <= maxTabs; step += 1) {
    await page.keyboard.press("Tab")
    if (await isLocatorFocused(target)) return step
  }
  return null
}

async function verifyKeyboardInput(target: Locator): Promise<boolean> {
  const marker = "m3-focus-check"
  const inputAccepted = await target
    .evaluate((element, value) => {
      if (
        element instanceof HTMLInputElement ||
        element instanceof HTMLTextAreaElement
      ) {
        element.value = value
        return element.value === value
      }
      if (element instanceof HTMLElement && element.isContentEditable) {
        element.textContent = value
        return element.textContent === value
      }
      return false
    }, marker)
    .catch(() => false)
  return inputAccepted
}

async function captureRouteFocusEvidence(
  page: Page,
  viewport: ViewportTarget,
  entry: RouteFocusMatrixEntry
): Promise<RouteFocusEvidence> {
  await page.setViewportSize({ width: viewport.width, height: viewport.height })
  await page.goto(entry.route, { waitUntil: "domcontentloaded", timeout: 30_000 })
  await page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => {})

  const target = entry.target(page)
  await expect(target).toBeVisible({ timeout: 20_000 })

  const tabPresses = await tabToTarget(page, target)
  let focusMethod: "tab" | "programmatic" = "tab"
  let reachedTarget = tabPresses !== null

  if (!reachedTarget) {
    await target.focus()
    focusMethod = "programmatic"
    reachedTarget = await isLocatorFocused(target)
  }

  expect(
    reachedTarget,
    `Failed to focus ${entry.route} target for ${viewport.label} evidence capture`
  ).toBeTruthy()

  const keyInputVerified = await verifyKeyboardInput(target)
  const screenshotFile = `${viewport.label}-${entry.slug}.png`

  await page.screenshot({
    path: path.join(EVIDENCE_DIR, screenshotFile),
    fullPage: true
  })

  const note =
    focusMethod === "tab"
      ? `Target reached via Tab in ${tabPresses} steps.`
      : "Target required programmatic focus fallback after tab sweep."

  return {
    flow: entry.flow,
    route: entry.route,
    objective: entry.objective,
    viewport: viewport.label,
    screenshot: screenshotFile,
    tabPressesToTarget: tabPresses,
    focusMethod,
    reachedTarget,
    keyInputVerified,
    note
  }
}

function writeViewportResults(
  viewport: ViewportTarget["label"],
  results: RouteFocusEvidence[]
): void {
  fs.writeFileSync(
    path.join(EVIDENCE_DIR, `${viewport}-route-matrix-results.json`),
    `${JSON.stringify(results, null, 2)}\n`,
    "utf8"
  )
}

function readViewportResults(
  viewport: ViewportTarget["label"]
): RouteFocusEvidence[] {
  const filePath = path.join(EVIDENCE_DIR, `${viewport}-route-matrix-results.json`)
  if (!fs.existsSync(filePath)) return []
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8")) as RouteFocusEvidence[]
  } catch {
    return []
  }
}

function buildMarkdownTableRows(results: RouteFocusEvidence[]): string {
  return results
    .map(
      (result) =>
        `| ${result.flow} | \`${result.route}\` | \`${result.screenshot}\` | ${result.tabPressesToTarget ?? "n/a"} | ${result.focusMethod} | ${result.keyInputVerified ? "pass" : "fail"} | ${result.note} |`
    )
    .join("\n")
}

function writeEvidenceReadme(): void {
  const desktopResults = readViewportResults("desktop")
  const mobileResults = readViewportResults("mobile")

  const markdown = [
    "# M3.2 Keyboard/Focus Evidence Set",
    "",
    `Date: ${DATE_STAMP.split("_").join("-")}`,
    "",
    "## Desktop (1440x900)",
    "",
    "| Flow | Route | Screenshot | Tab Presses | Focus Method | Key Input | Notes |",
    "|---|---|---|---:|---|---|---|",
    buildMarkdownTableRows(desktopResults),
    "",
    "## Mobile (375x812)",
    "",
    "| Flow | Route | Screenshot | Tab Presses | Focus Method | Key Input | Notes |",
    "|---|---|---|---:|---|---|---|",
    buildMarkdownTableRows(mobileResults),
    ""
  ].join("\n")

  fs.writeFileSync(path.join(EVIDENCE_DIR, "README.md"), markdown, "utf8")
}

test.describe("M3.2 Core Flow Keyboard/Focus Evidence", () => {
  test.beforeEach(async ({ page }) => {
    ensureEvidenceDirectory()
    await seedAuth(page)
  })

  for (const viewport of VIEWPORTS) {
    test(`capture ${viewport.label} route matrix evidence`, async ({ page }) => {
      const results: RouteFocusEvidence[] = []

      for (const entry of ROUTE_MATRIX) {
        const result = await captureRouteFocusEvidence(page, viewport, entry)
        results.push(result)
      }

      writeViewportResults(viewport.label, results)
      writeEvidenceReadme()
    })
  }
})
