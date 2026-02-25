import path from "path"
import { expect, test } from "@playwright/test"
import { requireRealServerConfig, launchWithExtensionOrSkip } from "./utils/real-server"
import { forceConnected, waitForConnectionStore } from "./utils/connection"

const normalizeServerUrl = (value: string) =>
  value.match(/^https?:\/\//) ? value : `http://${value}`

const isConnectivityError = (error: unknown): boolean => {
  const text = String(error)
  return /fetch failed|econnrefused|enotfound|ehostunreach|eperm|etimedout|eai_again|aborted/i.test(
    text.toLowerCase()
  )
}

const fetchWithTimeout = async (
  url: string,
  init?: RequestInit,
  timeoutMs = 30_000
) => {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(url, {
      ...init,
      signal: controller.signal,
    })
  } finally {
    clearTimeout(timeout)
  }
}

const requestJson = async (
  serverUrl: string,
  apiKey: string,
  path: string,
  init?: RequestInit,
  timeoutMs = 30_000
) => {
  const response = await fetchWithTimeout(
    `${serverUrl}${path}`,
    {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        ...(init?.headers || {}),
      },
    },
    timeoutMs
  )

  const text = await response.text().catch(() => "")
  if (!response.ok) {
    throw new Error(`Request failed ${response.status} ${response.statusText}: ${text}`)
  }

  if (!text) {
    return null
  }

  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

test.describe("ACP Playground real backend lifecycle", () => {
  test("hydrates backend session metadata and surfaces usage signal", async () => {
    const { serverUrl, apiKey } = requireRealServerConfig(test)
    const serverBaseUrl = normalizeServerUrl(serverUrl)

    let agentsPayload: any = null
    try {
      agentsPayload = await requestJson(serverBaseUrl, apiKey, "/api/v1/acp/agents")
    } catch (error) {
      if (isConnectivityError(error)) {
        test.skip(
          true,
          `ACP backend unreachable in this environment (${String(error)})`
        )
        return
      }
      throw error
    }

    const agents = Array.isArray(agentsPayload?.agents) ? agentsPayload.agents : []
    const configuredAgent = agents.find((agent) => agent?.is_configured)

    if (!configuredAgent?.type) {
      test.skip(true, "No configured ACP agent found on target server")
      return
    }

    const sessionName = `ACP E2E ${Date.now()}`
    let createdSessionId: string | null = null

    try {
      try {
        const created = await requestJson(
          serverBaseUrl,
          apiKey,
          "/api/v1/acp/sessions/new",
          {
            method: "POST",
            body: JSON.stringify({
              cwd: "/tmp",
              name: sessionName,
              agent_type: configuredAgent.type,
            }),
          },
          60_000
        )

        createdSessionId = typeof created?.session_id === "string" ? created.session_id : null
      } catch (error) {
        test.skip(true, `ACP session creation unavailable in this environment (${String(error)})`)
        return
      }

      if (!createdSessionId) {
        test.skip(true, "ACP session create did not return session_id")
        return
      }

      const usagePayload = await requestJson(
        serverBaseUrl,
        apiKey,
        `/api/v1/acp/sessions/${encodeURIComponent(createdSessionId)}/usage`
      )
      expect(usagePayload?.session_id).toBe(createdSessionId)

      const extPath = path.resolve("build/chrome-mv3")
      const seed = {
        __tldw_first_run_complete: true,
        tldwConfig: {
          serverUrl: serverBaseUrl,
          authMode: "single-user",
          apiKey,
        },
      }

      const { context, page, extensionId } = await launchWithExtensionOrSkip(test, extPath, {
        seedConfig: seed,
      })

      try {
        const optionsUrl = `chrome-extension://${extensionId}/options.html#/acp-playground`
        await page.goto(optionsUrl, { waitUntil: "domcontentloaded" })
        await waitForConnectionStore(page, "acp-playground-lifecycle")
        await forceConnected(
          page,
          { serverUrl: serverBaseUrl },
          "acp-playground-lifecycle"
        )

        await expect(page.getByText(/Agent Playground/i)).toBeVisible({ timeout: 20_000 })

        const sessionRow = page
          .locator('[data-testid="acp-session-item"]')
          .filter({ hasText: sessionName })
          .first()

        await expect(sessionRow).toBeVisible({ timeout: 30_000 })
        await expect(sessionRow).toContainText(/Msgs\s+\d+/)
        await expect(sessionRow).toContainText(/Tokens\s+\d+/)

        // Attempt a prompt to generate history for backend fork validation.
        await requestJson(
          serverBaseUrl,
          apiKey,
          "/api/v1/acp/sessions/prompt",
          {
            method: "POST",
            body: JSON.stringify({
              session_id: createdSessionId,
              prompt: [{ role: "user", content: "Say hello in one short sentence." }],
            }),
          },
          30_000
        ).catch(() => null)

        const detailPayload = await requestJson(
          serverBaseUrl,
          apiKey,
          `/api/v1/acp/sessions/${encodeURIComponent(createdSessionId)}/detail`
        ).catch(() => null)

        const detailMessages = Array.isArray(detailPayload?.messages)
          ? detailPayload.messages.length
          : 0

        if (detailMessages > 0) {
          await sessionRow.hover()
          const forkButton = page.getByTestId(`acp-session-fork-${createdSessionId}`)
          await expect(forkButton).toBeVisible({ timeout: 10_000 })
          await forkButton.click()

          const forkedRow = page
            .locator('[data-testid="acp-session-item"]')
            .filter({ hasText: "(fork)" })
            .first()

          await expect(forkedRow).toBeVisible({ timeout: 20_000 })
        }
      } finally {
        await context.close()
      }
    } finally {
      if (createdSessionId) {
        await requestJson(
          serverBaseUrl,
          apiKey,
          "/api/v1/acp/sessions/close",
          {
            method: "POST",
            body: JSON.stringify({ session_id: createdSessionId }),
          },
          15_000
        ).catch(() => null)
      }
    }
  })
})
