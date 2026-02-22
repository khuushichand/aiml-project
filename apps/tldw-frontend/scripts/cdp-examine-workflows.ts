#!/usr/bin/env npx tsx
/**
 * CDP Workflow Examination Script
 *
 * Walks through four frontend workflows on both the Next.js web UI and the
 * browser extension, capturing screenshots, network traffic, DOM snapshots,
 * and console output at each step.
 *
 * Usage:
 *   npx tsx scripts/cdp-examine-workflows.ts               # both targets
 *   npx tsx scripts/cdp-examine-workflows.ts --target web   # web UI only
 *   npx tsx scripts/cdp-examine-workflows.ts --target ext   # extension only
 */
import puppeteer, {
  type Browser,
  type Page,
  type HTTPRequest,
  type HTTPResponse,
  type ConsoleMessage,
} from "puppeteer"
import * as fs from "fs"
import * as path from "path"
import { execSync } from "child_process"
import * as http from "http"

// ─── Configuration ────────────────────────────────────────────────────────────

const CONFIG = {
  serverUrl: process.env.TLDW_SERVER_URL || "http://127.0.0.1:8000",
  webUrl: process.env.TLDW_WEB_URL || "http://localhost:3000",
  apiKey: process.env.TLDW_API_KEY || "THIS-IS-A-SECURE-KEY-123-FAKE-KEY",
  timeout: 30_000,
  screenshotDelay: 500,
  headless: process.env.CDP_HEADLESS !== "false",
  extensionBuildDir: path.resolve(__dirname, "../../extension/.output/chrome-mv3"),
  artifactsDir: path.resolve(__dirname, "../cdp-artifacts"),
}

type Target = "web" | "extension"
type WorkflowName = "chat" | "media" | "prompts" | "characters"

interface StepResult {
  step: number
  name: string
  screenshot?: string
  error?: string
  timestamp: string
}

interface WorkflowResult {
  workflow: WorkflowName
  target: Target
  steps: StepResult[]
  networkLog: NetworkEntry[]
  consoleLog: ConsoleEntry[]
  passed: boolean
  error?: string
}

interface NetworkEntry {
  type: "request" | "response"
  url: string
  method?: string
  status?: number
  body?: string | null
  timestamp: string
}

interface ConsoleEntry {
  type: string
  text: string
  timestamp: string
}

interface Summary {
  startedAt: string
  completedAt: string
  targets: Target[]
  results: WorkflowResult[]
}

// ─── Benign Patterns ──────────────────────────────────────────────────────────

const BENIGN_PATTERNS = [
  /ResizeObserver loop/,
  /Non-Error promise rejection/,
  /net::ERR_ABORTED/,
  /chrome-extension/,
  /Download the React DevTools/,
  /Fast Refresh/,
  /\[HMR\]/,
  /favicon\.ico.*404/,
  /Failed to load source map/,
  /Warning.*findDOMNode is deprecated/,
  /Hydration failed/,
  /There was an error while hydrating/,
  /\[mcp-init\]/,
  /\[mcp-static\]/,
  /CONNECTION_DEBUG/,
]

function isBenign(text: string): boolean {
  return BENIGN_PATTERNS.some((p) => p.test(text))
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function ensureDir(dirPath: string): void {
  fs.mkdirSync(dirPath, { recursive: true })
}

function timestamp(): string {
  return new Date().toISOString()
}

async function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}

/** Seed auth config into localStorage before page loads */
async function seedAuth(page: Page): Promise<void> {
  await page.evaluateOnNewDocument(
    (cfg: { serverUrl: string }) => {
      try {
        localStorage.setItem(
          "tldwConfig",
          JSON.stringify({ serverUrl: cfg.serverUrl, authMode: "single-user" })
        )
      } catch {}
      try {
        localStorage.setItem("__tldw_first_run_complete", "true")
      } catch {}
      try {
        localStorage.setItem("__tldw_allow_offline", "true")
      } catch {}
    },
    { serverUrl: CONFIG.serverUrl }
  )
}

/** Wait for connection store to report connected */
async function waitForConnection(page: Page, timeoutMs = 20_000): Promise<void> {
  try {
    await page.waitForFunction(
      () => {
        const store = (window as any).__tldw_useConnectionStore
        const state = store?.getState?.()?.state
        return state?.isConnected === true && state?.phase === "connected"
      },
      { timeout: timeoutMs }
    )
  } catch {
    console.warn("  [warn] Connection wait timed out — continuing anyway")
  }
}

/** Capture a screenshot */
async function captureStep(
  page: Page,
  dir: string,
  stepNum: number,
  name: string
): Promise<string> {
  const filename = `${String(stepNum).padStart(2, "0")}-${name}.png`
  const filepath = path.join(dir, filename)
  await delay(CONFIG.screenshotDelay)
  await page.screenshot({ path: filepath, fullPage: true })
  return filename
}

/** Wait for a selector with timeout, return true if found */
async function waitForSelector(
  page: Page,
  selector: string,
  timeoutMs = 10_000
): Promise<boolean> {
  try {
    await page.waitForSelector(selector, { visible: true, timeout: timeoutMs })
    return true
  } catch {
    return false
  }
}

/** Try multiple selectors, return the first one that matches */
async function findFirst(
  page: Page,
  selectors: string[],
  timeoutMs = 5_000
): Promise<string | null> {
  for (const sel of selectors) {
    try {
      const el = await page.$(sel)
      if (el) {
        const visible = await el.boundingBox()
        if (visible) return sel
      }
    } catch {}
  }
  // Wait a bit and retry
  await delay(1000)
  for (const sel of selectors) {
    try {
      await page.waitForSelector(sel, { visible: true, timeout: timeoutMs })
      return sel
    } catch {}
  }
  return null
}

/** Type into an input found via one of several selectors */
async function typeInto(
  page: Page,
  selectors: string[],
  text: string
): Promise<boolean> {
  const sel = await findFirst(page, selectors)
  if (!sel) return false
  await page.click(sel)
  await page.type(sel, text, { delay: 30 })
  return true
}

/** Click the first matching selector */
async function clickFirst(
  page: Page,
  selectors: string[]
): Promise<boolean> {
  const sel = await findFirst(page, selectors)
  if (!sel) return false
  await page.click(sel)
  return true
}

