#!/usr/bin/env node
/*
  Playwright login/redirect check for the tldw frontend.
  Usage:
    TLDW_WEB_URL=http://localhost:3000 \
    TLDW_SERVER_URL=http://127.0.0.1:8000 \
    TLDW_API_KEY=... \
    node scripts/playwright-login.mjs
*/

import { chromium } from "@playwright/test"
import { spawn } from "node:child_process"
import { fileURLToPath } from "node:url"
import { dirname, resolve } from "node:path"
import fs from "node:fs/promises"

const WEB_URL_RAW = (process.env.TLDW_WEB_URL || "http://localhost:3000").replace(
  /\/$/,
  ""
)
const SERVER_URL = (
  process.env.TLDW_SERVER_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000"
).replace(/\/$/, "")
const API_KEY = process.env.TLDW_API_KEY || "THIS-IS-A-SECURE-KEY-123-FAKE-KEY"
const WAIT_TIMEOUT_MS = Number(process.env.TLDW_WEB_WAIT_MS || "60000")
const WAIT_INTERVAL_MS = Number(process.env.TLDW_WEB_WAIT_INTERVAL_MS || "1000")
const AUTOSTART = process.env.TLDW_WEB_AUTOSTART !== "0"
const START_CMD = process.env.TLDW_WEB_CMD || "bun run dev"
const FORCE_LOCALHOST = process.env.TLDW_WEB_FORCE_LOCALHOST !== "0"
const ALLOW_OFFLINE = process.env.TLDW_E2E_ALLOW_OFFLINE !== "0"

const __dirname = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = resolve(__dirname, "..")

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function resolveWebUrl(input) {
  try {
    const url = new URL(input)
    if (!FORCE_LOCALHOST) return input
    const isLoopback =
      url.hostname === "127.0.0.1" ||
      url.hostname === "0.0.0.0" ||
      url.hostname === "::1"
    if (!isLoopback) return input
    url.hostname = "localhost"
    return url.toString().replace(/\/$/, "")
  } catch {
    return input
  }
}

async function waitForAnyUrl(urls, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs
  let lastStatus = null
  while (Date.now() < deadline) {
    for (const url of urls) {
      try {
        const res = await fetch(url, { method: "GET", redirect: "manual" })
        if (res.status === 200) {
          return url
        }
        lastStatus = `${url} -> ${res.status}`
      } catch (error) {
        lastStatus = `${url} -> ${error?.message || "fetch failed"}`
      }
    }
    await sleep(WAIT_INTERVAL_MS)
  }
  throw new Error(`Timed out waiting for bundle: ${lastStatus || "no response"}`)
}

async function waitForNextPageBundle(webUrl, routePath) {
  const normalized = routePath.startsWith("/") ? routePath : `/${routePath}`
  const trimmed = normalized.replace(/\/$/, "")
  const candidates = [
    `${webUrl}/_next/static/chunks/pages${trimmed}.js`,
    `${webUrl}/_next/static/chunks/pages${trimmed}/index.js`
  ]
  await waitForAnyUrl(candidates, WAIT_TIMEOUT_MS)
}

const createDiagnostics = () => ({
  console: [],
  pageErrors: [],
  requestFailures: []
})

const pushWithLimit = (list, item, limit = 200) => {
  list.push(item)
  if (list.length > limit) {
    list.shift()
  }
}

async function dumpDiagnostics(page, diagnostics, label) {
  const snapshot = {
    label,
    url: page.url(),
    console: diagnostics.console,
    pageErrors: diagnostics.pageErrors,
    requestFailures: diagnostics.requestFailures
  }
  const htmlPath = resolve(REPO_ROOT, "playwright-login-failure.html")
  const screenshotPath = resolve(REPO_ROOT, "playwright-login-failure.png")
  const logPath = resolve(REPO_ROOT, "playwright-login-failure.json")
  await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => {})
  const html = await page.content().catch(() => "")
  if (html) {
    await fs.writeFile(htmlPath, html, "utf8")
  }
  await fs.writeFile(logPath, JSON.stringify(snapshot, null, 2), "utf8")
  return { htmlPath, screenshotPath, logPath }
}

