/**
 * Workspace Playground Real-Backend Workflow E2E Tests
 *
 * These scenarios intentionally avoid route stubbing to catch regressions
 * that only appear when the page boots against a live API server.
 */
import { type Page, type Response, type Request } from "@playwright/test"
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors
} from "../utils/fixtures"
import {
  seedAuth,
  fetchWithApiKey,
  TEST_CONFIG,
  generateTestId
} from "../utils/helpers"
import { WorkspacePlaygroundPage } from "../utils/page-objects"

const DESKTOP_VIEWPORT = { width: 1440, height: 900 }
const CHAT_BOOTSTRAP_ENDPOINT =
  /\/api\/v1\/(?:chats(?:\/|\?|$)|chat\/conversations(?:\/|\?|$))/i

type BootstrapResponse = {
  url: string
  status: number
}

type BootstrapRequestFailure = {
  url: string
  errorText: string
}

const trackChatBootstrapResponses = (page: Page) => {
  const responses: BootstrapResponse[] = []
  const failures: BootstrapRequestFailure[] = []
  const onResponse = (response: Response) => {
    if (response.request().method().toUpperCase() !== "GET") return
    if (!CHAT_BOOTSTRAP_ENDPOINT.test(response.url())) return
    responses.push({
      url: response.url(),
      status: response.status()
    })
  }
  const onRequestFailed = (request: Request) => {
    if (request.method().toUpperCase() !== "GET") return
    if (!CHAT_BOOTSTRAP_ENDPOINT.test(request.url())) return
    failures.push({
      url: request.url(),
      errorText: request.failure()?.errorText || "request failed"
    })
  }

  page.on("response", onResponse)
  page.on("requestfailed", onRequestFailed)

  return {
    responses,
    failures,
    dispose: () => {
      page.off("response", onResponse)
      page.off("requestfailed", onRequestFailed)
    }
  }
}

const assertChatBootstrapHealthy = async (
  responses: BootstrapResponse[],
  failures: BootstrapRequestFailure[]
): Promise<void> => {
  if (failures.length > 0) {
    throw new Error(
      `Chat bootstrap requests failed at network layer: ${JSON.stringify(failures)}`
    )
  }

  const failingResponses = responses.filter(({ status }) => status >= 400)
  expect(
    failingResponses,
    `Chat bootstrap endpoints returned non-success responses: ${JSON.stringify(
      failingResponses
    )}`
  ).toHaveLength(0)
}

const canReachChatBootstrapEndpoint = async (): Promise<{
  reachable: boolean
  reason?: string
}> => {
  const endpoint = `${TEST_CONFIG.serverUrl}/api/v1/chats/?limit=1&offset=0&ordering=-updated_at`
  try {
    const response = await fetchWithApiKey(endpoint)
    if (response.ok) {
      return { reachable: true }
    }
    return {
      reachable: false,
      reason: `GET /api/v1/chats preflight returned HTTP ${response.status}`
    }
  } catch (error) {
    return {
      reachable: false,
      reason:
        error instanceof Error ? error.message : "GET /api/v1/chats preflight failed"
    }
  }
}