/** Click a button matching text content */
async function clickButtonByText(
  page: Page,
  textPattern: RegExp
): Promise<boolean> {
  const buttons = await page.$$("button")
  for (const btn of buttons) {
    const text = await btn.evaluate((el) => el.textContent || "")
    if (textPattern.test(text)) {
      const box = await btn.boundingBox()
      if (box) {
        await btn.click()
        return true
      }
    }
  }
  return false
}

// ─── Network & Console Loggers ────────────────────────────────────────────────

function createNetworkLogger(page: Page): NetworkEntry[] {
  const log: NetworkEntry[] = []

  page.on("request", (req: HTTPRequest) => {
    if (req.url().includes("/api/v1/") || req.url().includes("/api/")) {
      log.push({
        type: "request",
        url: req.url(),
        method: req.method(),
        body: req.postData() ?? null,
        timestamp: timestamp(),
      })
    }
  })

  page.on("response", (res: HTTPResponse) => {
    if (res.url().includes("/api/v1/") || res.url().includes("/api/")) {
      log.push({
        type: "response",
        url: res.url(),
        status: res.status(),
        timestamp: timestamp(),
      })
    }
  })

  return log
}

function createConsoleLogger(page: Page): ConsoleEntry[] {
  const log: ConsoleEntry[] = []

  page.on("console", (msg: ConsoleMessage) => {
    log.push({
      type: msg.type(),
      text: msg.text(),
      timestamp: timestamp(),
    })
  })

  page.on("pageerror", (err: Error) => {
    log.push({
      type: "pageerror",
      text: `${err.message}\n${err.stack || ""}`,
      timestamp: timestamp(),
    })
  })

  return log
}

// ─── Workflow: Chat ───────────────────────────────────────────────────────────

async function examineChat(
  page: Page,
  dir: string,
  _target: Target
): Promise<StepResult[]> {
  const steps: StepResult[] = []
  let stepNum = 0

  const addStep = async (name: string, fn: () => Promise<void>) => {
    stepNum++
    try {
      await fn()
      const screenshot = await captureStep(page, dir, stepNum, name)
      steps.push({ step: stepNum, name, screenshot, timestamp: timestamp() })
      console.log(`    [${stepNum}] ${name} ✓`)
    } catch (err: any) {
      const screenshot = await captureStep(page, dir, stepNum, `${name}-error`).catch(() => undefined)
      steps.push({ step: stepNum, name, screenshot, error: err.message, timestamp: timestamp() })
      console.log(`    [${stepNum}] ${name} ✗ — ${err.message}`)
    }
  }

  // Step 1: Navigate to chat
  await addStep("page-loaded", async () => {
    await page.goto(`${CONFIG.webUrl}/chat`, {
      waitUntil: "domcontentloaded",
      timeout: CONFIG.timeout,
    })
    await delay(2000)
  })

  // Step 2: Wait for connection
  await addStep("connection-ready", async () => {
    await waitForConnection(page)
  })

  // Step 3: Verify chat input
  await addStep("chat-ready", async () => {
    const found = await findFirst(page, [
      "#textarea-message",
      "[data-testid='chat-input']",
      "textarea[placeholder]",
    ])
    if (!found) throw new Error("Chat input not found")
  })

  // Step 4: Model selector
  await addStep("model-selector", async () => {
    const clicked = await clickFirst(page, [
      "[data-testid='model-selector']",
      "[data-testid='model-select-trigger']",
    ])
    if (!clicked) {
      console.log("      Model selector not clickable, skipping dropdown")
    }
    await delay(1000)
  })

  // Close any dropdown by pressing escape
  await page.keyboard.press("Escape").catch(() => {})
  await delay(500)

  // Step 5: Type message
  await addStep("message-typed", async () => {
    const typed = await typeInto(
      page,
      ["#textarea-message", "[data-testid='chat-input']", "textarea[placeholder]"],
      "Hello, what is 2+2?"
    )
    if (!typed) throw new Error("Could not type message")
  })

  // Step 6: Send message
  await addStep("message-sent", async () => {
    const sent =
      (await clickFirst(page, [
        "[data-testid='send-button']",
        "button[aria-label*='send' i]",
      ])) ||
      (await clickButtonByText(page, /send/i))

    if (!sent) {
      // Fallback: press Enter
      await page.keyboard.press("Enter")
    }
    await delay(1000)
  })

  // Step 7: Monitor streaming
  await addStep("streaming", async () => {
    // Wait briefly for streaming to start
    await delay(3000)
  })

  // Step 8: Wait for response
  await addStep("response-received", async () => {
    const found = await waitForSelector(
      page,
      "[data-role='assistant'], [data-message-role='assistant'], .assistant-message",
      60_000
    )
    if (!found) {
      console.log("      No assistant message appeared — server may be offline or no model configured")
    }
    await delay(2000)
  })

  // Step 9: Follow-up message
  await addStep("multi-turn", async () => {
    const typed = await typeInto(
      page,
      ["#textarea-message", "[data-testid='chat-input']", "textarea[placeholder]"],
      "Multiply by 3"
    )
    if (typed) {
      const sent =
        (await clickFirst(page, [
          "[data-testid='send-button']",
          "button[aria-label*='send' i]",
        ])) ||
        (await clickButtonByText(page, /send/i))

      if (!sent) await page.keyboard.press("Enter")
      await delay(5000)
    } else {
      console.log("      Could not type follow-up")
    }
  })

  // Step 10: New chat
  await addStep("new-chat", async () => {
    const clicked =
      (await clickButtonByText(page, /new chat|new conversation/i)) ||
      (await clickFirst(page, [
        "[data-testid='new-chat-button']",
        "button[aria-label*='new' i]",
      ]))
    if (!clicked) {
      // Try keyboard shortcut
      await page.keyboard.down("Meta")
      await page.keyboard.press("n")
      await page.keyboard.up("Meta")
    }
    await delay(2000)
  })

  return steps
}

// ─── Workflow: Media ──────────────────────────────────────────────────────────