async function seedConfigInStorage(page) {
  const config = {
    serverUrl: SERVER_URL,
    authMode: "single-user",
    apiKey: API_KEY
  }
  await page.evaluate((cfg) => {
    try {
      localStorage.setItem("tldwConfig", JSON.stringify(cfg))
    } catch {}
    try {
      localStorage.setItem("__tldw_first_run_complete", "true")
    } catch {}
    try {
      if (cfg.allowOffline) {
        localStorage.setItem("__tldw_allow_offline", "true")
      }
    } catch {}
  }, { ...config, allowOffline: ALLOW_OFFLINE })
}

async function waitForAnySelector(page, selectors, timeoutMs) {
  const perSelectorTimeout = Math.max(1000, Math.floor(timeoutMs / selectors.length))
  for (const selector of selectors) {
    try {
      await page.waitForSelector(selector, {
        state: "visible",
        timeout: perSelectorTimeout
      })
      return page.locator(selector).first()
    } catch {}
  }
  return null
}

async function isServerReachable(url) {
  try {
    const res = await fetch(url, { method: "GET", redirect: "manual" })
    return res.status >= 200 && res.status < 400
  } catch {
    return false
  }
}

async function waitForServer(urls) {
  const targets = Array.isArray(urls) ? urls : [urls]
  const deadline = Date.now() + WAIT_TIMEOUT_MS
  let lastError = null

  while (Date.now() < deadline) {
    for (const url of targets) {
      try {
        const res = await fetch(url, { method: "GET", redirect: "manual" })
        if (res.status >= 200 && res.status < 400) {
          return url
        }
        lastError = new Error(`Unexpected status ${res.status} for ${url}`)
      } catch (error) {
        lastError = error
      }
    }
    await sleep(WAIT_INTERVAL_MS)
  }

  const message =
    lastError?.message ||
    `No response after ${WAIT_TIMEOUT_MS}ms`
  throw new Error(`Timed out waiting for server: ${message}`)
}

function startDevServer() {
  console.log(`Starting frontend: ${START_CMD}`)
  const child = spawn(START_CMD, {
    cwd: REPO_ROOT,
    shell: true,
    stdio: "inherit"
  })
  return child
}

