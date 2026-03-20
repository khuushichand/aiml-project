/**
 * Workspace Playground Real-Backend Workflow E2E Tests
 *
 * These scenarios intentionally avoid route stubbing to catch regressions
 * that only appear when the page boots against a live API server.
 */
import {
  type Page,
  type Response,
  type Request,
  type Locator
} from "@playwright/test"
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

type LiveWorkspaceSource = {
  mediaId: number
  title: string
  type: "document"
  url: string
  content: string
}

type RagSearchCall = {
  requestBody: Record<string, unknown>
  responseBody: Record<string, unknown> | null
  status: number
}

const normalizeWhitespace = (value: string): string =>
  value.replace(/\s+/g, " ").trim()

const seedLiveWorkspaceDocument = async (
  title: string,
  content: string
): Promise<LiveWorkspaceSource> => {
  const fileName = `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.txt`
  const body = new FormData()
  body.append("media_type", "document")
  body.append("title", title)
  body.append("perform_analysis", "false")
  body.append("perform_chunking", "false")
  body.append("files", new Blob([content], { type: "text/plain" }), fileName)

  const response = await fetchWithApiKey(
    `${TEST_CONFIG.serverUrl}/api/v1/media/add`,
    TEST_CONFIG.apiKey,
    {
      method: "POST",
      body
    }
  )
  if (!response.ok) {
    throw new Error(
      `Failed to seed live workspace media "${title}": ${response.status} ${await response.text()}`
    )
  }

  const payload = await response.json().catch(() => ({}))
  const result = Array.isArray(payload?.results)
    ? payload.results[0]
    : payload?.result || payload
  const mediaId = Number(result?.db_id ?? result?.media_id ?? result?.id)
  if (!Number.isFinite(mediaId) || mediaId <= 0) {
    throw new Error(
      `Live workspace media seed for "${title}" returned no usable media id: ${JSON.stringify(
        payload
      )}`
    )
  }

  const expectedSnippet = normalizeWhitespace(content).slice(0, 48)
  await expect
    .poll(
      async () => {
        const details = await fetchWithApiKey(
          `${TEST_CONFIG.serverUrl}/api/v1/media/${mediaId}?include_content=true&include_versions=false&include_version_content=false`,
          TEST_CONFIG.apiKey
        )
        if (!details.ok) return ""
        const body = await details.json().catch(() => ({}))
        return normalizeWhitespace(
          String(
            body?.content?.text ??
              body?.content?.content ??
              body?.transcript ??
              ""
          )
        )
      },
      {
        timeout: 30_000,
        message: `Media ${mediaId} never exposed usable content for workspace grounding`
      }
    )
    .toContain(expectedSnippet)

  return {
    mediaId,
    title,
    type: "document",
    url: `file://${fileName}`,
    content
  }
}

const waitForRagSearchCall = async (
  page: Page,
  action: () => Promise<void>
): Promise<RagSearchCall> => {
  const responsePromise = page.waitForResponse(
    (response) =>
      response.request().method().toUpperCase() === "POST" &&
      /\/api\/v1\/rag\/search(?:\?|$)/i.test(response.url()),
    { timeout: 90_000 }
  )
  const [response] = await Promise.all([responsePromise, action()])
  return {
    requestBody:
      (response.request().postDataJSON() as Record<string, unknown>) || {},
    responseBody:
      (await response.json().catch(() => null)) as Record<string, unknown> | null,
    status: response.status()
  }
}

