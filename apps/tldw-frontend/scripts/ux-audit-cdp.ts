import fs from "node:fs/promises"
import path from "node:path"
import { chromium, devices, type BrowserContext, type Page } from "playwright"
import { PAGE_MAPPINGS, WEBUI_ONLY_PAGES } from "../e2e/page-mapping"

type Severity = "info" | "warn" | "error"

interface ScreenshotRecord {
  id: string
  file: string
  viewport: "desktop" | "mobile"
  route: string
  label: string
  url: string
  title: string
  createdAt: string
}

interface AccessibilitySignals {
  unlabeledInputs: number
  unnamedButtons: number
  imagesWithoutAlt: number
  smallTargets: number
  h1Count: number
  lang: string | null
  focusVisible: boolean | null
  focusTag: string | null
  focusClass: string | null
}

interface PageAuditResult {
  route: string
  name: string
  url: string
  title: string
  status: number | null
  finalUrl: string
  desktopScreenshot: string
  mobileScreenshot: string
  interactionScreenshots: string[]
  interactionNotes: string[]
  discoveredLinks: string[]
  diagnostics: {
    consoleErrors: string[]
    pageErrors: string[]
    requestFailures: string[]
  }
  accessibility: AccessibilitySignals
}

interface FlowStep {
  flow: string
  step: string
  screenshot: string
  note: string
  severity: Severity
}

interface DiscoveryData {
  rootLinks: string[]
  rootNavLabels: string[]
  allDiscoveredLinks: string[]
  mappedRoutes: string[]
  reachableRoutes: string[]
  unreachableRoutes: string[]
}

interface AuditOutput {
  generatedAt: string
  baseUrl: string
  backendUrl: string
  screenshots: ScreenshotRecord[]
  discovery: DiscoveryData
  pages: PageAuditResult[]
  flows: Record<string, FlowStep[]>
  edgeCases: FlowStep[]
  summary: {
    totalMappedRoutes: number
    totalVisitedRoutes: number
    totalScreenshots: number
    pagesWithErrors: number
    pagesWithAccessibilityWarnings: number
  }
}

const BASE_URL = (process.env.TLDW_WEB_URL || "http://127.0.0.1:3000").replace(/\/$/, "")
const BACKEND_URL = process.env.TLDW_SERVER_URL || "http://127.0.0.1:8000"
const API_KEY = process.env.TLDW_API_KEY || "THIS-IS-A-SECURE-KEY-123-FAKE-KEY"
const TS = new Date().toISOString().replace(/[:.]/g, "-")
const OUT_DIR = path.resolve(process.cwd(), "cdp-artifacts", `ux-audit-${TS}`)

let screenshotIndex = 1
const screenshotRecords: ScreenshotRecord[] = []

