/**
 * Interactive Page Review Script
 *
 * This script provides an interactive Playwright-based review session for
 * systematically testing WebUI and Extension pages with a live backend.
 *
 * Usage:
 *   npx tsx e2e/interactive-review.ts [--session N] [--resume] [--extension-path PATH]
 *
 * Options:
 *   --session N          Start at session N (1-7, default: 1)
 *   --resume             Resume from last reviewed page
 *   --extension-path     Path to unpacked extension (for extension testing)
 *   --extension-id       Extension ID (auto-detected when possible)
 *   --non-interactive    Run without prompts (auto-detect pass/fail)
 *   --webui-only         Only review WebUI pages (skip extension)
 *   --output PATH        Custom path for results file
 */

import { chromium, Browser, Page, BrowserContext } from "playwright"
import * as fs from "fs"
import * as path from "path"
import * as readline from "readline"
import { waitForAppShell } from "./utils/helpers"
import {
  PAGE_MAPPINGS,
  WEBUI_ONLY_PAGES,
  EXTENSION_ONLY_PAGES,
  PageMapping,
  ReviewPriority,
  getPagesBySession,
  TOTAL_PAGE_COUNT
} from "./page-mapping"

// ═══════════════════════════════════════════════════════════════════════════
// Configuration
// ═══════════════════════════════════════════════════════════════════════════

interface ReviewConfig {
  webuiUrl: string
  backendUrl: string
  apiKey: string
  extensionPath: string | null
  extensionId: string | null
  nonInteractive: boolean
  outputPath: string
  startSession: ReviewPriority
  resume: boolean
  webuiOnly: boolean
}

const DEFAULT_CONFIG: ReviewConfig = {
  webuiUrl: process.env.WEBUI_URL || "http://localhost:3000",
  backendUrl: process.env.TLDW_SERVER_URL || "http://127.0.0.1:8000",
  apiKey: process.env.TLDW_API_KEY || "THIS-IS-A-SECURE-KEY-123-FAKE-KEY",
  extensionPath: null,
  extensionId: process.env.EXTENSION_ID || null,
  nonInteractive: false,
  outputPath: path.join(__dirname, "review-results.json"),
  startSession: 1,
  resume: false,
  webuiOnly: false
}

// ═══════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════

type ReviewStatus = "pass" | "fail" | "skip"

interface PageReviewResult {
  path: string
  name: string
  webui: ReviewStatus | null
  extension: ReviewStatus | null
  timestamp: string
  notes: string | null
  checklistResults: Record<string, boolean | null>
}

interface ReviewSession {
  sessionStart: string
  backend: string
  webuiUrl: string
  lastReviewedPath: string | null
  results: PageReviewResult[]
  summary: {
    total: number
    passed: number
    failed: number
    skipped: number
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════════════════════════════

function parseArgs(): ReviewConfig {
  const config = { ...DEFAULT_CONFIG }
  const args = process.argv.slice(2)

  for (let i = 0; i < args.length; i++) {
    const arg = args[i]
    if (arg === "--session" && args[i + 1]) {
      config.startSession = parseInt(args[++i], 10) as ReviewPriority
    } else if (arg === "--resume") {
      config.resume = true
    } else if (arg === "--extension-path" && args[i + 1]) {
      config.extensionPath = args[++i]
    } else if (arg === "--extension-id" && args[i + 1]) {
      config.extensionId = args[++i]
    } else if (arg === "--non-interactive") {
      config.nonInteractive = true
    } else if (arg === "--webui-only") {
      config.webuiOnly = true
    } else if (arg === "--output" && args[i + 1]) {
      config.outputPath = args[++i]
    }
  }

  return config
}

function loadExistingResults(outputPath: string): ReviewSession | null {
  try {
    if (fs.existsSync(outputPath)) {
      const content = fs.readFileSync(outputPath, "utf-8")
      return JSON.parse(content)
    }
  } catch {
    console.log("Could not load existing results, starting fresh")
  }
  return null
}

function saveResults(outputPath: string, session: ReviewSession): void {
  const resultStatuses = session.results.map((result) => {
    const statuses = [result.webui, result.extension].filter(
      (status): status is ReviewStatus => status !== null
    )

    if (statuses.length === 0) return "skip"
    if (statuses.includes("fail")) return "fail"
    if (statuses.every((status) => status === "pass")) return "pass"
    return "skip"
  })

  session.summary = {
    total: session.results.length,
    passed: resultStatuses.filter((status) => status === "pass").length,
    failed: resultStatuses.filter((status) => status === "fail").length,
    skipped: resultStatuses.filter((status) => status === "skip").length
  }

  fs.writeFileSync(outputPath, JSON.stringify(session, null, 2))
}

function createReadlineInterface(): readline.Interface {
  return readline.createInterface({
    input: process.stdin,
    output: process.stdout
  })
}

async function prompt(
  rl: readline.Interface,
  question: string
): Promise<string> {
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      resolve(answer.trim())
    })
  })
}