async function examineMedia(
  page: Page,
  dir: string,
  _target: Target
): Promise<StepResult[]> {
  const steps: StepResult[] = []
  let stepNum = 0

  const addStep = async (name: string, fn: () => Promise<void>) => {
    stepNum++
    try {
      await fn()
      const screenshot = await captureStep(page, dir, stepNum, name)
      steps.push({ step: stepNum, name, screenshot, timestamp: timestamp() })
      console.log(`    [${stepNum}] ${name} ✓`)
    } catch (err: any) {
      const screenshot = await captureStep(page, dir, stepNum, `${name}-error`).catch(() => undefined)
      steps.push({ step: stepNum, name, screenshot, error: err.message, timestamp: timestamp() })
      console.log(`    [${stepNum}] ${name} ✗ — ${err.message}`)
    }
  }

  // Step 1: Navigate to media
  await addStep("media-page", async () => {
    await page.goto(`${CONFIG.webUrl}/media`, {
      waitUntil: "domcontentloaded",
      timeout: CONFIG.timeout,
    })
    await delay(3000)
    await waitForConnection(page)
  })

  // Step 2: Open Quick Ingest
  await addStep("quick-ingest-modal", async () => {
    let opened =
      (await clickFirst(page, [
        "[data-testid='open-quick-ingest']",
      ])) ||
      (await clickButtonByText(page, /quick ingest/i))

    if (!opened) {
      // Dispatch custom event
      await page.evaluate(() => {
        window.dispatchEvent(new CustomEvent("tldw:open-quick-ingest"))
      })
    }
    await delay(2000)
  })

  // Step 3: Verify modal tabs
  await addStep("modal-tabs", async () => {
    const modalVisible = await waitForSelector(
      page,
      ".quick-ingest-modal .ant-modal-content, .ant-modal-content",
      10_000
    )
    if (!modalVisible) {
      console.log("      Quick ingest modal not visible")
    }
    await delay(1000)
  })

  // Step 4: Enter URL
  await addStep("url-entered", async () => {
    const typed = await typeInto(
      page,
      [
        "[data-testid='url-input']",
        "input[placeholder*='url' i]",
        "input[placeholder*='URL' i]",
        "input[placeholder*='paste' i]",
      ],
      "https://example.com"
    )
    if (!typed) {
      console.log("      Could not find URL input in Quick Ingest modal")
    }
  })

  // Step 5: Click process/add
  await addStep("processing", async () => {
    const clicked =
      (await clickButtonByText(page, /add|process|ingest|submit/i)) ||
      (await clickFirst(page, ["button[type='submit']"]))
    if (!clicked) {
      console.log("      Could not click process button")
    }
    await delay(3000)
  })

  // Step 6: Progress indicators
  await addStep("progress", async () => {
    await delay(3000)
    // Check for progress bar
    const hasProgress = await page.$(".ant-progress, [data-testid='progress-bar'], .progress")
    if (hasProgress) {
      console.log("      Progress indicator found")
    }
  })

  // Step 7: Close modal, check list
  await addStep("media-list", async () => {
    // Close modal if still open
    await page.keyboard.press("Escape").catch(() => {})
    await delay(1000)
    // Check for close button
    await clickFirst(page, [".ant-modal-close"]).catch(() => {})
    await delay(2000)
  })

  // Step 8: Click media item
  await addStep("media-detail", async () => {
    const hasItem = await page.$(".ant-table-row, [data-testid='media-item'], .media-item")
    if (hasItem) {
      await hasItem.click()
      await delay(2000)
    } else {
      console.log("      No media items in list")
    }
  })

  // Step 9: Search
  await addStep("search-results", async () => {
    const typed = await typeInto(
      page,
      [
        "[data-testid='search-input']",
        "input[placeholder*='search' i]",
        "input[placeholder*='filter' i]",
      ],
      "example"
    )
    if (typed) {
      await page.keyboard.press("Enter")
      await delay(2000)
    }
  })

  return steps
}

// ─── Workflow: Prompts ────────────────────────────────────────────────────────