function slugify(input: string): string {
  return input
    .replace(/^\//, "")
    .replace(/[?#]/g, "-")
    .replace(/[^a-zA-Z0-9._/-]+/g, "-")
    .replace(/\//g, "_")
    .replace(/-+/g, "-")
    .replace(/^[-_.]+|[-_.]+$/g, "") || "root"
}

function normalizeRoute(route: string): string {
  const trimmed = String(route || "").trim()
  if (!trimmed) return "/"
  if (/^https?:/i.test(trimmed)) {
    const u = new URL(trimmed)
    return `${u.pathname}${u.search}` || "/"
  }
  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`
}

function routeToUrl(route: string): string {
  if (/^https?:/i.test(route)) return route
  return `${BASE_URL}${normalizeRoute(route)}`
}

async function ensureDirs(): Promise<void> {
  await fs.mkdir(path.join(OUT_DIR, "desktop"), { recursive: true })
  await fs.mkdir(path.join(OUT_DIR, "mobile"), { recursive: true })
  await fs.mkdir(path.join(OUT_DIR, "flows"), { recursive: true })
}

async function primeCdp(page: Page): Promise<void> {
  try {
    const session = await page.context().newCDPSession(page)
    await session.send("Runtime.enable")
    await session.send("Network.enable")
    await session.send("Page.enable")
    await session.detach()
  } catch {
    // Best effort only; continue if CDP bootstrap is unavailable.
  }
}

async function takeShot(
  page: Page,
  viewport: "desktop" | "mobile",
  route: string,
  label: string,
  subdir?: "desktop" | "mobile" | "flows"
): Promise<string> {
  const id = `S${String(screenshotIndex).padStart(3, "0")}`
  const file = `${id}_${viewport}_${slugify(route)}_${slugify(label)}.png`
  const dir = subdir || viewport
  const target = path.join(OUT_DIR, dir, file)
  await page.screenshot({ path: target, fullPage: true })
  screenshotRecords.push({
    id,
    file: `${dir}/${file}`,
    viewport,
    route,
    label,
    url: page.url(),
    title: await page.title().catch(() => ""),
    createdAt: new Date().toISOString()
  })
  screenshotIndex += 1
  return `${dir}/${file}`
}

async function seedAuth(context: BrowserContext): Promise<void> {
  await context.addInitScript(
    (cfg: { backendUrl: string; apiKey: string }) => {
      try {
        localStorage.setItem(
          "tldwConfig",
          JSON.stringify({
            serverUrl: cfg.backendUrl,
            authMode: "single-user",
            apiKey: cfg.apiKey
          })
        )
      } catch {
        // ignore
      }
      try {
        localStorage.setItem("__tldw_first_run_complete", "true")
      } catch {
        // ignore
      }
      try {
        localStorage.setItem("__tldw_allow_offline", "true")
      } catch {
        // ignore
      }
    },
    { backendUrl: BACKEND_URL, apiKey: API_KEY }
  )
}

async function firstVisibleButton(page: Page, pattern: RegExp): Promise<ReturnType<Page["locator"]> | null> {
  const buttons = page.locator("button, [role=button], input[type=submit]")
  const count = Math.min(await buttons.count(), 100)
  for (let i = 0; i < count; i++) {
    const candidate = buttons.nth(i)
    const visible = await candidate.isVisible().catch(() => false)
    if (!visible) continue
    const enabled = await candidate.isEnabled().catch(() => false)
    if (!enabled) continue
    const text = (
      (await candidate.innerText().catch(() => "")) ||
      (await candidate.getAttribute("aria-label").catch(() => "")) ||
      ""
    ).trim()
    if (pattern.test(text)) {
      return candidate
    }
  }
  return null
}

async function firstVisibleInput(page: Page, pattern: RegExp): Promise<ReturnType<Page["locator"]> | null> {
  const inputs = page.locator("input:not([type=hidden]), textarea")
  const count = Math.min(await inputs.count(), 100)
  for (let i = 0; i < count; i++) {
    const candidate = inputs.nth(i)
    const visible = await candidate.isVisible().catch(() => false)
    if (!visible) continue
    const disabled = await candidate.isDisabled().catch(() => true)
    if (disabled) continue
    const placeholder = (await candidate.getAttribute("placeholder").catch(() => "")) || ""
    const name = (await candidate.getAttribute("name").catch(() => "")) || ""
    const id = (await candidate.getAttribute("id").catch(() => "")) || ""
    const aria = (await candidate.getAttribute("aria-label").catch(() => "")) || ""
    const combined = `${placeholder} ${name} ${id} ${aria}`.toLowerCase()
    if (pattern.test(combined)) {
      return candidate
    }
  }
  return null
}

async function collectInternalLinks(page: Page): Promise<string[]> {
  const origin = new URL(BASE_URL).origin
  return page
    .evaluate((baseOrigin) => {
      const links = new Set<string>()
      for (const anchor of Array.from(document.querySelectorAll("a[href]"))) {
        const href = anchor.getAttribute("href") || ""
        if (!href || href.startsWith("mailto:") || href.startsWith("tel:")) continue
        try {
          const url = new URL(href, window.location.href)
          if (url.origin === baseOrigin) {
            links.add(`${url.pathname}${url.search}`)
          }
        } catch {
          // ignore
        }
      }
      return Array.from(links).sort()
    }, origin)
    .catch(() => [])
}

async function collectRootNavLabels(page: Page): Promise<string[]> {
  return page
    .evaluate(() => {
      const labels = new Set<string>()
      const navNodes = Array.from(document.querySelectorAll("nav a, nav button, [role=navigation] a, [role=menuitem]"))
      for (const node of navNodes) {
        const raw = (node.textContent || "").trim().replace(/\s+/g, " ")
        if (raw) labels.add(raw)
      }
      return Array.from(labels).sort()
    })
    .catch(() => [])
}

async function collectAccessibilitySignals(page: Page): Promise<AccessibilitySignals> {
  await page.keyboard.press("Tab").catch(() => {})
  const focusProbe = await page
    .evaluate(() => {
      const active = document.activeElement as HTMLElement | null
      if (!active) {
        return { focusVisible: null, focusTag: null, focusClass: null }
      }
      const style = window.getComputedStyle(active)
      const outlined =
        style.outlineStyle !== "none" ||
        Number.parseFloat(style.outlineWidth || "0") > 0 ||
        style.boxShadow !== "none"
      return {
        focusVisible: outlined,
        focusTag: active.tagName?.toLowerCase() || null,
        focusClass: active.className || null
      }
    })
    .catch(() => ({ focusVisible: null, focusTag: null, focusClass: null }))

  const structural = await page
    .evaluate(() => {
      const isHidden = (el: Element): boolean => {
        const style = window.getComputedStyle(el)
        return style.display === "none" || style.visibility === "hidden"
      }

      const hasAccessibleName = (el: Element): boolean => {
        const ariaLabel = el.getAttribute("aria-label")?.trim()
        const ariaLabelledBy = el.getAttribute("aria-labelledby")?.trim()
        const title = el.getAttribute("title")?.trim()
        const text = (el.textContent || "").trim()
        return Boolean(ariaLabel || ariaLabelledBy || title || text)
      }

      const inputs = Array.from(document.querySelectorAll("input:not([type=hidden]), textarea, select"))
      const unlabeledInputs = inputs.filter((el) => {
        if (isHidden(el)) return false
        const id = el.getAttribute("id")
        const ariaLabel = el.getAttribute("aria-label")
        const ariaLabelledBy = el.getAttribute("aria-labelledby")
        const wrappedByLabel = Boolean(el.closest("label"))
        const hasForLabel = id ? document.querySelector(`label[for=]`) : null
        return !(ariaLabel || ariaLabelledBy || wrappedByLabel || hasForLabel)
      }).length

      const buttons = Array.from(document.querySelectorAll("button, [role=button], input[type=button], input[type=submit]"))
      const unnamedButtons = buttons.filter((el) => !isHidden(el) && !hasAccessibleName(el)).length

      const imagesWithoutAlt = Array.from(document.querySelectorAll("img")).filter((img) => {
        if (isHidden(img)) return false
        return !img.hasAttribute("alt")
      }).length

      const clickables = Array.from(
        document.querySelectorAll(
          "button, a[href], [role=button], input, select, textarea, [tabindex]:not([tabindex=-1])"
        )
      )
      const smallTargets = clickables.filter((el) => {
        if (isHidden(el)) return false
        const rect = el.getBoundingClientRect()
        if (rect.width === 0 || rect.height === 0) return false
        return rect.width < 44 || rect.height < 44
      }).length

      return {
        unlabeledInputs,
        unnamedButtons,
        imagesWithoutAlt,
        smallTargets,
        h1Count: document.querySelectorAll("h1").length,
        lang: document.documentElement.getAttribute("lang")
      }
    })
    .catch(() => ({
      unlabeledInputs: 0,
      unnamedButtons: 0,
      imagesWithoutAlt: 0,
      smallTargets: 0,
      h1Count: 0,
      lang: null
    }))

  return {
    ...structural,
    focusVisible: focusProbe.focusVisible,
    focusTag: focusProbe.focusTag,
    focusClass: focusProbe.focusClass
  }
}

async function runGenericInteractions(
  page: Page,
  route: string,
  viewport: "desktop" | "mobile"
): Promise<{ notes: string[]; screenshots: string[] }> {
  const notes: string[] = []
  const shots: string[] = []

  const combo = page.locator("[role=combobox], .ant-select-selector").first()
  if (await combo.isVisible().catch(() => false)) {
    await combo.click({ timeout: 2500 }).catch(() => {})
    await page.waitForTimeout(400)
    shots.push(await takeShot(page, viewport, route, "interaction-combobox"))
    notes.push("Opened first visible combobox/dropdown.")
    await page.keyboard.press("Escape").catch(() => {})
  }

  const submitBtn = await firstVisibleButton(page, /(save|submit|create|add|process|search|login|sign in|test|connect)/i)
  if (submitBtn) {
    await submitBtn.click({ timeout: 3000 }).catch(() => {})
    await page.waitForTimeout(800)
    shots.push(await takeShot(page, viewport, route, "interaction-submit"))
    const errorCount = await page
      .locator(".ant-form-item-explain-error, [role=alert], .error, .ant-message-error")
      .count()
      .catch(() => 0)
    notes.push(`Triggered first submit-like action; visible error alerts: ${errorCount}.`)
  }

  const themeBtn = await firstVisibleButton(page, /(theme|dark|light|appearance)/i)
  if (themeBtn) {
    await themeBtn.click({ timeout: 2000 }).catch(() => {})
    await page.waitForTimeout(600)
    shots.push(await takeShot(page, viewport, route, "interaction-theme-toggle"))
    notes.push("Toggled theme/appearance control.")
  }

  return { notes, screenshots: shots }
}

async function navigateForAudit(
  page: Page,
  route: string,
  viewport: "desktop" | "mobile",
  doInteractions: boolean
): Promise<{
  title: string
  url: string
  finalUrl: string
  status: number | null
  screenshot: string
  interactionScreenshots: string[]
  interactionNotes: string[]
  discoveredLinks: string[]
  diagnostics: { consoleErrors: string[]; pageErrors: string[]; requestFailures: string[] }
  accessibility: AccessibilitySignals
}> {
  const url = routeToUrl(route)
  const consoleErrors: string[] = []
  const pageErrors: string[] = []
  const requestFailures: string[] = []

  const onConsole = (msg: { type: () => string; text: () => string }) => {
    if (msg.type() === "error") consoleErrors.push(msg.text())
  }
  const onPageError = (err: Error) => {
    pageErrors.push(err.message)
  }
  const onRequestFailed = (req: { url: () => string; failure: () => { errorText?: string } | null }) => {
    const failure = req.failure()
    requestFailures.push(`${req.url()} :: ${failure?.errorText || "failed"}`)
  }

  page.on("console", onConsole)
  page.on("pageerror", onPageError)
  page.on("requestfailed", onRequestFailed)

  let status: number | null = null
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 }).then((response) => {
    status = response?.status() ?? null
  }).catch(() => {
    status = null
  })

  await page.waitForLoadState("networkidle", { timeout: 6000 }).catch(() => {})
  await page.waitForTimeout(500)

  const screenshot = await takeShot(page, viewport, route, "initial")
  let interactionScreenshots: string[] = []
  let interactionNotes: string[] = []
  if (doInteractions) {
    const interactions = await runGenericInteractions(page, route, viewport)
    interactionScreenshots = interactions.screenshots
    interactionNotes = interactions.notes
  }

  const discoveredLinks = await collectInternalLinks(page)
  const accessibility = await collectAccessibilitySignals(page)

  const title = await page.title().catch(() => "")
  const finalUrl = page.url()

  page.off("console", onConsole)
  page.off("pageerror", onPageError)
  page.off("requestfailed", onRequestFailed)

  return {
    title,
    url,
    finalUrl,
    status,
    screenshot,
    interactionScreenshots,
    interactionNotes,
    discoveredLinks,
    diagnostics: {
      consoleErrors,
      pageErrors,
      requestFailures
    },
    accessibility
  }
}

async function runMediaFlow(page: Page): Promise<FlowStep[]> {
  const steps: FlowStep[] = []
  const route = "/media"
  await page.goto(routeToUrl(route), { waitUntil: "domcontentloaded", timeout: 45000 }).catch(() => {})
  await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {})
  steps.push({
    flow: "media_ingestion",
    step: "Media landing",
    screenshot: await takeShot(page, "desktop", route, "flow-media-landing", "flows"),
    note: "Loaded media library screen.",
    severity: "info"
  })

  const openBtn = await firstVisibleButton(page, /(quick ingest|upload|add|new|ingest)/i)
  if (openBtn) {
    await openBtn.click({ timeout: 3000 }).catch(() => {})
    await page.waitForTimeout(700)
    steps.push({
      flow: "media_ingestion",
      step: "Open ingestion UI",
      screenshot: await takeShot(page, "desktop", route, "flow-media-open-ingest", "flows"),
      note: "Opened ingestion entry point button.",
      severity: "info"
    })
  }

  const urlInput =
    (await firstVisibleInput(page, /(url|link|source)/i)) ||
    page.locator("input[type=url]").first()

  const processBtn = await firstVisibleButton(page, /(process|ingest|add|submit|go|upload)/i)

  if (urlInput && (await urlInput.isVisible().catch(() => false)) && processBtn) {
    await urlInput.fill("not-a-valid-url").catch(() => {})
    await processBtn.click({ timeout: 3000 }).catch(() => {})
    await page.waitForTimeout(1000)
    steps.push({
      flow: "media_ingestion",
      step: "Submit invalid URL",
      screenshot: await takeShot(page, "desktop", route, "flow-media-invalid-url", "flows"),
      note: "Submitted intentionally invalid URL to inspect validation messaging.",
      severity: "warn"
    })

    await urlInput.fill("https://example.com").catch(() => {})
    await processBtn.click({ timeout: 3000 }).catch(() => {})
    await page.waitForTimeout(3000)
    steps.push({
      flow: "media_ingestion",
      step: "Submit valid URL",
      screenshot: await takeShot(page, "desktop", route, "flow-media-valid-url", "flows"),
      note: "Submitted a valid URL to inspect processing/loading/result states.",
      severity: "info"
    })
  } else {
    steps.push({
      flow: "media_ingestion",
      step: "Ingestion input unavailable",
      screenshot: await takeShot(page, "desktop", route, "flow-media-input-missing", "flows"),
      note: "Could not find URL input and process button combination for this runtime state.",
      severity: "warn"
    })
  }

  return steps
}

async function runSearchFlow(page: Page): Promise<FlowStep[]> {
  const steps: FlowStep[] = []
  const route = "/search"
  await page.goto(routeToUrl(route), { waitUntil: "domcontentloaded", timeout: 45000 }).catch(() => {})
  await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {})
  steps.push({
    flow: "search",
    step: "Search landing",
    screenshot: await takeShot(page, "desktop", route, "flow-search-landing", "flows"),
    note: "Loaded search workspace.",
    severity: "info"
  })

  const input =
    (await firstVisibleInput(page, /(search|query|find)/i)) ||
    page.locator("input[type=search], [role=searchbox]").first()

  if (input && (await input.isVisible().catch(() => false))) {
    await input.fill("machine learning").catch(() => {})
    const searchBtn = await firstVisibleButton(page, /(search|run|find)/i)
    if (searchBtn) {
      await searchBtn.click({ timeout: 3000 }).catch(() => {})
    } else {
      await input.press("Enter").catch(() => {})
    }
    await page.waitForTimeout(2200)
    steps.push({
      flow: "search",
      step: "Run normal query",
      screenshot: await takeShot(page, "desktop", route, "flow-search-query", "flows"),
      note: "Executed regular search query and captured result/empty state.",
      severity: "info"
    })

    await input.fill("zzzzzzzzzzzzzzzzzzzzzzzzzzzzzz").catch(() => {})
    if (searchBtn) {
      await searchBtn.click({ timeout: 3000 }).catch(() => {})
    } else {
      await input.press("Enter").catch(() => {})
    }
    await page.waitForTimeout(1800)
    steps.push({
      flow: "search",
      step: "Run low-likelihood query",
      screenshot: await takeShot(page, "desktop", route, "flow-search-empty-or-error", "flows"),
      note: "Executed unlikely query to inspect empty and no-results messaging.",
      severity: "warn"
    })
  }

  return steps
}

async function runChatFlow(page: Page): Promise<FlowStep[]> {
  const steps: FlowStep[] = []
  const route = "/chat"
  await page.goto(routeToUrl(route), { waitUntil: "domcontentloaded", timeout: 45000 }).catch(() => {})
  await page.waitForLoadState("networkidle", { timeout: 7000 }).catch(() => {})
  steps.push({
    flow: "chat",
    step: "Chat landing",
    screenshot: await takeShot(page, "desktop", route, "flow-chat-landing", "flows"),
    note: "Loaded chat interface.",
    severity: "info"
  })

  const startBtn = await firstVisibleButton(page, /(start chatting|start chat|new chat)/i)
  if (startBtn) {
    await startBtn.click({ timeout: 2000 }).catch(() => {})
    await page.waitForTimeout(400)
  }

  const input =
    page.locator("#textarea-message").first() ||
    (await firstVisibleInput(page, /(message|ask|prompt|chat)/i)) ||
    page.locator("textarea").first()

  if (input && (await input.isVisible().catch(() => false))) {
    await input.fill("Hello. Reply with one short sentence for UX audit verification.").catch(() => {})

    const sendBtn = await firstVisibleButton(page, /(send|submit|enter)/i)
    if (sendBtn) {
      await sendBtn.click({ timeout: 3000 }).catch(() => {})
    } else {
      await input.press("Enter").catch(() => {})
    }

    await page.waitForTimeout(6000)
    steps.push({
      flow: "chat",
      step: "Send message",
      screenshot: await takeShot(page, "desktop", route, "flow-chat-after-send", "flows"),
      note: "Sent message and captured assistant response, error, or loading state.",
      severity: "info"
    })

    const newChatBtn = await firstVisibleButton(page, /(new chat|new conversation|reset)/i)
    if (newChatBtn) {
      await newChatBtn.click({ timeout: 2500 }).catch(() => {})
      await page.waitForTimeout(700)
      steps.push({
        flow: "chat",
        step: "Start new conversation",
        screenshot: await takeShot(page, "desktop", route, "flow-chat-new-thread", "flows"),
        note: "Triggered new chat flow and captured state reset/history visibility.",
        severity: "info"
      })
    }
  }

  return steps
}

async function runSettingsFlow(page: Page): Promise<FlowStep[]> {
  const steps: FlowStep[] = []
  const route = "/settings/tldw"
  await page.goto(routeToUrl(route), { waitUntil: "domcontentloaded", timeout: 45000 }).catch(() => {})
  await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {})

  steps.push({
    flow: "settings",
    step: "Settings landing",
    screenshot: await takeShot(page, "desktop", route, "flow-settings-landing", "flows"),
    note: "Loaded server/configuration settings section.",
    severity: "info"
  })

  const serverInput =
    (await firstVisibleInput(page, /(server|url|endpoint)/i)) ||
    page.getByLabel(/server/i).first()
  const keyInput =
    (await firstVisibleInput(page, /(api key|apikey|token|key)/i)) ||
    page.getByLabel(/api key|token|key/i).first()
  const saveBtn = await firstVisibleButton(page, /(save|apply|update)/i)
  const testBtn = await firstVisibleButton(page, /(test|check|verify|connect)/i)

  if (serverInput && (await serverInput.isVisible().catch(() => false))) {
    await serverInput.fill("").catch(() => {})
  }
  if (keyInput && (await keyInput.isVisible().catch(() => false))) {
    await keyInput.fill("").catch(() => {})
  }

  if (saveBtn) {
    await saveBtn.click({ timeout: 3000 }).catch(() => {})
    await page.waitForTimeout(1200)
    steps.push({
      flow: "settings",
      step: "Submit empty config",
      screenshot: await takeShot(page, "desktop", route, "flow-settings-empty-submit", "flows"),
      note: "Submitted empty settings fields to inspect validation and prevention behavior.",
      severity: "warn"
    })
  }

  if (serverInput && (await serverInput.isVisible().catch(() => false))) {
    await serverInput.fill(BACKEND_URL).catch(() => {})
  }
  if (keyInput && (await keyInput.isVisible().catch(() => false))) {
    await keyInput.fill(API_KEY).catch(() => {})
  }
  if (saveBtn) {
    await saveBtn.click({ timeout: 3000 }).catch(() => {})
  }
  if (testBtn) {
    await testBtn.click({ timeout: 3000 }).catch(() => {})
  }
  await page.waitForTimeout(1800)
  steps.push({
    flow: "settings",
    step: "Save/test filled config",
    screenshot: await takeShot(page, "desktop", route, "flow-settings-valid-submit", "flows"),
    note: "Filled server URL and API key, then ran save/test actions.",
    severity: "info"
  })

  return steps
}

async function runAuthFlow(page: Page): Promise<FlowStep[]> {
  const steps: FlowStep[] = []

  for (const route of ["/login", "/setup"]) {
    await page.goto(routeToUrl(route), { waitUntil: "domcontentloaded", timeout: 45000 }).catch(() => {})
    await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {})
    steps.push({
      flow: "auth",
      step: `${route} landing`,
      screenshot: await takeShot(page, "desktop", route, `flow-auth-${slugify(route)}-landing`, "flows"),
      note: `Loaded ${route} authentication/setup related screen.`,
      severity: "info"
    })

    const submitBtn = await firstVisibleButton(page, /(login|sign in|submit|continue|next|save|finish)/i)
    if (submitBtn) {
      await submitBtn.click({ timeout: 3000 }).catch(() => {})
      await page.waitForTimeout(1200)
      steps.push({
        flow: "auth",
        step: `${route} empty submit`,
        screenshot: await takeShot(page, "desktop", route, `flow-auth-${slugify(route)}-submit-empty`, "flows"),
        note: `Submitted without additional input to inspect error prevention/validation on ${route}.`,
        severity: "warn"
      })
    }
  }

  return steps
}

async function runCharacterFlow(page: Page): Promise<FlowStep[]> {
  const steps: FlowStep[] = []

  await page.goto(routeToUrl("/persona"), { waitUntil: "domcontentloaded", timeout: 45000 }).catch(() => {})
  await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {})
  steps.push({
    flow: "character_chat",
    step: "Persona chat landing",
    screenshot: await takeShot(page, "desktop", "/persona", "flow-persona-landing", "flows"),
    note: "Loaded persona chat page.",
    severity: "info"
  })

  const personaInput =
    (await firstVisibleInput(page, /(message|chat|prompt|ask)/i)) ||
    page.locator("textarea").first()
  if (personaInput && (await personaInput.isVisible().catch(() => false))) {
    await personaInput.fill("Hi persona, give a one-line greeting.").catch(() => {})
    const sendBtn = await firstVisibleButton(page, /(send|submit|start)/i)
    if (sendBtn) {
      await sendBtn.click({ timeout: 3000 }).catch(() => {})
    } else {
      await personaInput.press("Enter").catch(() => {})
    }
    await page.waitForTimeout(5000)
    steps.push({
      flow: "character_chat",
      step: "Send persona message",
      screenshot: await takeShot(page, "desktop", "/persona", "flow-persona-send", "flows"),
      note: "Sent a persona chat message and captured outcome.",
      severity: "info"
    })
  }

  await page.goto(routeToUrl("/characters"), { waitUntil: "domcontentloaded", timeout: 45000 }).catch(() => {})
  await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {})
  steps.push({
    flow: "character_chat",
    step: "Characters workspace",
    screenshot: await takeShot(page, "desktop", "/characters", "flow-characters-workspace", "flows"),
    note: "Captured character management workspace.",
    severity: "info"
  })

  return steps
}

async function runNotesFlow(page: Page): Promise<FlowStep[]> {
  const steps: FlowStep[] = []
  const route = "/notes"
  await page.goto(routeToUrl(route), { waitUntil: "domcontentloaded", timeout: 45000 }).catch(() => {})
  await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {})

  steps.push({
    flow: "notes",
    step: "Notes landing",
    screenshot: await takeShot(page, "desktop", route, "flow-notes-landing", "flows"),
    note: "Loaded notes/knowledge capture page.",
    severity: "info"
  })

  const newBtn = await firstVisibleButton(page, /(new note|new|create|add)/i)
  if (newBtn) {
    await newBtn.click({ timeout: 2500 }).catch(() => {})
    await page.waitForTimeout(900)
  }

  const titleInput = await firstVisibleInput(page, /(title|name|subject)/i)
  const bodyInput = await firstVisibleInput(page, /(content|body|note|text|description)/i)

  if (titleInput && (await titleInput.isVisible().catch(() => false))) {
    await titleInput.fill("UX audit test note").catch(() => {})
  }
  if (bodyInput && (await bodyInput.isVisible().catch(() => false))) {
    await bodyInput.fill("This note is created by automated UX audit flow to evaluate form and save states.").catch(() => {})
  }

  const saveBtn = await firstVisibleButton(page, /(save|create|add)/i)
  if (saveBtn) {
    await saveBtn.click({ timeout: 2500 }).catch(() => {})
    await page.waitForTimeout(1400)
  }

  steps.push({
    flow: "notes",
    step: "Create note",
    screenshot: await takeShot(page, "desktop", route, "flow-notes-create", "flows"),
    note: "Attempted note creation to evaluate form UX and feedback loop.",
    severity: "info"
  })

  return steps
}

async function runEdgeCases(page: Page): Promise<FlowStep[]> {
  const steps: FlowStep[] = []

  const badRoute = "/this-route-should-404-ux-audit"
  await page.goto(routeToUrl(badRoute), { waitUntil: "domcontentloaded", timeout: 45000 }).catch(() => {})
  await page.waitForTimeout(1000)
  steps.push({
    flow: "edge_cases",
    step: "404 route",
    screenshot: await takeShot(page, "desktop", badRoute, "edge-404", "flows"),
    note: "Captured 404/error page handling for invalid route.",
    severity: "warn"
  })

  await page.goto(routeToUrl("/media"), { waitUntil: "commit", timeout: 45000 }).catch(() => {})
  await page.waitForTimeout(300)
  steps.push({
    flow: "edge_cases",
    step: "Loading-state snapshot",
    screenshot: await takeShot(page, "desktop", "/media", "edge-loading-state", "flows"),
    note: "Captured early loading state before network idle.",
    severity: "info"
  })

  await page.goto(routeToUrl("/chat"), { waitUntil: "domcontentloaded", timeout: 45000 }).catch(() => {})
  await page.waitForTimeout(700)
  const input =
    (await firstVisibleInput(page, /(message|chat|prompt|ask)/i)) ||
    page.locator("textarea").first()
  if (input && (await input.isVisible().catch(() => false))) {
    await input.fill("Long-content-test ".repeat(180)).catch(() => {})
    await page.waitForTimeout(350)
    steps.push({
      flow: "edge_cases",
      step: "Long-content overflow",
      screenshot: await takeShot(page, "desktop", "/chat", "edge-long-content", "flows"),
      note: "Filled chat input with long text to inspect overflow and scroll containment.",
      severity: "warn"
    })
  }

  return steps
}

async function main(): Promise<void> {
  await ensureDirs()

  const routeNameMap = new Map<string, string>()
  for (const item of [...PAGE_MAPPINGS, ...WEBUI_ONLY_PAGES]) {
    if (item.webuiPath) {
      const route = normalizeRoute(item.webuiPath)
      if (!routeNameMap.has(route)) routeNameMap.set(route, item.name)
    }
  }

  const mappedRoutes = Array.from(routeNameMap.keys()).sort((a, b) => a.localeCompare(b))

  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-dev-shm-usage"]
  })

  const desktopContext = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  })

  const mobileContext = await browser.newContext({
    ...devices["iPhone 12"],
    viewport: { width: 375, height: 812 }
  })

  await seedAuth(desktopContext)
  await seedAuth(mobileContext)

  const desktopPage = await desktopContext.newPage()
  const mobilePage = await mobileContext.newPage()
  await primeCdp(desktopPage)
  await primeCdp(mobilePage)

  const pages: PageAuditResult[] = []
  const discoveredLinksSet = new Set<string>()

  // Discovery phase from root
  await desktopPage.goto(routeToUrl("/"), { waitUntil: "domcontentloaded", timeout: 45000 }).catch(() => {})
  await desktopPage.waitForTimeout(1000)
  const rootLinks = await collectInternalLinks(desktopPage)
  const rootNavLabels = await collectRootNavLabels(desktopPage)
  rootLinks.forEach((link) => discoveredLinksSet.add(normalizeRoute(link)))

  for (const route of mappedRoutes) {
    const desktopData = await navigateForAudit(desktopPage, route, "desktop", true)
    const mobileData = await navigateForAudit(mobilePage, route, "mobile", false)

    for (const link of desktopData.discoveredLinks) {
      discoveredLinksSet.add(normalizeRoute(link))
    }

    pages.push({
      route,
      name: routeNameMap.get(route) || route,
      url: desktopData.url,
      title: desktopData.title,
      status: desktopData.status,
      finalUrl: desktopData.finalUrl,
      desktopScreenshot: desktopData.screenshot,
      mobileScreenshot: mobileData.screenshot,
      interactionScreenshots: desktopData.interactionScreenshots,
      interactionNotes: desktopData.interactionNotes,
      discoveredLinks: desktopData.discoveredLinks,
      diagnostics: desktopData.diagnostics,
      accessibility: desktopData.accessibility
    })
  }

  const flowPage = await desktopContext.newPage()
  await primeCdp(flowPage)
  await seedAuth(desktopContext)

  const mediaFlow = await runMediaFlow(flowPage)
  const searchFlow = await runSearchFlow(flowPage)
  const chatFlow = await runChatFlow(flowPage)
  const settingsFlow = await runSettingsFlow(flowPage)
  const authFlow = await runAuthFlow(flowPage)
  const characterFlow = await runCharacterFlow(flowPage)
  const notesFlow = await runNotesFlow(flowPage)
  const edgeCases = await runEdgeCases(flowPage)

  const reachableRoutes = pages.filter((p) => p.status !== null && p.status < 400).map((p) => p.route)
  const unreachableRoutes = pages
    .filter((p) => p.status === null || p.status >= 400)
    .map((p) => `${p.route}${p.status ? ` (HTTP ${p.status})` : " (no response status)"}`)

  const pagesWithErrors = pages.filter(
    (p) =>
      p.diagnostics.consoleErrors.length > 0 ||
      p.diagnostics.pageErrors.length > 0 ||
      p.diagnostics.requestFailures.length > 0
  ).length

  const pagesWithAccessibilityWarnings = pages.filter(
    (p) =>
      p.accessibility.unlabeledInputs > 0 ||
      p.accessibility.unnamedButtons > 0 ||
      p.accessibility.imagesWithoutAlt > 0 ||
      p.accessibility.smallTargets > 0 ||
      p.accessibility.focusVisible === false
  ).length

  const output: AuditOutput = {
    generatedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    backendUrl: BACKEND_URL,
    screenshots: screenshotRecords,
    discovery: {
      rootLinks,
      rootNavLabels,
      allDiscoveredLinks: Array.from(discoveredLinksSet).sort((a, b) => a.localeCompare(b)),
      mappedRoutes,
      reachableRoutes,
      unreachableRoutes
    },
    pages,
    flows: {
      media_ingestion: mediaFlow,
      search: searchFlow,
      chat: chatFlow,
      settings: settingsFlow,
      auth: authFlow,
      character_chat: characterFlow,
      notes: notesFlow
    },
    edgeCases,
    summary: {
      totalMappedRoutes: mappedRoutes.length,
      totalVisitedRoutes: pages.length,
      totalScreenshots: screenshotRecords.length,
      pagesWithErrors,
      pagesWithAccessibilityWarnings
    }
  }

  await fs.writeFile(path.join(OUT_DIR, "audit-data.json"), JSON.stringify(output, null, 2), "utf8")

  await flowPage.close().catch(() => {})
  await desktopPage.close().catch(() => {})
  await mobilePage.close().catch(() => {})
  await desktopContext.close().catch(() => {})
  await mobileContext.close().catch(() => {})
  await browser.close().catch(() => {})

  console.log(JSON.stringify({ outDir: OUT_DIR, summary: output.summary }, null, 2))
}

main().catch(async (error) => {
  console.error("UX audit script failed:", error)
  process.exitCode = 1
})