async function waitForKeypress(
  rl: readline.Interface,
  message: string
): Promise<string> {
  console.log(message)
  return prompt(rl, "")
}

// ═══════════════════════════════════════════════════════════════════════════
// Browser Setup
// ═══════════════════════════════════════════════════════════════════════════

async function setupBrowser(
  config: ReviewConfig
): Promise<{ browser: Browser; context: BrowserContext }> {
  const launchOptions: Parameters<typeof chromium.launch>[0] = {
    headless: false,
    args: ["--start-maximized"]
  }

  // If extension path provided, load as unpacked extension
  if (config.extensionPath && !config.webuiOnly) {
    const browser = await chromium.launchPersistentContext("", {
      headless: false,
      args: [
        `--disable-extensions-except=${config.extensionPath}`,
        `--load-extension=${config.extensionPath}`,
        "--start-maximized"
      ]
    })
    return { browser: browser as unknown as Browser, context: browser }
  }

  const browser = await chromium.launch(launchOptions)
  const context = await browser.newContext({
    viewport: null // Use full window
  })

  return { browser, context }
}

async function seedExtensionConfig(
  context: BrowserContext,
  config: ReviewConfig
): Promise<void> {
  if (!config.extensionPath || config.webuiOnly) return

  await context.addInitScript(
    (cfg) => {
      try {
        const payload: Record<string, unknown> = {
          tldwConfig: {
            serverUrl: cfg.backendUrl,
            authMode: "single-user",
            apiKey: cfg.apiKey
          },
          tldwServerUrl: cfg.backendUrl,
          __tldw_first_run_complete: true,
          __tldw_allow_offline: true,
          __tldw_review_seeded: true
        }

        if (typeof chrome !== "undefined" && chrome?.storage?.local) {
          chrome.storage.local.set(payload)
        }

        if (typeof localStorage !== "undefined") {
          localStorage.setItem("__tldw_first_run_complete", "true")
          localStorage.setItem("__tldw_allow_offline", "true")
        }
      } catch {
        // Best-effort only
      }
    },
    { backendUrl: config.backendUrl, apiKey: config.apiKey }
  )
}

async function resolveExtensionId(
  context: BrowserContext
): Promise<string | null> {
  let targetUrl =
    context.backgroundPages()[0]?.url() ||
    context.serviceWorkers()[0]?.url() ||
    ""

  if (!targetUrl) {
    try {
      const page =
        context.backgroundPages()[0] ||
        context.pages()[0] ||
        (await context.newPage())
      const session = await context.newCDPSession(page)
      const { targetInfos } = await session.send("Target.getTargets")
      const extTarget =
        targetInfos.find(
          (target: { url?: string; type?: string }) =>
            typeof target.url === "string" &&
            target.url.startsWith("chrome-extension://") &&
            (target.type === "background_page" ||
              target.type === "service_worker")
        ) ||
        targetInfos.find(
          (target: { url?: string }) =>
            typeof target.url === "string" &&
            target.url.startsWith("chrome-extension://")
        )

      if (extTarget?.url) {
        targetUrl = extTarget.url
      }
    } catch {
      // Best-effort only.
    }
  }

  const match = targetUrl.match(/chrome-extension:\/\/([a-p]{32})/)
  return match ? match[1] : null
}

async function seedAuth(page: Page, config: ReviewConfig): Promise<void> {
  await page.addInitScript(
    (cfg) => {
      try {
        localStorage.setItem(
          "tldwConfig",
          JSON.stringify({
            serverUrl: cfg.backendUrl,
            authMode: "single-user",
            apiKey: cfg.apiKey
          })
        )
      } catch {}
      try {
        localStorage.setItem("__tldw_first_run_complete", "true")
      } catch {}
      try {
        localStorage.setItem("__tldw_allow_offline", "true")
      } catch {}
    },
    { backendUrl: config.backendUrl, apiKey: config.apiKey }
  )
}