async function examinePrompts(
  page: Page,
  dir: string,
  _target: Target
): Promise<StepResult[]> {
  const steps: StepResult[] = []
  let stepNum = 0

  const addStep = async (name: string, fn: () => Promise<void>) => {
    stepNum++
    try {
      await fn()
      const screenshot = await captureStep(page, dir, stepNum, name)
      steps.push({ step: stepNum, name, screenshot, timestamp: timestamp() })
      console.log(`    [${stepNum}] ${name} ✓`)
    } catch (err: any) {
      const screenshot = await captureStep(page, dir, stepNum, `${name}-error`).catch(() => undefined)
      steps.push({ step: stepNum, name, screenshot, error: err.message, timestamp: timestamp() })
      console.log(`    [${stepNum}] ${name} ✗ — ${err.message}`)
    }
  }

  // Step 1: Navigate
  await addStep("prompts-page", async () => {
    await page.goto(`${CONFIG.webUrl}/prompts`, {
      waitUntil: "domcontentloaded",
      timeout: CONFIG.timeout,
    })
    await delay(3000)
    await waitForConnection(page)
  })

  // Step 2: Verify tab bar
  await addStep("tab-bar", async () => {
    const found = await waitForSelector(
      page,
      "[data-testid='prompts-segmented'], .ant-segmented",
      10_000
    )
    if (!found) console.log("      Segmented tab bar not found")
  })

  // Step 3: Click Add
  await addStep("drawer-open", async () => {
    const clicked =
      (await clickFirst(page, ["[data-testid='prompts-add']"])) ||
      (await clickButtonByText(page, /add|create|new/i))
    if (!clicked) throw new Error("Add prompt button not found")
    await delay(1500)
  })

  // Step 4 + 5 + 6: Fill form
  await addStep("form-filled", async () => {
    // Name
    const nameTyped = await typeInto(
      page,
      ["[data-testid='prompt-drawer-name']", "input[placeholder*='name' i]", "#prompt-name"],
      "CDP Test Prompt"
    )
    if (!nameTyped) console.log("      Could not type prompt name")

    // System prompt
    const systemSel = await findFirst(page, [
      "[data-testid='prompt-drawer-system']",
      "textarea[placeholder*='system' i]",
      "#prompt-system",
    ])
    if (systemSel) {
      await page.click(systemSel)
      await page.type(systemSel, "You are a helpful test assistant.", { delay: 20 })
    }

    // User prompt
    const userSel = await findFirst(page, [
      "[data-testid='prompt-drawer-user']",
      "textarea[placeholder*='user' i]",
      "#prompt-user",
    ])
    if (userSel) {
      await page.click(userSel)
      await page.type(userSel, "Tell me about {{topic}}", { delay: 20 })
    }
  })

  // Step 7: Save
  await addStep("prompt-created", async () => {
    const saved =
      (await clickButtonByText(page, /save|create|submit/i)) ||
      (await clickFirst(page, ["button[type='submit']"]))
    if (!saved) console.log("      Save button not found")
    await delay(2000)
  })

  // Step 8: Search
  await addStep("search-result", async () => {
    const typed = await typeInto(
      page,
      ["[data-testid='prompts-search']", "input[placeholder*='search' i]"],
      "CDP Test"
    )
    if (typed) await delay(1500)
  })

  // Step 9: Edit
  await addStep("edit-drawer", async () => {
    // Try clicking edit button — testids are dynamic prompt-edit-{id}
    const editBtn = await page.$("[data-testid^='prompt-edit-']")
    if (editBtn) {
      await editBtn.click()
      await delay(1500)
    } else {
      // Try table row click
      const row = await page.$(".ant-table-row")
      if (row) {
        await row.click()
        await delay(1500)
      } else {
        console.log("      No prompt to edit")
      }
    }
  })

  // Step 10: Modify and save
  await addStep("prompt-edited", async () => {
    const nameInput = await findFirst(page, [
      "[data-testid='prompt-drawer-name']",
      "input[placeholder*='name' i]",
    ])
    if (nameInput) {
      // Clear and retype
      await page.click(nameInput, { clickCount: 3 })
      await page.type(nameInput, "CDP Test Prompt (Edited)", { delay: 20 })
    }
    const saved = await clickButtonByText(page, /save|update|submit/i)
    if (saved) await delay(1500)
  })

  // Step 11: Favorite
  await addStep("favorited", async () => {
    const favBtn = await page.$("[data-testid^='prompt-favorite-']")
    if (favBtn) {
      await favBtn.click()
      await delay(1000)
    } else {
      console.log("      Favorite button not found")
    }
  })

  // Step 12: Export
  await addStep("export", async () => {
    const clicked =
      (await clickFirst(page, ["[data-testid='prompts-export']"])) ||
      (await clickButtonByText(page, /export/i))
    if (!clicked) console.log("      Export button not found")
    await delay(1000)
  })

  // Step 13: Delete
  await addStep("deleted", async () => {
    // Clear search first
    const searchInput = await page.$("[data-testid='prompts-search'], input[placeholder*='search' i]")
    if (searchInput) {
      await searchInput.click({ clickCount: 3 })
      await page.keyboard.press("Backspace")
      await delay(1000)
    }

    // Look for delete on the test prompt row
    const deleteBtn = await page.$("[data-testid^='prompt-delete-'], button[aria-label*='delete' i]")
    if (deleteBtn) {
      await deleteBtn.click()
      await delay(500)
      // Confirm deletion
      await clickButtonByText(page, /confirm|yes|ok|delete/i)
      await delay(1500)
    } else {
      console.log("      Delete button not found")
    }
  })

  // Step 14: Switch to Trash
  await addStep("trash-tab", async () => {
    const trashClicked =
      (await clickFirst(page, ["[data-testid='prompts-trash']"])) ||
      (await clickButtonByText(page, /trash|deleted/i))
    if (!trashClicked) console.log("      Trash tab not found")
    await delay(1500)
  })

  // Step 15: Verify trash
  await addStep("trash-verified", async () => {
    // Check if a table row exists in trash
    const rows = await page.$$(".ant-table-row, [data-testid='prompts-trash-table'] tr")
    console.log(`      Found ${rows.length} items in trash`)
  })

  return steps
}

// ─── Workflow: Characters ─────────────────────────────────────────────────────

