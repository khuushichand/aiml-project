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

type PersonaCatalogEntry = {
  id?: string | null
}

type PersonaProfilePayload = {
  version?: number | null
}

const DEFAULT_PERSONA_ID = "research_assistant"
const COMPLETED_SETUP_STEPS = [
  "persona",
  "voice",
  "commands",
  "safety",
  "test",
] as const

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

const resolvePersonaIdForLiveProof = (
  catalog: PersonaCatalogEntry[] | null
): string => {
  const entries = Array.isArray(catalog) ? catalog : []
  const preferred = entries.find(
    (entry) => String(entry?.id || "").trim() === DEFAULT_PERSONA_ID
  )
  if (preferred) {
    return DEFAULT_PERSONA_ID
  }

  const fallback = entries.find((entry) => String(entry?.id || "").trim().length > 0)
  return String(fallback?.id || DEFAULT_PERSONA_ID).trim() || DEFAULT_PERSONA_ID
}

const ensurePersonaSetupCompleted = async (personaId: string): Promise<void> => {
  const normalizedPersonaId = String(personaId || "").trim()
  if (!normalizedPersonaId) {
    throw new Error("Persona live proof requires a persona id")
  }

  const profileUrl = `${TEST_CONFIG.serverUrl}/api/v1/persona/profiles/${encodeURIComponent(
    normalizedPersonaId
  )}`
  const profileResp = await fetchWithApiKey(profileUrl, TEST_CONFIG.apiKey).catch(
    () => null
  )

  if (!profileResp?.ok) {
    throw new Error(
      `Failed to load persona profile for live proof (${normalizedPersonaId})`
    )
  }

  const profilePayload = (await profileResp.json().catch(() => null)) as
    | PersonaProfilePayload
    | null
  const expectedVersion =
    typeof profilePayload?.version === "number" ? profilePayload.version : null
  const updateUrl = expectedVersion
    ? `${profileUrl}?expected_version=${encodeURIComponent(String(expectedVersion))}`
    : profileUrl
  const completedSetup = {
    status: "completed",
    version: 1,
    run_id: `e2e-live-${Date.now()}`,
    current_step: "test",
    completed_steps: [...COMPLETED_SETUP_STEPS],
    completed_at: new Date().toISOString(),
    last_test_type: "live_session",
  }
  const updateResp = await fetchWithApiKey(updateUrl, TEST_CONFIG.apiKey, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      setup: completedSetup,
    }),
  }).catch(() => null)

  if (!updateResp?.ok) {
    throw new Error(
      `Failed to mark persona setup complete for live proof (${normalizedPersonaId})`
    )
  }
}

test.describe("Persona Live Workflow", () => {
  test.beforeEach(async ({ authedPage }) => {
    await seedAuth(authedPage, {
      serverUrl: TEST_CONFIG.webUrl,
      webUrl: TEST_CONFIG.webUrl,
      apiKey: TEST_CONFIG.apiKey,
    })
    await authedPage.route("**/api/**", async (route, request) => {
      const headers = {
        ...request.headers(),
      }

      if (
        TEST_CONFIG.apiKey &&
        !headers["x-api-key"] &&
        !headers["authorization"]
      ) {
        headers["x-api-key"] = TEST_CONFIG.apiKey
      }

      await route.continue({ headers })
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

  test("connects to live persona websocket and receives a plan/cancel notice", async ({
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

    const catalogResp = await fetchWithApiKey(
      `${TEST_CONFIG.serverUrl}/api/v1/persona/catalog`,
      TEST_CONFIG.apiKey
    ).catch(() => null)
    const personaCatalog = (await catalogResp?.json().catch(() => null)) as
      | PersonaCatalogEntry[]
      | null
    const livePersonaId = resolvePersonaIdForLiveProof(personaCatalog)

    await ensurePersonaSetupCompleted(livePersonaId)

    await authedPage.goto(
      `/persona?persona_id=${encodeURIComponent(livePersonaId)}`,
      { waitUntil: "domcontentloaded" }
    )

    const personaUnavailableVisible = await authedPage
      .getByText("Persona unavailable")
      .isVisible()
      .catch(() => false)
    if (personaUnavailableVisible) {
      test.skip(true, "webui marked persona unavailable")
    }

    const setupOverlay = authedPage.getByTestId("assistant-setup-overlay")
    const connectButton = authedPage.getByRole("button", { name: /^Connect$/ })
    const disconnectButton = authedPage.getByRole("button", { name: /^Disconnect$/ })

    await expect(setupOverlay).toBeHidden({ timeout: 15_000 })

    const liveControlsState = await Promise.any([
      connectButton.waitFor({ state: "visible", timeout: 30_000 }).then(
        () => "connect" as const
      ),
      disconnectButton.waitFor({ state: "visible", timeout: 30_000 }).then(
        () => "disconnect" as const
      ),
    ]).catch(() => {
      throw new Error("Persona live proof did not reach connect or disconnect controls")
    })

    if (liveControlsState === "connect") {
      await connectButton.evaluate((el: HTMLElement) => el.click())
    }

    await expect(disconnectButton).toBeVisible({ timeout: 30000 })
    await expect(
      authedPage.getByText(/^Persona stream connected$/)
    ).toBeVisible({ timeout: 30000 })

    await authedPage
      .getByPlaceholder("Ask Persona...")
      .fill(`live persona ws ${Date.now()}`)
    await authedPage.getByRole("button", { name: /^Send$/ }).click()

    await expect(
      authedPage.getByText("Pending tool plan")
    ).toBeVisible({ timeout: 45000 })

    await authedPage.getByRole("button", { name: /^Cancel$/ }).click()

    await Promise.any([
      authedPage.getByText(/^Cancelled pending plan$/).waitFor({
        state: "visible",
        timeout: 30_000
      }),
      authedPage.getByText(/^Cancelled pending work\b/i).waitFor({
        state: "visible",
        timeout: 30_000
      }),
    ]).catch(() => {
      throw new Error("Expected a cancelled pending-work notice")
    })

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
