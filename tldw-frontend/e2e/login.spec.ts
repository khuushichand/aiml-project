import { test, expect } from "@playwright/test"

const serverUrl = process.env.TLDW_SERVER_URL || "http://127.0.0.1:8000"
const apiKey =
  process.env.TLDW_API_KEY || "THIS-IS-A-SECURE-KEY-123-FAKE-KEY"

const normalizeUrl = (value: string) => value.replace(/\/$/, "")

test("login via settings saves config", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear()
  })

  await page.goto("/login", { waitUntil: "domcontentloaded" })
  await page.waitForURL(/\/settings\/tldw/)

  const serverInput = page.getByLabel(/server url/i)
  await serverInput.waitFor({ state: "visible" })
  await serverInput.fill(serverUrl)

  const apiKeyInput = page.getByLabel(/api key/i)
  await apiKeyInput.fill(apiKey)

  await page.getByRole("button", { name: /save/i }).click()
  await page.waitForFunction(() => Boolean(localStorage.getItem("tldwConfig")))

  const stored = await page.evaluate(() => localStorage.getItem("tldwConfig"))
  expect(stored).toBeTruthy()
  const parsed = JSON.parse(stored || "{}")
  expect(normalizeUrl(parsed.serverUrl || "")).toBe(normalizeUrl(serverUrl))
  expect(parsed.apiKey).toBe(apiKey)
})

test("chat renders with saved config", async ({ page }) => {
  await page.addInitScript(
    (cfg) => {
      localStorage.setItem("tldwConfig", JSON.stringify(cfg))
      localStorage.setItem("__tldw_first_run_complete", "true")
    },
    {
      serverUrl,
      apiKey,
      authMode: "single-user"
    }
  )

  await page.goto("/chat", { waitUntil: "domcontentloaded" })
  await expect(page.getByTestId("chat-header")).toBeVisible()
})