async function examineCharacters(
  page: Page,
  dir: string,
  _target: Target
): Promise<StepResult[]> {
  const steps: StepResult[] = []
  let stepNum = 0

  const addStep = async (name: string, fn: () => Promise<void>) => {
    stepNum++
    try {
      await fn()
      const screenshot = await captureStep(page, dir, stepNum, name)
      steps.push({ step: stepNum, name, screenshot, timestamp: timestamp() })
      console.log(`    [${stepNum}] ${name} ✓`)
    } catch (err: any) {
      const screenshot = await captureStep(page, dir, stepNum, `${name}-error`).catch(() => undefined)
      steps.push({ step: stepNum, name, screenshot, error: err.message, timestamp: timestamp() })
      console.log(`    [${stepNum}] ${name} ✗ — ${err.message}`)
    }
  }

  // Step 1: Navigate
  await addStep("characters-page", async () => {
    await page.goto(`${CONFIG.webUrl}/characters`, {
      waitUntil: "domcontentloaded",
      timeout: CONFIG.timeout,
    })
    await delay(3000)
    await waitForConnection(page)
  })

  // Step 2: Capabilities check
  await addStep("capabilities-check", async () => {
    // Wait for the page to load and any capabilities check to resolve
    await delay(2000)
  })

  // Step 3: Click "New character"
  await addStep("create-modal", async () => {
    const clicked =
      (await clickButtonByText(page, /new character|create character/i)) ||
      (await clickFirst(page, [
        "button[aria-label*='new' i]",
        "button[aria-label*='create' i]",
      ]))
    if (!clicked) throw new Error("New character button not found")
    await delay(2000)
  })

  // Step 4 + 5 + 6 + 7: Fill form
  await addStep("form-filled", async () => {
    // Name field
    const nameInputs = [
      "input[placeholder*='name' i]",
      "#character-name",
      ".ant-form-item input",
      ".ant-modal input",
    ]
    const nameTyped = await typeInto(page, nameInputs, "CDP Test Character")
    if (!nameTyped) console.log("      Could not type character name")

    // System prompt / personality
    const textareas = await page.$$(".ant-modal textarea, .ant-form-item textarea")
    if (textareas.length >= 1) {
      await textareas[0].click()
      await textareas[0].type("You are a helpful test character created by CDP examination.", { delay: 15 })
    }

    // Greeting (second textarea if present)
    if (textareas.length >= 2) {
      await textareas[1].click()
      await textareas[1].type("Hello! I'm a test character. How can I help?", { delay: 15 })
    }

    // Description (third textarea or a shorter input)
    if (textareas.length >= 3) {
      await textareas[2].click()
      await textareas[2].type("A test character for CDP workflow examination", { delay: 15 })
    }

    // Tags — look for tag input
    const tagInput = await page.$("input[placeholder*='tag' i], .ant-select-selection-search-input")
    if (tagInput) {
      await tagInput.click()
      await tagInput.type("test")
      await page.keyboard.press("Enter")
      await delay(500)
    }
  })

  // Step 8: Submit
  await addStep("character-created", async () => {
    const submitted =
      (await clickButtonByText(page, /save|create|submit|ok/i)) ||
      (await clickFirst(page, [".ant-modal-footer button.ant-btn-primary", "button[type='submit']"]))
    if (!submitted) console.log("      Submit button not found")
    await delay(3000)
  })

  // Step 9: Verify in table
  await addStep("in-table", async () => {
    const row = await page.$(".ant-table-row")
    if (row) {
      const text = await row.evaluate((el) => el.textContent || "")
      console.log(`      First row content: ${text.substring(0, 80)}...`)
    } else {
      console.log("      No table rows found")
    }
  })

  // Step 10: Toggle Gallery view
  await addStep("gallery-view", async () => {
    const galleryClicked =
      (await clickButtonByText(page, /gallery|grid|card/i)) ||
      (await clickFirst(page, [
        "button[aria-label*='gallery' i]",
        "button[aria-label*='grid' i]",
        ".ant-radio-button-wrapper:nth-child(2)",
        ".ant-segmented-item:nth-child(2)",
      ]))
    if (!galleryClicked) console.log("      Gallery toggle not found")
    await delay(1500)
  })

  // Step 11: Edit
  await addStep("edit-modal", async () => {
    // Switch back to table first
    const tableClicked =
      (await clickButtonByText(page, /table|list/i)) ||
      (await clickFirst(page, [
        ".ant-radio-button-wrapper:first-child",
        ".ant-segmented-item:first-child",
      ]))
    if (tableClicked) await delay(1000)

    // Click edit on a row
    const editClicked =
      (await clickButtonByText(page, /edit/i)) ||
      (await clickFirst(page, [
        "button[aria-label*='edit' i]",
        ".ant-table-row button:first-child",
      ]))
    if (!editClicked) console.log("      Edit button not found")
    await delay(2000)
  })

  // Step 12: Modify description, save
  await addStep("edited", async () => {
    const textareas = await page.$$(".ant-modal textarea, .ant-form-item textarea")
    for (const ta of textareas) {
      const val = await ta.evaluate((el: HTMLTextAreaElement) => el.value)
      if (val.includes("CDP") || val.includes("test character")) {
        await ta.click({ clickCount: 3 })
        await ta.type("Modified by CDP examination script", { delay: 15 })
        break
      }
    }

    const saved =
      (await clickButtonByText(page, /save|update|ok/i)) ||
      (await clickFirst(page, [".ant-modal-footer button.ant-btn-primary"]))
    if (saved) await delay(2000)
  })

  // Step 13: Export
  await addStep("export", async () => {
    // Look for export action (might be in a dropdown or action column)
    const exportClicked =
      (await clickButtonByText(page, /export/i)) ||
      (await clickFirst(page, ["button[aria-label*='export' i]"]))
    if (!exportClicked) {
      // Try opening actions dropdown first
      const actionsBtn = await page.$(".ant-table-row button[aria-label*='more' i], .ant-dropdown-trigger")
      if (actionsBtn) {
        await actionsBtn.click()
        await delay(500)
        await clickButtonByText(page, /export/i)
      } else {
        console.log("      Export button not found")
      }
    }
    await delay(1000)
  })

  // Step 14: Delete + confirm
  await addStep("deleted", async () => {
    const deleteClicked =
      (await clickButtonByText(page, /delete/i)) ||
      (await clickFirst(page, ["button[aria-label*='delete' i]"]))
    if (deleteClicked) {
      await delay(500)
      // Confirm deletion
      const confirmed =
        (await clickButtonByText(page, /confirm|yes|ok|delete/i)) ||
        (await clickFirst(page, [".ant-popconfirm-buttons button.ant-btn-primary", ".ant-btn-dangerous"]))
      if (confirmed) await delay(2000)
    } else {
      console.log("      Delete button not found")
    }
  })

  return steps
}

// ─── Target Runners ───────────────────────────────────────────────────────────

const WORKFLOW_MAP: Record<
  WorkflowName,
  (page: Page, dir: string, target: Target) => Promise<StepResult[]>
> = {
  chat: examineChat,
  media: examineMedia,
  prompts: examinePrompts,
  characters: examineCharacters,
}

async function runWorkflows(
  browser: Browser,
  target: Target,
  baseDir: string
): Promise<WorkflowResult[]> {
  const results: WorkflowResult[] = []

  for (const [name, fn] of Object.entries(WORKFLOW_MAP) as [
    WorkflowName,
    typeof WORKFLOW_MAP[WorkflowName]
  ][]) {
    const workflowDir = path.join(baseDir, name)
    ensureDir(workflowDir)

    console.log(`\n  [${target}] Workflow: ${name}`)

    const page = await browser.newPage()
    await page.setViewport({ width: 1440, height: 900 })
    await seedAuth(page)

    const networkLog = createNetworkLogger(page)
    const consoleLog = createConsoleLogger(page)

    let steps: StepResult[] = []
    let passed = true
    let error: string | undefined

    try {
      steps = await fn(page, workflowDir, target)
    } catch (err: any) {
      passed = false
      error = err.message
      console.log(`    [FAIL] ${name}: ${err.message}`)
    }

    // Write logs
    fs.writeFileSync(
      path.join(workflowDir, "network.json"),
      JSON.stringify(networkLog, null, 2)
    )
    fs.writeFileSync(
      path.join(workflowDir, "console.json"),
      JSON.stringify(consoleLog, null, 2)
    )

    // Check for critical console errors
    const criticalErrors = consoleLog.filter(
      (c) => c.type === "pageerror" && !isBenign(c.text)
    )
    if (criticalErrors.length > 0) {
      console.log(`    [warn] ${criticalErrors.length} critical console error(s)`)
    }

    // Check for step errors
    const stepErrors = steps.filter((s) => s.error)
    if (stepErrors.length > 0) {
      passed = false
      error = `${stepErrors.length} step(s) failed`
    }

    results.push({
      workflow: name,
      target,
      steps,
      networkLog,
      consoleLog,
      passed,
      error,
    })

    await page.close()
  }

  return results
}

