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
import { seedAuth, fetchWithApiKey, TEST_CONFIG } from "../utils/helpers"
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

  await expect
    .poll(() => responses.length, {
      timeout: 20_000,
      message:
        "Expected workspace bootstrap to request /api/v1/chats or /api/v1/chat/conversations"
    })
    .toBeGreaterThan(0)

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
})
