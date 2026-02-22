#!/usr/bin/env node
/**
 * CDP Extension Workflow Examination Wrapper
 *
 * Builds the Chrome extension (if needed), launches Chrome with the extension
 * loaded, injects mock chrome.* environment, and examines all four workflows
 * against extension entry points (sidepanel.html and options.html).
 *
 * This is a standalone alternative to the main cdp-examine-workflows.ts script
 * that focuses exclusively on the extension target with native chrome-extension://
 * loading via --load-extension.
 *
 * Usage:
 *   node scripts/cdp-examine-extension-workflows.js
 *   node scripts/cdp-examine-extension-workflows.js --no-build
 *   node scripts/cdp-examine-extension-workflows.js --headed
 */
const puppeteer = require("puppeteer")
const fs = require("fs")
const path = require("path")
const { execSync } = require("child_process")

// ─── Configuration ────────────────────────────────────────────────────────────

const PROJECT_ROOT = path.resolve(__dirname, "..")
const BUILD_DIR = path.join(PROJECT_ROOT, ".output", "chrome-mv3")
const ARTIFACTS_DIR = path.join(PROJECT_ROOT, "cdp-extension-artifacts")
const SERVER_URL =
  process.env.TLDW_SERVER_URL || "http://127.0.0.1:8000"
const API_KEY =
  process.env.TLDW_API_KEY || "THIS-IS-A-SECURE-KEY-123-FAKE-KEY"

const args = process.argv.slice(2)
const noBuild = args.includes("--no-build")
const headed = args.includes("--headed")
const TIMEOUT = 30_000
const SCREENSHOT_DELAY = 500

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
  /\[ext-mock\]/,
  /CONNECTION_DEBUG/,
  /ERR_FILE_NOT_FOUND/,
]

function isBenign(text) {
  return BENIGN_PATTERNS.some((p) => p.test(text))
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true })
}

function ts() {
  return new Date().toISOString()
}