function getPageKey(mapping: PageMapping): string {
  return (
    mapping.webuiPath ||
    mapping.extensionOptionsPath ||
    mapping.extensionSidepanelPath ||
    mapping.name
  )
}

function buildExtensionUrl(
  extensionId: string,
  mapping: PageMapping
): { url: string; navigatePath: string | null } | null {
  if (mapping.extensionOptionsPath) {
    return {
      url: `chrome-extension://${extensionId}/options.html#${mapping.extensionOptionsPath}`,
      navigatePath: null
    }
  }

  if (mapping.extensionSidepanelPath) {
    return {
      url: `chrome-extension://${extensionId}/sidepanel.html`,
      navigatePath: mapping.extensionSidepanelPath
    }
  }

  return null
}

async function detectErrorBoundary(page: Page): Promise<boolean> {
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

  return errorBoundaryVisible || errorTextVisible
}

function deriveAutoStatus(input: {
  navError: string | null
  statusCode: number | null
  errorBoundary: boolean
}): { status: ReviewStatus; note: string | null } {
  if (input.navError) {
    return { status: "fail", note: `Navigation error: ${input.navError}` }
  }

  if (input.statusCode && input.statusCode >= 400) {
    return {
      status: "fail",
      note: `HTTP ${input.statusCode} response`
    }
  }

  if (input.errorBoundary) {
    return {
      status: "fail",
      note: "Error boundary visible"
    }
  }

  return { status: "pass", note: null }
}

// ═══════════════════════════════════════════════════════════════════════════
// Review Logic
// ═══════════════════════════════════════════════════════════════════════════