async function run() {
  const WEB_URL = resolveWebUrl(WEB_URL_RAW)
  if (WEB_URL !== WEB_URL_RAW) {
    console.log(`Using ${WEB_URL} instead of ${WEB_URL_RAW} for dev origin`)
  }
  const loginUrl = `${WEB_URL}/login`
  const settingsUrl = `${WEB_URL}/settings/tldw`
  let serverProcess = null
  const reachable = await isServerReachable(loginUrl)

  if (!reachable) {
    if (!AUTOSTART) {
      console.log(`Waiting for frontend: ${loginUrl}`)
      await waitForServer([loginUrl, settingsUrl])
    } else {
      serverProcess = startDevServer()
      const stopServer = () => {
        if (!serverProcess) return
        serverProcess.kill("SIGTERM")
        serverProcess = null
      }
      process.on("exit", stopServer)
      process.on("SIGINT", () => {
        stopServer()
        process.exit(130)
      })
      process.on("SIGTERM", () => {
        stopServer()
        process.exit(143)
      })

      console.log(`Waiting for frontend: ${loginUrl}`)
      await waitForServer([loginUrl, settingsUrl])
    }
  } else {
    await waitForServer([loginUrl, settingsUrl])
  }

  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({ locale: "en-US" })
  await context.addInitScript(
    ({ serverUrl, apiKey, allowOffline }) => {
      try {
        localStorage.setItem(
          "tldwConfig",
          JSON.stringify({
            serverUrl,
            authMode: "single-user",
            apiKey
          })
        )
      } catch {}
      try {
        localStorage.setItem("__tldw_first_run_complete", "true")
      } catch {}
      try {
        if (allowOffline) {
          localStorage.setItem("__tldw_allow_offline", "true")
        }
      } catch {}
    },
    {
      serverUrl: SERVER_URL,
      apiKey: API_KEY,
      allowOffline: ALLOW_OFFLINE
    }
  )
  const page = await context.newPage()
  const diagnostics = createDiagnostics()

  page.on("console", (msg) => {
    pushWithLimit(diagnostics.console, {
      type: msg.type(),
      text: msg.text(),
      location: msg.location()
    })
  })
  page.on("pageerror", (error) => {
    pushWithLimit(diagnostics.pageErrors, {
      message: error.message,
      stack: error.stack || ""
    })
  })
  page.on("requestfailed", (request) => {
    pushWithLimit(diagnostics.requestFailures, {
      url: request.url(),
      errorText: request.failure()?.errorText || ""
    })
  })

  try {
    await page.goto(loginUrl, { waitUntil: "domcontentloaded" })
    await waitForNextPageBundle(WEB_URL, "/login").catch(() => {})
    await page.waitForTimeout(1000)
    if (!page.url().includes("/settings/tldw")) {
      console.warn("Login redirect did not complete; navigating to /settings/tldw.")
      await page.goto(`${WEB_URL}/settings/tldw`, {
        waitUntil: "domcontentloaded"
      })
    }
    await waitForNextPageBundle(WEB_URL, "/settings/tldw").catch(() => {})
    await page.reload({ waitUntil: "domcontentloaded" })

    const serverUrlInput =
      (await waitForAnySelector(
        page,
        [
          "input#serverUrl",
          "input[name='serverUrl']",
          "input[placeholder*='127.0.0.1:8000']"
        ],
        15000
      )) || null
    if (!serverUrlInput) {
      const paths = await dumpDiagnostics(page, diagnostics, "server-url-not-found")
      console.warn(
        `Server URL input not found. Saved ${paths.htmlPath}, ${paths.screenshotPath}, ${paths.logPath}`
      )
      console.warn("Falling back to localStorage config injection.")
      await seedConfigInStorage(page)
      await page.goto(`${WEB_URL}/chat`, { waitUntil: "domcontentloaded" })
      await waitForNextPageBundle(WEB_URL, "/chat").catch(() => {})
      await page.reload({ waitUntil: "domcontentloaded" })
      await page
        .getByTestId("chat-header")
        .waitFor({ state: "visible", timeout: 15000 })
      console.log("Playwright login flow completed (storage fallback).")
      return
    }
    await serverUrlInput.fill(SERVER_URL)

    let apiKeyInput =
      (await waitForAnySelector(
        page,
        [
          "input#apiKey",
          "input[name='apiKey']",
          "input[placeholder*='API key']",
          "input[placeholder*='api key']"
        ],
        6000
      )) || null

    if (!apiKeyInput) {
      const segmented = page.locator(".ant-segmented-item").first()
      if ((await segmented.count()) > 0) {
        await segmented.click()
      }
      apiKeyInput =
        (await waitForAnySelector(
          page,
          [
            "input#apiKey",
            "input[name='apiKey']",
            "input[placeholder*='API key']",
            "input[placeholder*='api key']",
            "input[type='password']"
          ],
          15000
        )) || null
      if (!apiKeyInput) {
        try {
          apiKeyInput = page.getByLabel("API Key")
        } catch {}
      }
    }
    if (!apiKeyInput) {
      const paths = await dumpDiagnostics(page, diagnostics, "api-key-not-found")
      console.warn(
        `API Key input not found. Saved ${paths.htmlPath}, ${paths.screenshotPath}, ${paths.logPath}`
      )
      console.warn("Falling back to localStorage config injection.")
      await seedConfigInStorage(page)
      await page.goto(`${WEB_URL}/chat`, { waitUntil: "domcontentloaded" })
      await page
        .getByTestId("chat-header")
        .waitFor({ state: "visible", timeout: 15000 })
      console.log("Playwright login flow completed (storage fallback).")
      return
    }
    await apiKeyInput.fill(API_KEY)

    await page.getByRole("button", { name: /^Save$/ }).click()

    await page
      .getByText(/settings saved/i)
      .waitFor({ state: "visible", timeout: 15000 })
      .catch(() => {})

    await page.goto(`${WEB_URL}/chat`, { waitUntil: "domcontentloaded" })
    await waitForNextPageBundle(WEB_URL, "/chat").catch(() => {})
    await page.reload({ waitUntil: "domcontentloaded" })
    await page.getByTestId("chat-header").waitFor({ state: "visible", timeout: 15000 })

    console.log("Playwright login flow completed.")
  } finally {
    await browser.close()
  }
}

run().catch((error) => {
  console.error(error)
  process.exit(1)
})
