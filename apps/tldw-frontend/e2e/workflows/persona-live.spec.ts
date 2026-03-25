/**
 * Persona Live Workflow E2E Tests
 *
 * Uses the live backend persona websocket endpoint (no mocked websocket).
 */
import {
  test,
  expect,
  skipIfServerUnavailable
} from "../utils/fixtures"
import { TEST_CONFIG, fetchWithApiKey, seedAuth } from "../utils/helpers"

type DocsInfoPayload = {
  capabilities?: Record<string, unknown> | null
  supported_features?: Record<string, unknown> | null
}

const parseBooleanish = (value: unknown): boolean | null => {
  if (typeof value === "boolean") return value
  if (typeof value === "number") return value !== 0
  if (typeof value !== "string") return null
  const normalized = value.trim().toLowerCase()
  if (!normalized) return null
  if (["true", "1", "yes", "on", "enabled"].includes(normalized)) return true
  if (["false", "0", "no", "off", "disabled"].includes(normalized)) return false
  return null
}

const isPersonaAdvertised = (docsInfo: DocsInfoPayload): boolean => {
  const maps = [docsInfo?.capabilities, docsInfo?.supported_features]
  for (const map of maps) {
    if (!map || typeof map !== "object" || !("persona" in map)) {
      continue
    }
    const parsed = parseBooleanish(map.persona)
    if (parsed !== null) return parsed
  }
  return false
}

test.describe("Persona Live Workflow", () => {
  test.beforeEach(async ({ authedPage }) => {
    await seedAuth(authedPage, {
      serverUrl: TEST_CONFIG.webUrl,
      webUrl: TEST_CONFIG.webUrl,
      apiKey: TEST_CONFIG.apiKey,
    })
    await authedPage.addInitScript(() => {
      const OriginalWebSocket = window.WebSocket
      const seen: string[] = []
      ;(window as Window & { __tldwSeenWsUrls?: string[] }).__tldwSeenWsUrls = seen
      window.WebSocket = class extends OriginalWebSocket {
        constructor(url: string | URL, protocols?: string | string[]) {
          seen.push(String(url))
          super(url, protocols)
        }
      } as typeof WebSocket
    })
  })

  test("shows setup gate or connects to live persona websocket and receives a plan/cancel notice", async ({
    authedPage,
    serverInfo,
    diagnostics
  }) => {
    skipIfServerUnavailable(serverInfo)

    const docsInfoResp = await fetchWithApiKey(
      `${TEST_CONFIG.serverUrl}/api/v1/config/docs-info`,
      TEST_CONFIG.apiKey
    ).catch(() => null)

    if (!docsInfoResp?.ok) {
      test.skip(true, "docs-info unavailable; cannot verify persona capability")
    }

    const docsInfo = (await docsInfoResp?.json().catch(() => null)) as
      | DocsInfoPayload
      | null
    if (!docsInfo || !isPersonaAdvertised(docsInfo)) {
      test.skip(true, "persona capability disabled on backend")
    }

    await authedPage.goto("/persona", { waitUntil: "domcontentloaded" })

    const personaUnavailableVisible = await authedPage
      .getByText("Persona unavailable")
      .isVisible()
      .catch(() => false)
    if (personaUnavailableVisible) {
      test.skip(true, "webui marked persona unavailable")
    }

    const setupOverlay = authedPage.getByTestId("assistant-setup-overlay")
    const setupHeading = authedPage.getByText("Assistant Setup").first()
    const setupRequired =
      (await setupHeading.isVisible().catch(() => false)) ||
      (await setupHeading.waitFor({ state: "visible", timeout: 5_000 }).then(() => true).catch(() => false))
    if (setupRequired) {
      await expect(setupOverlay).toBeVisible()
      await expect(setupHeading).toBeVisible()
      await expect(
        authedPage.getByText("Choose a persona")
      ).toBeVisible()
      expect(diagnostics.pageErrors).toHaveLength(0)
      return
    }

    await authedPage
      .getByRole("button", { name: /^Connect$/ })
      .evaluate((el: HTMLElement) => el.click())

    await expect(
      authedPage.getByRole("button", { name: /^Disconnect$/ })
    ).toBeVisible({ timeout: 30000 })
    await expect(
      authedPage.getByText("Persona stream connected")
    ).toBeVisible({ timeout: 30000 })

    await authedPage
      .getByPlaceholder("Ask Persona...")
      .fill(`live persona ws ${Date.now()}`)
    await authedPage.getByRole("button", { name: /^Send$/ }).click()

    await expect(
      authedPage.getByText("Pending tool plan")
    ).toBeVisible({ timeout: 45000 })

    await authedPage.getByRole("button", { name: /^Cancel$/ }).click()

    await expect(
      authedPage.getByText(/Cancelled pending work|Cancelled pending plan/i)
    ).toBeVisible({ timeout: 30000 })

    const seenWsUrls = await authedPage.evaluate(
      () => (window as Window & { __tldwSeenWsUrls?: string[] }).__tldwSeenWsUrls || []
    )
    const webHost = new URL(TEST_CONFIG.webUrl).host
    const backendHost = new URL(TEST_CONFIG.serverUrl).host
    const personaWsUrls = seenWsUrls.filter((raw: string) =>
      raw.includes("/api/v1/persona/stream")
    )

    expect(personaWsUrls.length).toBeGreaterThan(0)
    expect(
      personaWsUrls.some((raw: string) => new URL(raw).host === webHost)
    ).toBe(true)
    expect(
      personaWsUrls.every((raw: string) => new URL(raw).host !== backendHost)
    ).toBe(true)
    expect(diagnostics.pageErrors).toHaveLength(0)
  })
})