async function reviewPage(
  webuiPage: Page,
  extensionPage: Page | null,
  mapping: PageMapping,
  config: ReviewConfig,
  rl: readline.Interface | null
): Promise<PageReviewResult> {
  const result: PageReviewResult = {
    path: getPageKey(mapping),
    name: mapping.name,
    webui: null,
    extension: null,
    timestamp: new Date().toISOString(),
    notes: null,
    checklistResults: {}
  }

  console.log("\n" + "═".repeat(70))
  console.log(`Reviewing: ${mapping.name}`)
  console.log("═".repeat(70))
  console.log(`Category: ${mapping.category}`)
  if (mapping.webuiPath) {
    console.log(`WebUI Path: ${mapping.webuiPath}`)
  }

  if (mapping.sharedComponent) {
    console.log(`Shared Component: ${mapping.sharedComponent}`)
  }

  const hasWebui = Boolean(mapping.webuiPath)
  let webuiNavError: string | null = null
  let webuiStatusCode: number | null = null
  if (hasWebui && mapping.webuiPath) {
    // Navigate to WebUI page
    console.log("\n[WebUI] Navigating...")
    try {
      const response = await webuiPage.goto(
        `${config.webuiUrl}${mapping.webuiPath}`,
        {
          waitUntil: "domcontentloaded",
          timeout: 30000
        }
      )
      webuiStatusCode = response?.status() ?? null
      await waitForAppShell(webuiPage, 15000)
      console.log("[WebUI] Page loaded")
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      webuiNavError = message
      console.log(`[WebUI] Navigation error: ${message}`)
    }
  }

  // Navigate to Extension page if applicable
  const hasExtension =
    !config.webuiOnly &&
    extensionPage &&
    config.extensionId &&
    (mapping.extensionOptionsPath || mapping.extensionSidepanelPath)

  let extensionNavError: string | null = null
  let extensionStatusCode: number | null = null
  if (hasExtension && extensionPage) {
    const extTarget = buildExtensionUrl(config.extensionId!, mapping)
    if (!extTarget) {
      console.log("[Extension] No extension path mapped, skipping.")
    } else {
      const targetLabel =
        mapping.extensionOptionsPath || mapping.extensionSidepanelPath
      console.log(`\n[Extension] Navigating to ${targetLabel}...`)
      try {
        const response = await extensionPage.goto(extTarget.url, {
          waitUntil: "domcontentloaded",
          timeout: 30000
        })
        extensionStatusCode = response?.status() ?? null
        if (extTarget.navigatePath) {
          await extensionPage
            .waitForFunction(
              () =>
                typeof (window as Window & { __tldwNavigate?: unknown })
                  .__tldwNavigate === "function",
              undefined,
              { timeout: 10000 }
            )
            .catch(() => {})
          await extensionPage.evaluate((path) => {
            const targetWindow = window as Window & {
              __tldwNavigate?: (path: string) => void
            }
            targetWindow.__tldwNavigate?.(path)
          }, extTarget.navigatePath)
        }
        await waitForAppShell(extensionPage, 15000)
        console.log("[Extension] Page loaded")
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e)
        extensionNavError = message
        console.log(`[Extension] Navigation error: ${message}`)
      }
    }
  }

  if (!config.nonInteractive) {
    // Display checklist
    console.log("\n--- Interaction Checklist ---")
    mapping.checklistItems.forEach((item, idx) => {
      console.log(`  ${idx + 1}. ${item}`)
    })
    console.log("")

    // Wait for manual review
    console.log("Review the page(s) in the browser...")
    console.log("Press key to mark result:")
    console.log("  [p] = pass, [f] = fail, [s] = skip, [c] = checklist")
    console.log("")
  }

  if (config.nonInteractive) {
    if (hasWebui) {
      const errorBoundary = await detectErrorBoundary(webuiPage)
      const webuiAuto = deriveAutoStatus({
        navError: webuiNavError,
        statusCode: webuiStatusCode,
        errorBoundary
      })
      result.webui = webuiAuto.status
      if (webuiAuto.note) {
        result.notes = webuiAuto.note
      }
    }

    if (hasExtension && extensionPage) {
      const errorBoundary = await detectErrorBoundary(extensionPage)
      const extensionAuto = deriveAutoStatus({
        navError: extensionNavError,
        statusCode: extensionStatusCode,
        errorBoundary
      })
      result.extension = extensionAuto.status
      if (extensionAuto.note) {
        result.notes = result.notes
          ? `${result.notes} | Extension: ${extensionAuto.note}`
          : extensionAuto.note
      }
    }
  } else if (hasWebui) {
    // WebUI review
    let webuiStatus: ReviewStatus = "skip"
    const webuiKey = await prompt(rl!, "[WebUI] Result (p/f/s/c): ")

    if (webuiKey === "c") {
      // Run through checklist
      console.log("\n--- Checklist Review ---")
      let allPassed = true
    for (const item of mapping.checklistItems) {
        const checkResult = await prompt(rl!, `  ${item} (p/f/s): `)
        result.checklistResults[item] =
          checkResult === "p" ? true : checkResult === "f" ? false : null
        if (checkResult === "f") allPassed = false
      }
      webuiStatus = allPassed ? "pass" : "fail"
    } else {
      webuiStatus =
        webuiKey === "p" ? "pass" : webuiKey === "f" ? "fail" : "skip"
    }
    result.webui = webuiStatus
  }

  // Extension review (if applicable)
  if (hasExtension && !config.nonInteractive) {
    const extKey = await prompt(rl!, "[Extension] Result (p/f/s): ")
    result.extension = extKey === "p" ? "pass" : extKey === "f" ? "fail" : "skip"
  }

  // Collect notes if failed
  if (!config.nonInteractive) {
    if (result.webui === "fail" || result.extension === "fail") {
      const notes = await prompt(
        rl!,
        "Enter failure notes (or press Enter to skip): "
      )
      if (notes) {
        result.notes = notes
      }
    }
  }

  // Display result summary
  console.log("\n--- Result ---")
  console.log(`WebUI: ${result.webui?.toUpperCase() || "N/A"}`)
  if (hasExtension) {
    console.log(`Extension: ${result.extension?.toUpperCase() || "N/A"}`)
  }
  if (result.notes) {
    console.log(`Notes: ${result.notes}`)
  }

  return result
}

// ═══════════════════════════════════════════════════════════════════════════
// Main
// ═══════════════════════════════════════════════════════════════════════════