// ─── Web UI Target ────────────────────────────────────────────────────────────

async function runWebUI(): Promise<WorkflowResult[]> {
  console.log("\n=== Web UI Target ===")

  const browser = await puppeteer.launch({
    headless: CONFIG.headless,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--window-size=1440,900",
    ],
  })

  const webDir = path.join(CONFIG.artifactsDir, "web")
  ensureDir(webDir)

  try {
    return await runWorkflows(browser, "web", webDir)
  } finally {
    await browser.close()
  }
}

// ─── Extension Target ─────────────────────────────────────────────────────────

/**
 * Start a static file server for the extension build output.
 * - Serves extension files with correct MIME types
 * - Proxies /api/ requests to backend
 * - Patches the extension guard check in JS files
 */
async function startExtensionServer(
  buildDir: string
): Promise<{ url: string; close: () => Promise<void> }> {
  const MIME: Record<string, string> = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".map": "application/json; charset=utf-8",
    ".wasm": "application/wasm",
    ".mjs": "application/javascript; charset=utf-8",
  }

  const guard =
    'if(!(globalThis.chrome&&globalThis.chrome.runtime&&globalThis.chrome.runtime.id))throw new Error("This script should only be loaded in a browser extension.");'
  const replacement = `if(!(globalThis.chrome&&globalThis.chrome.runtime&&globalThis.chrome.runtime.id)){console.warn("[cdp-ext] mocking chrome runtime");if(typeof globalThis.__mcpEnsureExtensionEnv==='function'){globalThis.__mcpEnsureExtensionEnv();}else{globalThis.chrome=globalThis.chrome||{runtime:{}};globalThis.chrome.runtime.id=globalThis.chrome.runtime.id||'mock-runtime-id';globalThis.browser=globalThis.browser||{runtime:globalThis.chrome.runtime};}}`

  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url || "/", "http://localhost")

      // Proxy API requests
      if (url.pathname.startsWith("/api/")) {
        const target = new URL(req.url || "/", CONFIG.serverUrl)
        const proxyReq = http.request(
          target,
          { method: req.method, headers: req.headers },
          (proxyRes) => {
            res.writeHead(proxyRes.statusCode || 500, proxyRes.headers)
            proxyRes.pipe(res)
          }
        )
        proxyReq.on("error", (err) => {
          res.statusCode = 502
          res.end(`Proxy error: ${err.message}`)
        })
        req.pipe(proxyReq)
        return
      }

      let reqPath = decodeURIComponent(url.pathname)
      if (!reqPath || reqPath === "/") reqPath = "/index.html"
      if (reqPath.endsWith("/")) reqPath += "index.html"

      const filePath = path.join(buildDir, reqPath)
      const rel = path.relative(buildDir, filePath)
      if (rel.startsWith("..")) {
        res.statusCode = 403
        res.end("Forbidden")
        return
      }

      let data: Buffer
      try {
        data = fs.readFileSync(filePath)
      } catch {
        res.statusCode = 404
        res.end("Not found")
        return
      }

      const ext = path.extname(filePath).toLowerCase()

      // Patch extension guard in JS files
      if (ext === ".js" || ext === ".mjs") {
        let text = data.toString("utf8")
        if (text.includes("This script should only be loaded in a browser extension.")) {
          text = text.split(guard).join(replacement)
          data = Buffer.from(text, "utf8")
        }
      }

      res.setHeader("Content-Type", MIME[ext] || "application/octet-stream")
      res.end(data)
    } catch (err: any) {
      res.statusCode = 500
      res.end("Server error")
    }
  })

  return new Promise((resolve, reject) => {
    server.once("error", reject)
    server.listen(0, "127.0.0.1", () => {
      server.removeListener("error", reject)
      const addr = server.address()
      if (!addr || typeof addr === "string") {
        reject(new Error("Failed to get server address"))
        return
      }
      resolve({
        url: `http://127.0.0.1:${addr.port}`,
        close: () => new Promise<void>((r) => server.close(() => r())),
      })
    })
  })
}