function delay(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

async function captureStep(page, dir, num, name) {
  const filename = `${String(num).padStart(2, "0")}-${name}.png`
  const filepath = path.join(dir, filename)
  await delay(SCREENSHOT_DELAY)
  await page.screenshot({ path: filepath, fullPage: true })
  return filename
}

async function findFirst(page, selectors, timeoutMs = 5000) {
  for (const sel of selectors) {
    try {
      const el = await page.$(sel)
      if (el) {
        const box = await el.boundingBox()
        if (box) return sel
      }
    } catch {}
  }
  await delay(1000)
  for (const sel of selectors) {
    try {
      await page.waitForSelector(sel, { visible: true, timeout: timeoutMs })
      return sel
    } catch {}
  }
  return null
}

async function typeInto(page, selectors, text) {
  const sel = await findFirst(page, selectors)
  if (!sel) return false
  await page.click(sel)
  await page.type(sel, text, { delay: 30 })
  return true
}

async function clickFirst(page, selectors) {
  const sel = await findFirst(page, selectors)
  if (!sel) return false
  await page.click(sel)
  return true
}

async function clickButtonByText(page, pattern) {
  const buttons = await page.$$("button")
  for (const btn of buttons) {
    const text = await btn.evaluate((el) => el.textContent || "")
    if (pattern.test(text)) {
      const box = await btn.boundingBox()
      if (box) {
        await btn.click()
        return true
      }
    }
  }
  return false
}

async function waitForConnection(page, timeoutMs = 20000) {
  try {
    await page.waitForFunction(
      () => {
        const store = window.__tldw_useConnectionStore
        const state = store?.getState?.()?.state
        return state?.isConnected === true && state?.phase === "connected"
      },
      { timeout: timeoutMs }
    )
  } catch {
    console.warn("  [warn] Connection wait timed out — continuing")
  }
}

function createNetworkLogger(page) {
  const log = []
  page.on("request", (req) => {
    if (req.url().includes("/api/v1/") || req.url().includes("/api/")) {
      log.push({
        type: "request",
        url: req.url(),
        method: req.method(),
        body: req.postData() ?? null,
        timestamp: ts(),
      })
    }
  })
  page.on("response", (res) => {
    if (res.url().includes("/api/v1/") || res.url().includes("/api/")) {
      log.push({
        type: "response",
        url: res.url(),
        status: res.status(),
        timestamp: ts(),
      })
    }
  })
  return log
}

function createConsoleLogger(page) {
  const log = []
  page.on("console", (msg) => {
    log.push({ type: msg.type(), text: msg.text(), timestamp: ts() })
  })
  page.on("pageerror", (err) => {
    log.push({
      type: "pageerror",
      text: `${err.message}\n${err.stack || ""}`,
      timestamp: ts(),
    })
  })
  return log
}

// ─── Build Extension ──────────────────────────────────────────────────────────

function buildExtension() {
  if (noBuild && fs.existsSync(path.join(BUILD_DIR, "manifest.json"))) {
    console.log("  Skipping build (--no-build)")
    return
  }
  console.log("  Building Chrome extension...")
  execSync("bun run build:chrome", { cwd: PROJECT_ROOT, stdio: "inherit" })
}

// ─── Discover Extension ID ────────────────────────────────────────────────────

/**
 * After launching Chrome with --load-extension, discover the extension's ID
 * by querying chrome://extensions or service-worker target URL.
 */
async function discoverExtensionId(browser) {
  // Method: look at available targets for a service worker from our extension
  const targets = browser.targets()
  for (const t of targets) {
    const url = t.url()
    if (url.startsWith("chrome-extension://") && url.includes("background")) {
      const match = url.match(/chrome-extension:\/\/([a-z]+)\//)
      if (match) return match[1]
    }
  }

  // Fallback: open chrome://extensions and parse
  const page = await browser.newPage()
  await page.goto("chrome://extensions", { waitUntil: "domcontentloaded" })
  await delay(2000)

  const extensionId = await page.evaluate(() => {
    const manager = document.querySelector("extensions-manager")
    if (!manager || !manager.shadowRoot) return null
    const list = manager.shadowRoot.querySelector("extensions-item-list")
    if (!list || !list.shadowRoot) return null
    const items = list.shadowRoot.querySelectorAll("extensions-item")
    for (const item of items) {
      const id = item.getAttribute("id")
      if (id) return id
    }
    return null
  })

  await page.close()
  return extensionId
}

// ─── Workflow Runners ─────────────────────────────────────────────────────────

async function examineChat(page, dir) {
  const steps = []
  let stepNum = 0

  const addStep = async (name, fn) => {
    stepNum++
    try {
      await fn()
      const screenshot = await captureStep(page, dir, stepNum, name)
      steps.push({ step: stepNum, name, screenshot, timestamp: ts() })
      console.log(`    [${stepNum}] ${name}`)
    } catch (err) {
      const screenshot = await captureStep(page, dir, stepNum, `${name}-error`).catch(() => undefined)
      steps.push({ step: stepNum, name, screenshot, error: err.message, timestamp: ts() })
      console.log(`    [${stepNum}] ${name} FAIL — ${err.message}`)
    }
  }

  await addStep("page-loaded", async () => {
    await delay(3000)
  })

  await addStep("connection-ready", async () => {
    await waitForConnection(page)
  })

  await addStep("chat-ready", async () => {
    const found = await findFirst(page, [
      "#textarea-message",
      "[data-testid='chat-input']",
      "textarea[placeholder]",
      "textarea",
    ])
    if (!found) throw new Error("Chat input not found")
  })

  await addStep("model-selector", async () => {
    await clickFirst(page, [
      "[data-testid='model-selector']",
      "[data-testid='model-select-trigger']",
    ])
    await delay(1000)
  })

  await page.keyboard.press("Escape").catch(() => {})
  await delay(300)

  await addStep("message-typed", async () => {
    const typed = await typeInto(
      page,
      ["#textarea-message", "[data-testid='chat-input']", "textarea"],
      "Hello, what is 2+2?"
    )
    if (!typed) throw new Error("Could not type message")
  })

  await addStep("message-sent", async () => {
    const sent =
      (await clickFirst(page, ["[data-testid='send-button']"])) ||
      (await clickButtonByText(page, /send/i))
    if (!sent) await page.keyboard.press("Enter")
    await delay(2000)
  })

  await addStep("streaming", async () => {
    await delay(3000)
  })

  await addStep("response-received", async () => {
    try {
      await page.waitForSelector(
        "[data-role='assistant'], [data-message-role='assistant'], .assistant-message",
        { visible: true, timeout: 60000 }
      )
    } catch {
      console.log("      No assistant response (server may not have models)")
    }
    await delay(2000)
  })

  return steps
}

async function examineMedia(page, dir) {
  const steps = []
  let stepNum = 0

  const addStep = async (name, fn) => {
    stepNum++
    try {
      await fn()
      const screenshot = await captureStep(page, dir, stepNum, name)
      steps.push({ step: stepNum, name, screenshot, timestamp: ts() })
      console.log(`    [${stepNum}] ${name}`)
    } catch (err) {
      const screenshot = await captureStep(page, dir, stepNum, `${name}-error`).catch(() => undefined)
      steps.push({ step: stepNum, name, screenshot, error: err.message, timestamp: ts() })
      console.log(`    [${stepNum}] ${name} FAIL — ${err.message}`)
    }
  }

  await addStep("media-page", async () => {
    await delay(3000)
    await waitForConnection(page)
  })

  await addStep("quick-ingest-modal", async () => {
    const opened =
      (await clickFirst(page, ["[data-testid='open-quick-ingest']"])) ||
      (await clickButtonByText(page, /quick ingest/i))
    if (!opened) {
      await page.evaluate(() => {
        window.dispatchEvent(new CustomEvent("tldw:open-quick-ingest"))
      })
    }
    await delay(2000)
  })

  await addStep("modal-tabs", async () => {
    await delay(1000)
  })

  await addStep("url-entered", async () => {
    await typeInto(
      page,
      ["[data-testid='url-input']", "input[placeholder*='url' i]", "input[placeholder*='URL' i]"],
      "https://example.com"
    )
  })

  await addStep("processing", async () => {
    await clickButtonByText(page, /add|process|ingest|submit/i)
    await delay(3000)
  })

  await addStep("media-list", async () => {
    await page.keyboard.press("Escape").catch(() => {})
    await clickFirst(page, [".ant-modal-close"]).catch(() => {})
    await delay(2000)
  })

  return steps
}

async function examinePrompts(page, dir) {
  const steps = []
  let stepNum = 0

  const addStep = async (name, fn) => {
    stepNum++
    try {
      await fn()
      const screenshot = await captureStep(page, dir, stepNum, name)
      steps.push({ step: stepNum, name, screenshot, timestamp: ts() })
      console.log(`    [${stepNum}] ${name}`)
    } catch (err) {
      const screenshot = await captureStep(page, dir, stepNum, `${name}-error`).catch(() => undefined)
      steps.push({ step: stepNum, name, screenshot, error: err.message, timestamp: ts() })
      console.log(`    [${stepNum}] ${name} FAIL — ${err.message}`)
    }
  }

  await addStep("prompts-page", async () => {
    await delay(3000)
    await waitForConnection(page)
  })

  await addStep("tab-bar", async () => {
    try {
      await page.waitForSelector("[data-testid='prompts-segmented'], .ant-segmented", {
        visible: true,
        timeout: 10000,
      })
    } catch {
      console.log("      Segmented tab bar not found")
    }
  })

  await addStep("drawer-open", async () => {
    const clicked =
      (await clickFirst(page, ["[data-testid='prompts-add']"])) ||
      (await clickButtonByText(page, /add|create|new/i))
    if (!clicked) throw new Error("Add prompt button not found")
    await delay(1500)
  })

  await addStep("form-filled", async () => {
    await typeInto(
      page,
      ["[data-testid='prompt-drawer-name']", "input[placeholder*='name' i]"],
      "CDP Extension Test"
    )
    const systemSel = await findFirst(page, [
      "[data-testid='prompt-drawer-system']",
      "textarea[placeholder*='system' i]",
    ])
    if (systemSel) {
      await page.click(systemSel)
      await page.type(systemSel, "You are a test assistant.", { delay: 20 })
    }
    const userSel = await findFirst(page, [
      "[data-testid='prompt-drawer-user']",
      "textarea[placeholder*='user' i]",
    ])
    if (userSel) {
      await page.click(userSel)
      await page.type(userSel, "Tell me about {{topic}}", { delay: 20 })
    }
  })

  await addStep("prompt-created", async () => {
    await clickButtonByText(page, /save|create|submit/i)
    await delay(2000)
  })

  await addStep("search-result", async () => {
    await typeInto(
      page,
      ["[data-testid='prompts-search']", "input[placeholder*='search' i]"],
      "CDP Extension"
    )
    await delay(1500)
  })

  await addStep("delete-and-trash", async () => {
    const deleteBtn = await page.$("[data-testid^='prompt-delete-'], button[aria-label*='delete' i]")
    if (deleteBtn) {
      await deleteBtn.click()
      await delay(500)
      await clickButtonByText(page, /confirm|yes|ok|delete/i)
      await delay(1500)
    }
    // Switch to trash
    const trashClicked =
      (await clickFirst(page, ["[data-testid='prompts-trash']"])) ||
      (await clickButtonByText(page, /trash|deleted/i))
    if (trashClicked) await delay(1500)
  })

  return steps
}

async function examineCharacters(page, dir) {
  const steps = []
  let stepNum = 0

  const addStep = async (name, fn) => {
    stepNum++
    try {
      await fn()
      const screenshot = await captureStep(page, dir, stepNum, name)
      steps.push({ step: stepNum, name, screenshot, timestamp: ts() })
      console.log(`    [${stepNum}] ${name}`)
    } catch (err) {
      const screenshot = await captureStep(page, dir, stepNum, `${name}-error`).catch(() => undefined)
      steps.push({ step: stepNum, name, screenshot, error: err.message, timestamp: ts() })
      console.log(`    [${stepNum}] ${name} FAIL — ${err.message}`)
    }
  }

  await addStep("characters-page", async () => {
    await delay(3000)
    await waitForConnection(page)
  })

  await addStep("create-modal", async () => {
    const clicked =
      (await clickButtonByText(page, /new character|create character/i)) ||
      (await clickFirst(page, ["button[aria-label*='new' i]", "button[aria-label*='create' i]"]))
    if (!clicked) throw new Error("New character button not found")
    await delay(2000)
  })

  await addStep("form-filled", async () => {
    await typeInto(
      page,
      ["input[placeholder*='name' i]", ".ant-modal input", ".ant-form-item input"],
      "CDP Ext Character"
    )
    const textareas = await page.$$(".ant-modal textarea, .ant-form-item textarea")
    if (textareas.length >= 1) {
      await textareas[0].click()
      await textareas[0].type("Test character from CDP extension examination.", { delay: 15 })
    }
    if (textareas.length >= 2) {
      await textareas[1].click()
      await textareas[1].type("Hello! I'm a test character.", { delay: 15 })
    }
  })

  await addStep("character-created", async () => {
    const submitted =
      (await clickButtonByText(page, /save|create|submit|ok/i)) ||
      (await clickFirst(page, [".ant-modal-footer button.ant-btn-primary"]))
    if (!submitted) console.log("      Submit not found")
    await delay(3000)
  })

  await addStep("in-table", async () => {
    const row = await page.$(".ant-table-row")
    if (row) {
      const text = await row.evaluate((el) => el.textContent || "")
      console.log(`      Row: ${text.substring(0, 60)}...`)
    }
  })

  await addStep("delete", async () => {
    const deleteClicked =
      (await clickButtonByText(page, /delete/i)) ||
      (await clickFirst(page, ["button[aria-label*='delete' i]"]))
    if (deleteClicked) {
      await delay(500)
      await clickButtonByText(page, /confirm|yes|ok|delete/i)
      await delay(2000)
    }
  })

  return steps
}

// ─── Workflow Map ─────────────────────────────────────────────────────────────

const WORKFLOWS = {
  chat: { fn: examineChat, entryPoint: "sidepanel.html" },
  media: { fn: examineMedia, entryPoint: "options.html" },
  prompts: { fn: examinePrompts, entryPoint: "options.html" },
  characters: { fn: examineCharacters, entryPoint: "options.html" },
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  console.log("CDP Extension Workflow Examination")
  console.log(`  Server: ${SERVER_URL}`)
  console.log(`  Build dir: ${BUILD_DIR}`)
  console.log(`  Headed: ${headed}`)

  // Build extension
  buildExtension()

  if (!fs.existsSync(path.join(BUILD_DIR, "manifest.json"))) {
    console.error("Extension build missing manifest.json!")
    process.exit(1)
  }

  // Clean artifacts
  if (fs.existsSync(ARTIFACTS_DIR)) {
    fs.rmSync(ARTIFACTS_DIR, { recursive: true })
  }
  ensureDir(ARTIFACTS_DIR)

  // Launch Chrome with extension loaded
  console.log("\n  Launching Chrome with extension...")
  const browser = await puppeteer.launch({
    headless: headed ? false : "new",
    args: [
      `--disable-extensions-except=${BUILD_DIR}`,
      `--load-extension=${BUILD_DIR}`,
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--window-size=1440,900",
    ],
  })

  // Give extension time to load
  await delay(3000)

  // Discover extension ID
  let extensionId = await discoverExtensionId(browser)
  if (!extensionId) {
    console.warn(
      "  Could not discover extension ID — falling back to first available"
    )
    // Try again after more time
    await delay(3000)
    extensionId = await discoverExtensionId(browser)
  }

  console.log(`  Extension ID: ${extensionId || "not found"}`)

  const summary = {
    startedAt: ts(),
    completedAt: "",
    extensionId,
    results: [],
  }

  try {
    for (const [name, { fn, entryPoint }] of Object.entries(WORKFLOWS)) {
      const workflowDir = path.join(ARTIFACTS_DIR, name)
      ensureDir(workflowDir)

      console.log(`\n  Workflow: ${name}`)

      const page = await browser.newPage()
      await page.setViewport({ width: 1440, height: 900 })

      // Seed auth
      await page.evaluateOnNewDocument(
        (cfg) => {
          try {
            localStorage.setItem(
              "tldwConfig",
              JSON.stringify({ serverUrl: cfg.serverUrl, authMode: "single-user" })
            )
          } catch {}
          try { localStorage.setItem("__tldw_first_run_complete", "true") } catch {}
          try { localStorage.setItem("__tldw_allow_offline", "true") } catch {}
        },
        { serverUrl: SERVER_URL }
      )

      const networkLog = createNetworkLogger(page)
      const consoleLog = createConsoleLogger(page)

      let steps = []
      let passed = true
      let error

      try {
        // Navigate to extension page
        let url
        if (extensionId) {
          url = `chrome-extension://${extensionId}/${entryPoint}`
          // For options.html routes, append hash
          if (name !== "chat" && entryPoint === "options.html") {
            url = `chrome-extension://${extensionId}/options.html#/${name}`
          }
        } else {
          // Can't navigate to extension without ID
          throw new Error("Extension ID not found — cannot navigate")
        }

        console.log(`    Navigating to ${url}`)
        await page.goto(url, { waitUntil: "domcontentloaded", timeout: TIMEOUT })
        await delay(2000)

        steps = await fn(page, workflowDir)
      } catch (err) {
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

      const criticalErrors = consoleLog.filter(
        (c) => c.type === "pageerror" && !isBenign(c.text)
      )
      if (criticalErrors.length > 0) {
        console.log(`    [warn] ${criticalErrors.length} critical error(s)`)
      }

      const stepErrors = steps.filter((s) => s.error)
      if (stepErrors.length > 0) {
        passed = false
        error = `${stepErrors.length} step(s) failed`
      }

      summary.results.push({
        workflow: name,
        target: "extension-native",
        steps,
        networkLog,
        consoleLog,
        passed,
        error,
      })

      await page.close()
    }
  } finally {
    await browser.close()
  }

  summary.completedAt = ts()

  // Write summary
  fs.writeFileSync(
    path.join(ARTIFACTS_DIR, "summary.json"),
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
      `  ${result.workflow}: ${status} (${stepCount} steps, ${failedSteps} failed, ${apiCalls} API calls)`
    )
    if (result.error) console.log(`    Error: ${result.error}`)
  }

  const totalPassed = summary.results.filter((r) => r.passed).length
  const totalFailed = summary.results.filter((r) => !r.passed).length
  console.log(`\n  Total: ${totalPassed} passed, ${totalFailed} failed`)
  console.log(`  Artifacts: ${ARTIFACTS_DIR}`)
}

main().catch((err) => {
  console.error("Fatal error:", err)
  process.exit(1)
})