async function main(): Promise<void> {
  const config = parseArgs()
  const rl = config.nonInteractive ? null : createReadlineInterface()

  console.log("\n" + "═".repeat(70))
  console.log("    Interactive Page Review Session")
  console.log("═".repeat(70))
  console.log(`WebUI URL:     ${config.webuiUrl}`)
  console.log(`Backend URL:   ${config.backendUrl}`)
  console.log(`Output:        ${config.outputPath}`)
  console.log(`WebUI Only:    ${config.webuiOnly}`)
  console.log(`Auto Mode:     ${config.nonInteractive}`)
  console.log(`Total Pages:   ${TOTAL_PAGE_COUNT}`)
  console.log("═".repeat(70) + "\n")

  // Load existing results if resuming
  let session: ReviewSession
  if (config.resume) {
    const existing = loadExistingResults(config.outputPath)
    if (existing) {
      session = existing
      console.log(`Resuming from previous session (${session.results.length} pages reviewed)`)
    } else {
      session = {
        sessionStart: new Date().toISOString(),
        backend: config.backendUrl,
        webuiUrl: config.webuiUrl,
        lastReviewedPath: null,
        results: [],
        summary: { total: 0, passed: 0, failed: 0, skipped: 0 }
      }
    }
  } else {
    session = {
      sessionStart: new Date().toISOString(),
      backend: config.backendUrl,
      webuiUrl: config.webuiUrl,
      lastReviewedPath: null,
      results: [],
      summary: { total: 0, passed: 0, failed: 0, skipped: 0 }
    }
  }

  // Get pages to review
  const allPages = [...PAGE_MAPPINGS, ...WEBUI_ONLY_PAGES, ...EXTENSION_ONLY_PAGES]
  const reviewedPaths = new Set(session.results.map((r) => r.path))

  // Filter by session if specified
  let pagesToReview = allPages
  if (config.startSession > 1) {
    const sessionPages: PageMapping[] = []
    for (let s = config.startSession as number; s <= 7; s++) {
      sessionPages.push(...getPagesBySession(s as ReviewPriority))
    }
    pagesToReview = sessionPages
  }

  // Filter already reviewed pages if resuming
  if (config.resume) {
    pagesToReview = pagesToReview.filter(
      (p) => !reviewedPaths.has(getPageKey(p))
    )
  }

  console.log(`Pages to review: ${pagesToReview.length}`)

  // Setup browser
  console.log("\nLaunching browser...")
  const { browser, context } = await setupBrowser(config)

  await seedExtensionConfig(context, config)

  if (!config.webuiOnly && config.extensionPath && !config.extensionId) {
    config.extensionId = await resolveExtensionId(context)
    if (!config.extensionId && !config.nonInteractive) {
      const manualId = await prompt(
        rl!,
        "Extension ID not detected. Enter extension ID (or press Enter to skip extension review): "
      )
      config.extensionId = manualId || null
    }
    if (!config.extensionId) {
      console.log("Skipping extension review (no extension ID provided).")
    }
  }

  const webuiPage = await context.newPage()
  await seedAuth(webuiPage, config)

  // Extension page (if applicable)
  let extensionPage: Page | null = null
  if (!config.webuiOnly && config.extensionPath && config.extensionId) {
    extensionPage = await context.newPage()
    console.log("Extension loaded (will open in separate tab)")
  }

  // Wait for user to be ready
  if (!config.nonInteractive) {
    await waitForKeypress(rl!, "\nPress Enter when ready to start review...")
  }

  // Review each page
  for (let i = 0; i < pagesToReview.length; i++) {
    const mapping = pagesToReview[i]

    console.log(`\nProgress: ${i + 1}/${pagesToReview.length}`)

    const result = await reviewPage(
      webuiPage,
      extensionPage,
      mapping,
      config,
      rl
    )

    session.results.push(result)
    session.lastReviewedPath = getPageKey(mapping)

    // Save after each page
    saveResults(config.outputPath, session)
    console.log(`\nResults saved to ${config.outputPath}`)

    // Ask to continue
    if (!config.nonInteractive && i < pagesToReview.length - 1) {
      const continueKey = await prompt(
        rl!,
        "\nPress Enter to continue, or 'q' to quit: "
      )
      if (continueKey.toLowerCase() === "q") {
        console.log("Stopping review session...")
        break
      }
    }
  }

  // Final summary
  console.log("\n" + "═".repeat(70))
  console.log("    Review Session Complete")
  console.log("═".repeat(70))
  console.log(`Total reviewed: ${session.summary.total}`)
  console.log(`Passed:         ${session.summary.passed}`)
  console.log(`Failed:         ${session.summary.failed}`)
  console.log(`Skipped:        ${session.summary.skipped}`)
  console.log(`Results saved:  ${config.outputPath}`)
  console.log("═".repeat(70) + "\n")

  // Show failed pages
  const failedPages = session.results.filter(
    (r) => r.webui === "fail" || r.extension === "fail"
  )
  if (failedPages.length > 0) {
    console.log("Failed pages:")
    failedPages.forEach((p) => {
      console.log(`  - ${p.name} (${p.path})`)
      if (p.notes) {
        console.log(`    Notes: ${p.notes}`)
      }
    })
  }

  // Cleanup
  await browser.close()
  rl?.close()
}

// Run if executed directly
main().catch((err) => {
  console.error("Error:", err)
  process.exit(1)
})