/** Chrome extension init script — mocks chrome.* APIs */
function getExtensionInitScript(): string {
  return `
    (() => {
      const createEventDispatcher = () => {
        const listeners = new Set();
        return {
          addListener(l) { if (typeof l === 'function') listeners.add(l); },
          removeListener(l) { listeners.delete(l); },
          hasListener(l) { return listeners.has(l); },
          emit(...args) { for (const l of listeners) { try { l(...args); } catch (e) { console.error('[ext-mock] listener error', e); } } }
        };
      };
      const createStorageArea = (name, globalChanged) => {
        const store = new Map();
        const onChanged = createEventDispatcher();
        const emitChanges = (changes) => {
          if (!changes || Object.keys(changes).length === 0) return;
          onChanged.emit(changes, name);
          globalChanged?.emit(changes, name);
        };
        const normalizeKeys = (keys) => {
          if (keys === null || keys === undefined) return [];
          if (Array.isArray(keys)) return keys;
          if (typeof keys === 'string') return [keys];
          if (typeof keys === 'object') return Object.keys(keys);
          return [];
        };
        return {
          get(keys, cb) {
            const kl = normalizeKeys(keys);
            let res;
            if (kl.length === 0) { res = Object.fromEntries(store.entries()); }
            else { res = {}; for (const k of kl) { if (typeof keys === 'object' && !Array.isArray(keys)) { res[k] = store.has(k) ? store.get(k) : keys[k]; } else { res[k] = store.get(k); } } }
            cb?.(res); return Promise.resolve(res);
          },
          set(items, cb) {
            const changes = {};
            for (const [k, v] of Object.entries(items || {})) { const old = store.has(k) ? store.get(k) : undefined; store.set(k, v); changes[k] = { oldValue: old, newValue: v }; }
            emitChanges(changes); cb?.(); return Promise.resolve();
          },
          remove(keys, cb) {
            const kl = normalizeKeys(keys); const changes = {};
            for (const k of kl) { if (store.has(k)) { changes[k] = { oldValue: store.get(k), newValue: undefined }; store.delete(k); } }
            emitChanges(changes); cb?.(); return Promise.resolve();
          },
          clear(cb) {
            const changes = {};
            for (const [k, v] of store.entries()) { changes[k] = { oldValue: v, newValue: undefined }; }
            store.clear(); emitChanges(changes); cb?.(); return Promise.resolve();
          },
          onChanged
        };
      };
      const makeEvent = () => ({ addListener() {}, removeListener() {}, hasListener() { return false; } });
      const ensureExtensionEnv = () => {
        const runtime = globalThis.chrome?.runtime || {
          id: 'mock-runtime-id',
          getURL(p) { try { return new URL(p, location.origin).toString(); } catch { return p; } },
          sendMessage(m, cb) { cb?.(); return Promise.resolve(); },
          connect() { return { onMessage: makeEvent(), onDisconnect: makeEvent(), postMessage() {}, disconnect() {} }; },
          onMessage: makeEvent(), onConnect: makeEvent(), onInstalled: makeEvent()
        };
        runtime.onMessage = runtime.onMessage || makeEvent();
        runtime.onConnect = runtime.onConnect || makeEvent();
        runtime.onInstalled = runtime.onInstalled || makeEvent();
        runtime.reload = runtime.reload || (() => { console.info('[ext-mock] chrome.runtime.reload'); });
        runtime.connect = runtime.connect || (() => ({ onMessage: makeEvent(), onDisconnect: makeEvent(), postMessage() {}, disconnect() {} }));
        runtime.sendMessage = runtime.sendMessage || ((m, cb) => { cb?.(); return Promise.resolve(); });
        runtime.getURL = runtime.getURL || ((p) => { try { return new URL(p, location.origin).toString(); } catch { return p; } });
        const storageChanged = globalThis.chrome?.storage?.onChanged || createEventDispatcher();
        const storage = globalThis.chrome?.storage || {
          local: createStorageArea('local', storageChanged),
          sync: createStorageArea('sync', storageChanged),
          session: createStorageArea('session', storageChanged),
          onChanged: storageChanged
        };
        storage.onChanged = storage.onChanged || storageChanged;
        storage.local.onChanged = storage.local.onChanged || createEventDispatcher();
        storage.sync.onChanged = storage.sync.onChanged || createEventDispatcher();
        storage.session.onChanged = storage.session.onChanged || createEventDispatcher();
        const i18n = globalThis.chrome?.i18n || { getMessage(n) { return n; } };
        globalThis.chrome = { runtime, storage, i18n };
        if (!globalThis.chrome.runtime.id) globalThis.chrome.runtime.id = 'mock-runtime-id';
        globalThis.browser = globalThis.browser || {};
        globalThis.browser.runtime = globalThis.browser.runtime || globalThis.chrome.runtime;
        globalThis.browser.runtime.onMessage = globalThis.browser.runtime.onMessage || runtime.onMessage;
        globalThis.browser.runtime.onConnect = globalThis.browser.runtime.onConnect || runtime.onConnect;
        globalThis.browser.runtime.onInstalled = globalThis.browser.runtime.onInstalled || runtime.onInstalled;
        globalThis.browser.runtime.connect = globalThis.browser.runtime.connect || runtime.connect;
        globalThis.browser.runtime.sendMessage = globalThis.browser.runtime.sendMessage || runtime.sendMessage;
        globalThis.browser.runtime.reload = globalThis.browser.runtime.reload || runtime.reload;
        globalThis.browser.storage = globalThis.browser.storage || globalThis.chrome.storage;
        globalThis.browser.i18n = globalThis.browser.i18n || globalThis.chrome.i18n;
        globalThis.browser.tabs = globalThis.browser.tabs || { create() { return Promise.resolve({}); } };
      };
      ensureExtensionEnv();
      globalThis.__mcpEnsureExtensionEnv = ensureExtensionEnv;
    })();
  `
}