const ensureNoServerReachabilityDialog = async (page: Page): Promise<void> => {
  const serverDialog = page
    .getByRole("dialog")
    .filter({ hasText: /can't reach your tldw server/i })
  await expect(serverDialog).toBeHidden({ timeout: 5_000 })
}

const setWorkspaceSelectedModel = async (
  page: Page,
  modelId: string
): Promise<void> => {
  await page.evaluate((nextModel) => {
    const store = (window as { __tldw_useStoreMessageOption?: unknown })
      .__tldw_useStoreMessageOption as
        | {
            setState?: (nextState: Record<string, unknown>) => void
          }
        | undefined
    if (!store?.setState) {
      throw new Error("Message option store is unavailable on window")
    }
    store.setState({ selectedModel: nextModel })
  }, modelId)
}

const cleanupMediaItem = async (mediaId: number | null): Promise<void> => {
  if (!Number.isFinite(mediaId) || (mediaId as number) <= 0) {
    return
  }

  const targetId = Math.trunc(mediaId as number)
  const trashResponse = await fetchWithApiKey(`${TEST_CONFIG.serverUrl}/api/v1/media/${targetId}`, TEST_CONFIG.apiKey, {
    method: "DELETE"
  }).catch(() => null)

  if (trashResponse && !trashResponse.ok && trashResponse.status !== 204 && trashResponse.status !== 404) {
    throw new Error(`Soft delete for media ${targetId} returned HTTP ${trashResponse.status}`)
  }

  const permanentResponse = await fetchWithApiKey(
    `${TEST_CONFIG.serverUrl}/api/v1/media/${targetId}/permanent`,
    TEST_CONFIG.apiKey,
    { method: "DELETE" }
  ).catch(() => null)

  if (
    permanentResponse &&
    !permanentResponse.ok &&
    permanentResponse.status !== 204 &&
    permanentResponse.status !== 404
  ) {
    throw new Error(`Permanent delete for media ${targetId} returned HTTP ${permanentResponse.status}`)
  }
}

const fetchLiveMediaDetail = async (mediaId: number): Promise<Record<string, unknown>> => {
  const response = await fetchWithApiKey(
    `${TEST_CONFIG.serverUrl}/api/v1/media/${mediaId}?include_content=true&include_versions=false&include_version_content=false`
  )
  if (!response.ok) {
    throw new Error(`GET /api/v1/media/${mediaId} returned HTTP ${response.status}`)
  }
  const payload = await response.json().catch(() => null)
  if (!payload || typeof payload !== "object") {
    throw new Error(`GET /api/v1/media/${mediaId} returned a non-object payload`)
  }
  return payload as Record<string, unknown>
}

const buildSeedSources = () => {
  const base = Date.now() % 1_000_000
  return [
    {
      mediaId: 9_200_000 + base,
      title: "Workspace Real Backend Source A",
      type: "document" as const,
      url: "https://example.com/workspace-real-source-a"
    },
    {
      mediaId: 9_300_000 + base,
      title: "Workspace Real Backend Source B",
      type: "website" as const,
      url: "https://example.com/workspace-real-source-b"
    }
  ]
}

test.describe("Workspace Playground Workflow (Real Backend)", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    await page.setViewportSize(DESKTOP_VIEWPORT)
  })

  test("boots cleanly and keeps chat bootstrap endpoints healthy", async ({
    authedPage,
    serverInfo,
    diagnostics
  }) => {
    skipIfServerUnavailable(serverInfo)
    const chatBootstrapPreflight = await canReachChatBootstrapEndpoint()
    test.skip(
      !chatBootstrapPreflight.reachable,
      chatBootstrapPreflight.reason ||
        "Skipping real-backend workspace test: chat bootstrap endpoint unavailable"
    )

    const tracker = trackChatBootstrapResponses(authedPage)
    const workspacePage = new WorkspacePlaygroundPage(authedPage)

    try {
      await workspacePage.goto()
      await workspacePage.waitForReady()
      await assertChatBootstrapHealthy(tracker.responses, tracker.failures)
      await ensureNoServerReachabilityDialog(authedPage)
    } finally {
      tracker.dispose()
    }

    await assertNoCriticalErrors(diagnostics)
  })

  test("supports core workspace interactions with live API context", async ({
    authedPage,
    serverInfo,
    diagnostics
  }) => {
    skipIfServerUnavailable(serverInfo)
    const chatBootstrapPreflight = await canReachChatBootstrapEndpoint()
    test.skip(
      !chatBootstrapPreflight.reachable,
      chatBootstrapPreflight.reason ||
        "Skipping real-backend workspace test: chat bootstrap endpoint unavailable"
    )

    const tracker = trackChatBootstrapResponses(authedPage)
    const workspacePage = new WorkspacePlaygroundPage(authedPage)

    try {
      await workspacePage.goto()
      await workspacePage.waitForReady()
      await assertChatBootstrapHealthy(tracker.responses, tracker.failures)

      await workspacePage.openGlobalSearchWithShortcut()
      await workspacePage.closeGlobalSearchWithEscape()
      await workspacePage.hideSourcesPane()
      await workspacePage.showSourcesPane()
      await workspacePage.hideStudioPane()
      await workspacePage.showStudioPane()
      await workspacePage.openAddSourcesModal()
      await workspacePage.closeAddSourcesModal()

      await workspacePage.seedSources(buildSeedSources())
      await expect
        .poll(async () => (await workspacePage.getSourceIds()).length, {
          timeout: 10_000
        })
        .toBeGreaterThanOrEqual(2)
      const sourceIds = await workspacePage.getSourceIds()
      await workspacePage.selectSourceById(sourceIds[0])
      await workspacePage.expectSourceSelected(sourceIds[0])

      await ensureNoServerReachabilityDialog(authedPage)
    } finally {
      tracker.dispose()
    }

    await assertNoCriticalErrors(diagnostics)
  })

  test("ingests pasted text through the live add-source flow", async ({
    authedPage,
    serverInfo,
    diagnostics
  }) => {
    skipIfServerUnavailable(serverInfo)
    const chatBootstrapPreflight = await canReachChatBootstrapEndpoint()
    test.skip(
      !chatBootstrapPreflight.reachable,
      chatBootstrapPreflight.reason ||
        "Skipping real-backend workspace test: chat bootstrap endpoint unavailable"
    )

    const tracker = trackChatBootstrapResponses(authedPage)
    const workspacePage = new WorkspacePlaygroundPage(authedPage)
    const uniqueSlug = generateTestId("workspace-live-paste")
    const sourceTitle = `Workspace Live Paste ${uniqueSlug}`
    const sourceBody = `Live workspace ingestion body ${uniqueSlug}`
    let createdMediaId: number | null = null

    try {
      await workspacePage.goto()
      await workspacePage.waitForReady()
      await assertChatBootstrapHealthy(tracker.responses, tracker.failures)

      await workspacePage.openAddSourcesModal()
      await workspacePage.addSourceModal.getByRole("tab", { name: /paste/i }).click()
      await workspacePage.addSourceModal
        .getByPlaceholder("Give your content a title")
        .fill(sourceTitle)
      await workspacePage.addSourceModal
        .getByPlaceholder("Paste your text content here...")
        .fill(sourceBody)

      const uploadResponsePromise = authedPage.waitForResponse((response) => {
        const request = response.request()
        return (
          request.method().toUpperCase() === "POST" &&
          response.url().includes("/api/v1/media/add")
        )
      })

      await workspacePage.addSourceModal
        .getByRole("button", { name: /^add text$/i })
        .click()

      const uploadResponse = await uploadResponsePromise
      expect(uploadResponse.ok()).toBeTruthy()
      const uploadPayload = await uploadResponse.json().catch(() => null)
      const createdCandidate =
        uploadPayload?.results?.[0]?.media_id ??
        uploadPayload?.results?.[0]?.db_id ??
        uploadPayload?.result?.media_id ??
        uploadPayload?.result?.db_id ??
        uploadPayload?.media_id ??
        uploadPayload?.db_id ??
        uploadPayload?.id
      createdMediaId = Number(createdCandidate)
      expect(Number.isFinite(createdMediaId)).toBeTruthy()
      const liveMediaId = createdMediaId as number
      const uploadResult =
        uploadPayload?.results?.[0] ??
        uploadPayload?.result ??
        uploadPayload
      expect(
        uploadResult?.embeddings_scheduled,
        `Expected workspace source ingest to schedule embeddings, received ${JSON.stringify(uploadPayload)}`
      ).toBeTruthy()

      await expect(workspacePage.addSourceModal).toBeHidden({ timeout: 15_000 })

      let liveMediaDetail = await fetchLiveMediaDetail(liveMediaId)
      const initialVectorStatus =
        (liveMediaDetail.processing as Record<string, unknown> | undefined)
          ?.vector_processing_status ?? null
      expect(
        initialVectorStatus !== null,
        `Expected media details to expose vector_processing_status, received ${JSON.stringify(liveMediaDetail)}`
      ).toBeTruthy()
      await expect
        .poll(
          async () => {
            liveMediaDetail = await fetchLiveMediaDetail(liveMediaId)
            return (
              (liveMediaDetail.processing as Record<string, unknown> | undefined)
                ?.vector_processing_status ?? null
            )
          },
          {
            timeout: 60_000,
            message: `Timed out waiting for vector processing to complete: ${JSON.stringify(liveMediaDetail)}`
          }
        )
        .toBe(1)

      const sourceRow = workspacePage.sourcesPanel
        .locator("[data-source-id]", { hasText: sourceTitle })
        .first()
      await expect(sourceRow).toBeVisible({ timeout: 15_000 })
      await expect(
        sourceRow.locator("span").filter({ hasText: /^ready$/i }).first()
      ).toBeVisible({ timeout: 15_000 })
      await expect(sourceRow.locator('input[type="checkbox"]')).toBeEnabled()

      const sourceId = await sourceRow.getAttribute("data-source-id")
      expect(sourceId).toBeTruthy()
      await workspacePage.selectSourceById(sourceId!)
      await workspacePage.expectSourceSelected(sourceId!)
      await expect(workspacePage.sourcesPanel.getByText(/^1 selected$/i)).toBeVisible()
      await ensureNoServerReachabilityDialog(authedPage)
    } finally {
      tracker.dispose()
      await cleanupMediaItem(createdMediaId)
    }

    await assertNoCriticalErrors(diagnostics)
  })

  test("submits grounded live chat for a selected source and reopens the matching assistant turn from workspace search", async ({
    authedPage,
    serverInfo,
    diagnostics
  }) => {
    skipIfServerUnavailable(serverInfo)
    const chatBootstrapPreflight = await canReachChatBootstrapEndpoint()
    test.skip(
      !chatBootstrapPreflight.reachable,
      chatBootstrapPreflight.reason ||
        "Skipping real-backend workspace test: chat bootstrap endpoint unavailable"
    )

    const availableModel = serverInfo.models?.[0]
    test.skip(!availableModel, "Skipping grounded live chat test: no live chat models reported by /api/v1/llm/providers")

    test.setTimeout(180_000)

    const tracker = trackChatBootstrapResponses(authedPage)
    const workspacePage = new WorkspacePlaygroundPage(authedPage)
    const uniqueSlug = generateTestId("workspace-live-grounded-chat")
    const sourceTitle = `Workspace Live Grounded ${uniqueSlug}`
    const sourceBody =
      `Grounded workspace source marker LIVE-GROUNDED-${uniqueSlug.toUpperCase()}. ` +
      "This source explains that evidence handling should stay grounded in the selected source."
    const userQuestion =
      "In one sentence, what does the selected source say about evidence handling?"
    let createdMediaId: number | null = null

    try {
      await workspacePage.goto()
      await workspacePage.waitForReady()
      await assertChatBootstrapHealthy(tracker.responses, tracker.failures)
      await setWorkspaceSelectedModel(authedPage, availableModel!)

      await workspacePage.openAddSourcesModal()
      await workspacePage.addSourceModal.getByRole("tab", { name: /paste/i }).click()
      await workspacePage.addSourceModal
        .getByPlaceholder("Give your content a title")
        .fill(sourceTitle)
      await workspacePage.addSourceModal
        .getByPlaceholder("Paste your text content here...")
        .fill(sourceBody)

      const uploadResponsePromise = authedPage.waitForResponse((response) => {
        const request = response.request()
        return (
          request.method().toUpperCase() === "POST" &&
          response.url().includes("/api/v1/media/add")
        )
      })

      await workspacePage.addSourceModal
        .getByRole("button", { name: /^add text$/i })
        .click()

      const uploadResponse = await uploadResponsePromise
      expect(uploadResponse.ok()).toBeTruthy()
      const uploadPayload = await uploadResponse.json().catch(() => null)
      const createdCandidate =
        uploadPayload?.results?.[0]?.media_id ??
        uploadPayload?.results?.[0]?.db_id ??
        uploadPayload?.result?.media_id ??
        uploadPayload?.result?.db_id ??
        uploadPayload?.media_id ??
        uploadPayload?.db_id ??
        uploadPayload?.id
      createdMediaId = Number(createdCandidate)
      expect(Number.isFinite(createdMediaId)).toBeTruthy()
      const liveMediaId = createdMediaId as number
      const uploadResult =
        uploadPayload?.results?.[0] ??
        uploadPayload?.result ??
        uploadPayload
      expect(
        uploadResult?.embeddings_scheduled,
        `Expected workspace source ingest to schedule embeddings, received ${JSON.stringify(uploadPayload)}`
      ).toBeTruthy()

      await expect(workspacePage.addSourceModal).toBeHidden({ timeout: 15_000 })

      let liveMediaDetail = await fetchLiveMediaDetail(liveMediaId)
      const initialVectorStatus =
        (liveMediaDetail.processing as Record<string, unknown> | undefined)
          ?.vector_processing_status ?? null
      expect(
        initialVectorStatus !== null,
        `Expected media details to expose vector_processing_status, received ${JSON.stringify(liveMediaDetail)}`
      ).toBeTruthy()
      await expect
        .poll(
          async () => {
            liveMediaDetail = await fetchLiveMediaDetail(liveMediaId)
            return (
              (liveMediaDetail.processing as Record<string, unknown> | undefined)
                ?.vector_processing_status ?? null
            )
          },
          {
            timeout: 60_000,
            message: `Timed out waiting for vector processing to complete: ${JSON.stringify(liveMediaDetail)}`
          }
        )
        .toBe(1)

      const sourceRow = workspacePage.sourcesPanel
        .locator("[data-source-id]", { hasText: sourceTitle })
        .first()
      await expect(sourceRow).toBeVisible({ timeout: 15_000 })
      await expect(
        sourceRow.locator("span").filter({ hasText: /^ready$/i }).first()
      ).toBeVisible({ timeout: 15_000 })

      const sourceId = await sourceRow.getAttribute("data-source-id")
      expect(sourceId).toBeTruthy()
      await workspacePage.selectSourceById(sourceId!)
      await workspacePage.expectSourceSelected(sourceId!)
      await expect(
        workspacePage.chatPanel.getByText("Answers will be grounded in your selected sources")
      ).toBeVisible({ timeout: 15_000 })

      const ragResponsePromise = authedPage.waitForResponse((response) => {
        const request = response.request()
        return (
          request.method().toUpperCase() === "POST" &&
          response.url().includes("/api/v1/rag/search")
        )
      })
      const chatCompletionResponsePromise = authedPage.waitForResponse((response) => {
        const request = response.request()
        return (
          request.method().toUpperCase() === "POST" &&
          response.url().includes("/api/v1/chat/completions")
        )
      })

      const chatInput = workspacePage.chatPanel.getByPlaceholder(/ask about your sources/i)
      await chatInput.fill(userQuestion)
      await chatInput.press("Enter")

      const ragResponse = await ragResponsePromise
      expect(ragResponse.ok()).toBeTruthy()
      const ragRequestBody =
        (ragResponse.request().postDataJSON() as Record<string, unknown> | null) || {}
      expect(ragRequestBody.query).toBe(userQuestion)
      expect(ragRequestBody.include_media_ids).toEqual([createdMediaId])
      const ragResponseBody = await ragResponse.json().catch(() => null)
      const ragResults = Array.isArray(ragResponseBody?.documents)
        ? ragResponseBody.documents
        : Array.isArray(ragResponseBody?.results)
          ? ragResponseBody.results
        : []
      expect(
        ragResults.length,
        `Expected grounded retrieval results for live chat, received ${JSON.stringify(ragResponseBody)}`
      ).toBeGreaterThan(0)
      expect(ragResponseBody?.errors ?? []).toEqual([])

      const chatCompletionResponse = await chatCompletionResponsePromise
      expect(chatCompletionResponse.ok()).toBeTruthy()

      const messageItems = workspacePage.chatPanel.locator("[data-chat-message-id]")
      await expect
        .poll(async () => await messageItems.count(), { timeout: 60_000 })
        .toBeGreaterThanOrEqual(2)

      const assistantMessage = messageItems.last()
      const assistantBody = assistantMessage.locator("article p").first()
      let assistantText = ""
      await expect
        .poll(
          async () => {
            assistantText = ((await assistantBody.textContent()) || "")
              .replace(/\s+/g, " ")
              .trim()
            if (/generating response/i.test(assistantText)) {
              return 0
            }
            return assistantText.length
          },
          { timeout: 60_000 }
        )
        .toBeGreaterThan(20)
      expect(assistantText).not.toMatch(
        /only answer questions that are related to the provided context/i
      )

      const searchQuery =
        assistantText.split(/\s+/).slice(0, 6).join(" ")
      expect(searchQuery.length).toBeGreaterThan(10)

      await workspacePage.openGlobalSearchWithShortcut()
      await workspacePage.globalSearchInput.fill(searchQuery)

      const assistantResult = workspacePage.globalSearchModal
        .getByRole("button", { name: /assistant message/i })
        .first()
      await expect(assistantResult).toBeVisible({ timeout: 15_000 })
      await assistantResult.click()

      await expect(workspacePage.globalSearchModal).toBeHidden({ timeout: 10_000 })
      await expect
        .poll(async () => (await assistantMessage.getAttribute("class")) || "", {
          timeout: 10_000
        })
        .toContain("ring-2")
      await ensureNoServerReachabilityDialog(authedPage)
    } finally {
      tracker.dispose()
      await cleanupMediaItem(createdMediaId)
    }

    await assertNoCriticalErrors(diagnostics)
  })
})