const waitForStudioArtifactCompletion = async (artifactCard: Locator) => {
  await expect
    .poll(
      async () => {
        const downloadVisible = await artifactCard
          .getByRole("button", { name: /download/i })
          .isVisible()
          .catch(() => false)
        if (downloadVisible) {
          return "completed"
        }

        const cardText = (await artifactCard.textContent()) || ""
        if (/failed|encountered an error|no usable/i.test(cardText)) {
          return `failed:${cardText}`
        }

        return "pending"
      },
      {
        timeout: 120_000,
        message: "Studio artifact did not reach a completed state"
      }
    )
    .toBe("completed")
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

  test("grounds live chat requests on the selected source", async ({
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

    const fixtureId = generateTestId("workspace-chat-grounding")
    const probeToken = `${fixtureId}-beacon-fox`
    const selectedSource = await seedLiveWorkspaceDocument(
      `WS ${fixtureId} Alpha`,
      `Workspace chat grounding source. Token ${probeToken}. Deterministic verification requires stable include media ids.`
    )
    const unselectedSource = await seedLiveWorkspaceDocument(
      `WS ${fixtureId} Beta`,
      `Workspace chat distractor source. Token ${fixtureId}-distractor.`
    )

    const tracker = trackChatBootstrapResponses(authedPage)
    const workspacePage = new WorkspacePlaygroundPage(authedPage)
    const question = `What does the source say about ${probeToken}?`

    try {
      await workspacePage.goto()
      await workspacePage.waitForReady()
      await assertChatBootstrapHealthy(tracker.responses, tracker.failures)

      await workspacePage.seedSources([selectedSource, unselectedSource])
      await expect
        .poll(async () => (await workspacePage.getSourceIds()).length, {
          timeout: 10_000
        })
        .toBeGreaterThanOrEqual(2)

      await workspacePage.selectSourceByTitle(selectedSource.title)
      await workspacePage.expectSourceSelectedByTitle(selectedSource.title)
      await expect(workspacePage.getSelectedSourceTag(selectedSource.title)).toBeVisible({
        timeout: 10_000
      })

      const ragCall = await waitForRagSearchCall(authedPage, async () => {
        await workspacePage.sendChatMessage(question)
      })

      expect(ragCall.status).toBe(200)
      expect(ragCall.requestBody.include_media_ids).toEqual([selectedSource.mediaId])
      expect(ragCall.requestBody.sources).toEqual(["media_db"])
      expect(String(ragCall.requestBody.query ?? "")).toContain(probeToken)
      expect(
        String(ragCall.responseBody?.generated_answer ?? "").trim().length
      ).toBeGreaterThan(0)
      await expect(workspacePage.chatPanel.getByText(question)).toBeVisible({
        timeout: 10_000
      })

      await ensureNoServerReachabilityDialog(authedPage)
    } finally {
      tracker.dispose()
    }

    await assertNoCriticalErrors(diagnostics)
  })

  test("scopes studio compare-sources generation to the selected media ids", async ({
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

    const fixtureId = generateTestId("workspace-studio-scope")
    const leftSource = await seedLiveWorkspaceDocument(
      `WS ${fixtureId} Left`,
      `Left comparison source. Token ${fixtureId}-left. Claim: alpha baseline improved by 11 percent.`
    )
    const rightSource = await seedLiveWorkspaceDocument(
      `WS ${fixtureId} Right`,
      `Right comparison source. Token ${fixtureId}-right. Claim: beta baseline improved by 19 percent.`
    )

    const tracker = trackChatBootstrapResponses(authedPage)
    const workspacePage = new WorkspacePlaygroundPage(authedPage)

    try {
      await workspacePage.goto()
      await workspacePage.waitForReady()
      await assertChatBootstrapHealthy(tracker.responses, tracker.failures)

      await workspacePage.seedSources([leftSource, rightSource])
      await expect
        .poll(async () => (await workspacePage.getSourceIds()).length, {
          timeout: 10_000
        })
        .toBeGreaterThanOrEqual(2)

      await workspacePage.selectSourceByTitle(leftSource.title)
      await workspacePage.selectSourceByTitle(rightSource.title)
      await workspacePage.expectSourceSelectedByTitle(leftSource.title)
      await workspacePage.expectSourceSelectedByTitle(rightSource.title)
      await expect(
        workspacePage.getStudioOutputButton("Compare Sources")
      ).toBeEnabled({ timeout: 10_000 })

      const beforeCount = await workspacePage.getStudioArtifactCards().count()
      const ragCall = await waitForRagSearchCall(authedPage, async () => {
        await workspacePage.getStudioOutputButton("Compare Sources").click()
      })

      expect(ragCall.status).toBe(200)
      expect(
        [...((ragCall.requestBody.include_media_ids as number[]) || [])].sort(
          (a, b) => a - b
        )
      ).toEqual([leftSource.mediaId, rightSource.mediaId].sort((a, b) => a - b))
      expect(ragCall.requestBody.enable_generation).toBe(true)
      expect(String(ragCall.requestBody.generation_prompt ?? "")).toContain(
        "Compare the selected sources and produce"
      )
      expect(
        String(ragCall.responseBody?.generated_answer ?? "").trim().length
      ).toBeGreaterThan(0)

      await expect(workspacePage.getStudioArtifactCards()).toHaveCount(
        beforeCount + 1,
        { timeout: 90_000 }
      )
      const artifactCard = workspacePage.getStudioArtifactCards().first()
      await waitForStudioArtifactCompletion(artifactCard)
      await expect(artifactCard).toContainText(/Compare Sources/i)

      await ensureNoServerReachabilityDialog(authedPage)
    } finally {
      tracker.dispose()
    }

    await assertNoCriticalErrors(diagnostics)
  })

  test("searches live chat turns from the workspace global search surface", async ({
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

    const fixtureId = generateTestId("workspace-global-search")
    const probeToken = `${fixtureId}-search-token`
    const selectedSource = await seedLiveWorkspaceDocument(
      `WS ${fixtureId} Search`,
      `Workspace search source. Token ${probeToken}.`
    )

    const tracker = trackChatBootstrapResponses(authedPage)
    const workspacePage = new WorkspacePlaygroundPage(authedPage)
    const question = `What does the document say about ${probeToken}?`

    try {
      await workspacePage.goto()
      await workspacePage.waitForReady()
      await assertChatBootstrapHealthy(tracker.responses, tracker.failures)

      await workspacePage.seedSources([selectedSource])
      await expect
        .poll(async () => (await workspacePage.getSourceIds()).length, {
          timeout: 10_000
        })
        .toBeGreaterThanOrEqual(1)

      await workspacePage.selectSourceByTitle(selectedSource.title)
      await workspacePage.expectSourceSelectedByTitle(selectedSource.title)

      const ragCall = await waitForRagSearchCall(authedPage, async () => {
        await workspacePage.sendChatMessage(question)
      })
      expect(ragCall.status).toBe(200)
      expect(ragCall.requestBody.include_media_ids).toEqual([selectedSource.mediaId])

      await workspacePage.openGlobalSearchWithShortcut()
      await workspacePage.searchWorkspace(`chat: ${probeToken}`)

      const chatResult = workspacePage.getGlobalSearchResult(probeToken)
      await expect(chatResult).toBeVisible({ timeout: 10_000 })
      await expect(chatResult).toContainText(/Chat/i)
      await workspacePage.globalSearchInput.press("Enter")
      await expect(workspacePage.globalSearchModal).toBeHidden({ timeout: 10_000 })

      await ensureNoServerReachabilityDialog(authedPage)
    } finally {
      tracker.dispose()
    }

    await assertNoCriticalErrors(diagnostics)
  })
})