async function runExtension(): Promise<WorkflowResult[]> {
  console.log("\n=== Extension Target ===")

  // Verify extension build exists
  if (!fs.existsSync(CONFIG.extensionBuildDir)) {
    console.log("  Extension build not found. Building...")
    try {
      execSync("bun run build:chrome", {
        cwd: path.resolve(__dirname, "../../extension"),
        stdio: "inherit",
      })
    } catch (err: any) {
      console.error("  Failed to build extension:", err.message)
      return []
    }
  }

  if (!fs.existsSync(path.join(CONFIG.extensionBuildDir, "options.html"))) {
    console.error("  Extension build incomplete — missing options.html")
    return []
  }

  // Start static server for extension
  const staticServer = await startExtensionServer(CONFIG.extensionBuildDir)
  console.log(`  Extension static server at ${staticServer.url}`)

  // Write init script to a temp file
  const initScriptPath = path.join(CONFIG.artifactsDir, "extension-init.js")
  fs.writeFileSync(initScriptPath, getExtensionInitScript())

  const browser = await puppeteer.launch({
    headless: CONFIG.headless,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--window-size=1440,900",
    ],
  })

  const extDir = path.join(CONFIG.artifactsDir, "extension")
  ensureDir(extDir)

  // Override CONFIG.webUrl for extension target
  const originalWebUrl = CONFIG.webUrl
  CONFIG.webUrl = staticServer.url

  try {
    // For extension pages, we inject the init script and navigate to extension HTML
    const results: WorkflowResult[] = []

    for (const [wfName, fn] of Object.entries(WORKFLOW_MAP) as [
      WorkflowName,
      typeof WORKFLOW_MAP[WorkflowName]
    ][]) {
      const workflowDir = path.join(extDir, wfName)
      ensureDir(workflowDir)

      console.log(`\n  [extension] Workflow: ${wfName}`)

      const page = await browser.newPage()
      await page.setViewport({ width: 1440, height: 900 })

      // Inject extension mock before page loads
      await page.evaluateOnNewDocument(getExtensionInitScript())

      // Seed auth with extension server URL
      await page.evaluateOnNewDocument(
        (cfg: { serverUrl: string; staticUrl: string }) => {
          try {
            localStorage.setItem(
              "tldwConfig",
              JSON.stringify({ serverUrl: cfg.serverUrl, authMode: "single-user" })
            )
          } catch {}
          try { localStorage.setItem("__tldw_first_run_complete", "true") } catch {}
          try { localStorage.setItem("__tldw_allow_offline", "true") } catch {}
        },
        { serverUrl: CONFIG.serverUrl, staticUrl: staticServer.url }
      )

      const networkLog = createNetworkLogger(page)
      const consoleLog = createConsoleLogger(page)

      let steps: StepResult[] = []
      let passed = true
      let error: string | undefined

      try {
        // Map web routes to extension entry points
        const extPage = getExtensionPage(wfName)

        // Override the workflow to navigate to extension page instead
        const wrappedFn = async (
          p: Page,
          dir: string,
          target: Target
        ): Promise<StepResult[]> => {
          // Navigate to the extension entry point first
          const targetUrl = `${staticServer.url}/${extPage}`
          console.log(`    Navigating to ${targetUrl}`)
          await p.goto(targetUrl, {
            waitUntil: "domcontentloaded",
            timeout: CONFIG.timeout,
          })
          await delay(3000)

          // Then run the workflow (which will try to navigate within)
          return fn(p, dir, target)
        }

        steps = await wrappedFn(page, workflowDir, "extension")
      } catch (err: any) {
        passed = false
        error = err.message
        console.log(`    [FAIL] ${wfName}: ${err.message}`)
      }

      // Write logs
      fs.writeFileSync(
        path.join(workflowDir, "network.json"),
        JSON.stringify(networkLog, null, 2)
      )
      fs.writeFileSync(
        path.join(workflowDir, "console.json"),
        JSON.stringify(consoleLog, null, 2)
      )

      const criticalErrors = consoleLog.filter(
        (c) => c.type === "pageerror" && !isBenign(c.text)
      )
      if (criticalErrors.length > 0) {
        console.log(`    [warn] ${criticalErrors.length} critical console error(s)`)
      }

      const stepErrors = steps.filter((s) => s.error)
      if (stepErrors.length > 0) {
        passed = false
        error = `${stepErrors.length} step(s) failed`
      }

      results.push({
        workflow: wfName,
        target: "extension",
        steps,
        networkLog,
        consoleLog,
        passed,
        error,
      })

      await page.close()
    }

    return results
  } finally {
    CONFIG.webUrl = originalWebUrl
    await browser.close()
    await staticServer.close()
  }
}

/** Map workflow name to extension entry point */
function getExtensionPage(workflow: WorkflowName): string {
  switch (workflow) {
    case "chat":
      return "sidepanel.html"
    case "media":
      return "options.html#/media"
    case "prompts":
      return "options.html#/prompts"
    case "characters":
      return "options.html#/characters"
  }
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const args = process.argv.slice(2)
  const targetArg = args.find((a) => a.startsWith("--target"))
  let targetValue: string | undefined
  if (targetArg) {
    const eqIdx = targetArg.indexOf("=")
    if (eqIdx >= 0) {
      targetValue = targetArg.slice(eqIdx + 1)
    } else {
      const idx = args.indexOf(targetArg)
      targetValue = args[idx + 1]
    }
  }

  const targets: Target[] = []
  if (!targetValue || targetValue === "web" || targetValue === "all") {
    targets.push("web")
  }
  if (
    !targetValue ||
    targetValue === "ext" ||
    targetValue === "extension" ||
    targetValue === "all"
  ) {
    targets.push("extension")
  }

  console.log("CDP Workflow Examination")
  console.log(`  Targets: ${targets.join(", ")}`)
  console.log(`  Server: ${CONFIG.serverUrl}`)
  console.log(`  Web UI: ${CONFIG.webUrl}`)
  console.log(`  Headless: ${CONFIG.headless}`)
  console.log(`  Artifacts: ${CONFIG.artifactsDir}`)

  // Clean and create artifacts directory
  if (fs.existsSync(CONFIG.artifactsDir)) {
    fs.rmSync(CONFIG.artifactsDir, { recursive: true })
  }
  ensureDir(CONFIG.artifactsDir)

  const summary: Summary = {
    startedAt: timestamp(),
    completedAt: "",
    targets,
    results: [],
  }

  // Run targets
  if (targets.includes("web")) {
    try {
      const webResults = await runWebUI()
      summary.results.push(...webResults)
    } catch (err: any) {
      console.error(`\n[ERROR] Web UI target failed: ${err.message}`)
    }
  }

  if (targets.includes("extension")) {
    try {
      const extResults = await runExtension()
      summary.results.push(...extResults)
    } catch (err: any) {
      console.error(`\n[ERROR] Extension target failed: ${err.message}`)
    }
  }

  summary.completedAt = timestamp()

  // Write summary
  fs.writeFileSync(
    path.join(CONFIG.artifactsDir, "summary.json"),
    JSON.stringify(summary, null, 2)
  )

  // Print summary
  console.log("\n=== Summary ===")
  for (const result of summary.results) {
    const status = result.passed ? "PASS" : "FAIL"
    const stepCount = result.steps.length
    const failedSteps = result.steps.filter((s) => s.error).length
    const apiCalls = result.networkLog.filter((n) => n.type === "request").length
    console.log(
      `  [${result.target}] ${result.workflow}: ${status} (${stepCount} steps, ${failedSteps} failed, ${apiCalls} API calls)`
    )
    if (result.error) {
      console.log(`    Error: ${result.error}`)
    }
  }

  const totalPassed = summary.results.filter((r) => r.passed).length
  const totalFailed = summary.results.filter((r) => !r.passed).length
  console.log(`\n  Total: ${totalPassed} passed, ${totalFailed} failed`)
  console.log(`  Artifacts: ${CONFIG.artifactsDir}`)
}

main().catch((err) => {
  console.error("Fatal error:", err)
  process.exit(1)
})
