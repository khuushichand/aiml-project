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
import { TEST_CONFIG, fetchWithApiKey } from "../utils/helpers"

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
    await authedPage.addInitScript(
      (cfg) => {
        try {
          localStorage.setItem(
            "tldwConfig",
            JSON.stringify({
              serverUrl: cfg.serverUrl,
              authMode: "single-user",
              apiKey: cfg.apiKey
            })
          )
        } catch {
          // ignore localStorage errors
        }
        try {
          localStorage.setItem("__tldw_first_run_complete", "true")
        } catch {
          // ignore localStorage errors
        }
        try {
          localStorage.setItem("__tldw_allow_offline", "true")
        } catch {
          // ignore localStorage errors
        }
      },
      {
        serverUrl: TEST_CONFIG.serverUrl,
        apiKey: TEST_CONFIG.apiKey
      }
    )
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

    expect(diagnostics.pageErrors).toHaveLength(0)
  })
})
