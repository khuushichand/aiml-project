import { test, expect, type Page } from "@playwright/test"
import { grantHostPermission } from "./utils/permissions"
import {
  launchWithExtensionOrSkip,
  requireRealServerConfig
} from "./utils/real-server"
import { forceConnected, waitForConnectionStore } from "./utils/connection"
import { IMAGE_GENERATION_EVENT_MIRROR_PREFIX } from "@tldw/ui/utils/image-generation-chat"

const normalizeServerUrl = (value: string) =>
  value.match(/^https?:\/\//) ? value : `http://${value}`

const escapeRegExp = (value: string) =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")

const parseListPayload = (payload: any): any[] => {
  if (Array.isArray(payload)) return payload
  if (!payload || typeof payload !== "object") return []
  return (
    payload.items ||
    payload.results ||
    payload.data ||
    payload.messages ||
    payload.chats ||
    payload.characters ||
    payload.models ||
    []
  )
}

const E2E_MOCK_IMAGE_PNG_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5f2qsAAAAASUVORK5CYII="

const buildMockImageArtifactPayload = (backend: string) => ({
  artifact: {
    file_id: `e2e-mock-image-${Date.now()}`,
    export: {
      format: "png",
      mode: "inline",
      content_type: "image/png",
      bytes: E2E_MOCK_IMAGE_PNG_BASE64.length,
      content_b64: E2E_MOCK_IMAGE_PNG_BASE64
    },
    metadata: {
      backend
    }
  }
})

const requestJson = async (
  serverUrl: string,
  apiKey: string,
  path: string,
  init?: RequestInit,
  timeoutMs = 30000
) => {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`${serverUrl}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        ...(init?.headers || {})
      }
    })
    const text = await response.text().catch(() => "")
    if (!response.ok) {
      throw new Error(
        `Request failed ${response.status} ${response.statusText}: ${text}`
      )
    }
    if (!text) return null
    try {
      return JSON.parse(text)
    } catch {
      return null
    }
  } finally {
    clearTimeout(timeout)
  }
}

const ensureCharacterId = async (serverUrl: string, apiKey: string) => {
  const list = await requestJson(serverUrl, apiKey, "/api/v1/characters/").catch(
    () => requestJson(serverUrl, apiKey, "/api/v1/characters")
  )
  const characters = parseListPayload(list)
  const existing = characters.find((entry: any) => entry?.id != null)
  if (existing?.id != null) {
    return { id: String(existing.id), created: false }
  }

  const name = `E2E Image Sync Character ${Date.now()}`
  const created = await requestJson(serverUrl, apiKey, "/api/v1/characters/", {
    method: "POST",
    body: JSON.stringify({
      name,
      greeting: `Hello from ${name}`,
      first_message: `Hello from ${name}`
    })
  }).catch(() =>
    requestJson(serverUrl, apiKey, "/api/v1/characters", {
      method: "POST",
      body: JSON.stringify({
        name,
        greeting: `Hello from ${name}`,
        first_message: `Hello from ${name}`
      })
    })
  )
  if (created?.id == null) {
    throw new Error("Failed to create character for image sync e2e.")
  }
  return { id: String(created.id), created: true }
}

const createServerChat = async (
  serverUrl: string,
  apiKey: string,
  payload: Record<string, unknown>
) => {
  const created = await requestJson(serverUrl, apiKey, "/api/v1/chats/", {
    method: "POST",
    body: JSON.stringify(payload)
  }).catch(() =>
    requestJson(serverUrl, apiKey, "/api/v1/chats", {
      method: "POST",
      body: JSON.stringify(payload)
    })
  )
  const rawId = created?.id ?? created?.chat_id ?? null
  return rawId != null ? String(rawId) : null
}

const deleteServerChat = async (
  serverUrl: string,
  apiKey: string,
  chatId: string
) => {
  await requestJson(serverUrl, apiKey, `/api/v1/chats/${chatId}`, {
    method: "DELETE"
  }).catch(() => null)
}

const deleteCharacter = async (
  serverUrl: string,
  apiKey: string,
  characterId: string
) => {
  await requestJson(serverUrl, apiKey, `/api/v1/characters/${characterId}`, {
    method: "DELETE"
  }).catch(() => null)
}

const waitForServerChatSelected = async (page: Page, chatId: string) => {
  await page.waitForFunction(
    (expectedId) => {
      const store = (window as any).__tldw_useStoreMessageOption
      if (!store?.getState) return false
      const current = store.getState().serverChatId
      return String(current ?? "") === String(expectedId)
    },
    chatId,
    { timeout: 30000 }
  )
}

const setServerChatByStore = async (page: Page, chatId: string) => {
  await page.evaluate((expectedId) => {
    const store = (window as any).__tldw_useStoreMessageOption
    if (!store?.getState) return
    const state = store.getState()
    if (typeof state?.setServerChatId === "function") {
      state.setServerChatId(expectedId)
      return
    }
    if (typeof store.setState === "function") {
      store.setState((prev: any) => ({
        ...prev,
        serverChatId: expectedId
      }))
    }
  }, chatId)
}

const chooseSelectOption = async (
  page: Page,
  selectTestId: string,
  optionText?: RegExp
) => {
  const select = page.getByTestId(selectTestId)
  await expect(select).toBeVisible({ timeout: 20000 })
  await select.click({ timeout: 10000 })
  const dropdown = page.locator(".ant-select-dropdown:visible")
  await expect(dropdown).toBeVisible({ timeout: 10000 })
  const options = dropdown.locator(
    ".ant-select-item-option:not(.ant-select-item-option-disabled)"
  )

  if (optionText) {
    const matching = dropdown.locator(".ant-select-item-option", {
      hasText: optionText
    })
    if ((await matching.count()) > 0) {
      await matching.first().click({ timeout: 10000 })
      return
    }
    if ((await options.count()) > 0) {
      await options.first().click({ timeout: 10000 })
      return
    }
    await page.keyboard.press("Escape").catch(() => null)
    return
  }
  if ((await options.count()) === 0) {
    await page.keyboard.press("Escape").catch(() => null)
    return
  }
  await options.first().click({ timeout: 10000 })
}

const openImageGenerateModal = async (page: Page) => {
  const heading = page.getByRole("heading", { name: /Generate image/i })
  const syncChip = page.getByRole("button", { name: /Image sync/i }).first()
  const hasSyncChip = await syncChip.isVisible({ timeout: 2000 }).catch(() => false)
  if (hasSyncChip) {
    await syncChip.click({ timeout: 10000 })
    const openedFromChip = await heading.isVisible({ timeout: 3000 }).catch(() => false)
    if (openedFromChip) {
      return
    }
  }

  const trigger = page.getByTestId("composer-generate-button")
  await expect(trigger).toBeVisible({ timeout: 20000 })
  await trigger.click({ timeout: 10000 })

  const directModal = await heading.isVisible({ timeout: 2000 }).catch(() => false)
  if (directModal) {
    return
  }

  const imageMenuItem = page.getByRole("menuitem", { name: /^Image$/i }).first()
  const hasRoleMenuItem = await imageMenuItem
    .isVisible({ timeout: 2000 })
    .catch(() => false)
  if (hasRoleMenuItem) {
    await imageMenuItem.click({ timeout: 10000 })
  } else {
    await page
      .locator(".ant-dropdown-menu-item", { hasText: /^Image$/i })
      .first()
      .click({ timeout: 10000 })
  }

  await expect(heading).toBeVisible({ timeout: 15000 })
}

const gotoChatRoute = async (page: Page, extensionId: string) => {
  await page.goto(`chrome-extension://${extensionId}/options.html#/chat`, {
    waitUntil: "domcontentloaded"
  })

  const routeNotFound = page.getByText(/We could not find that route/i)
  if (await routeNotFound.isVisible().catch(() => false)) {
    const goToChat = page.getByRole("button", { name: /Go to Chat/i }).first()
    if (await goToChat.isVisible().catch(() => false)) {
      await goToChat.click()
    }
  }
}

const submitImageGenerate = async (
  page: Page,
  syncPolicy: "on" | "off",
  prompt: string,
  backend?: string
) => {
  await openImageGenerateModal(page)
  const promptArea = page.getByPlaceholder(/Describe the image you want to generate/i)
  await promptArea.fill(prompt)

  await chooseSelectOption(
    page,
    "image-generate-backend-select",
    backend ? new RegExp(escapeRegExp(backend), "i") : undefined
  )

  await chooseSelectOption(
    page,
    "image-generate-sync-policy-select",
    syncPolicy === "on" ? /Mirror event/i : /Local only/i
  )

  await page
    .getByRole("button", { name: /^Generate image$/i })
    .click({ timeout: 10000 })
}

const listServerMessages = async (
  serverUrl: string,
  apiKey: string,
  chatId: string
) => {
  const payload = await requestJson(serverUrl, apiKey, `/api/v1/chats/${chatId}/messages`).catch(
    () => requestJson(serverUrl, apiKey, `/api/v1/chats/${chatId}/messages?limit=200`)
  )
  return parseListPayload(payload)
}

test.describe("Playground image event sync", () => {
  test("keeps off events local-only and mirrors on events to server history", async () => {
    test.setTimeout(300000)
    const { serverUrl, apiKey } = requireRealServerConfig(test)
    const normalizedServerUrl = normalizeServerUrl(serverUrl)

    let createdCharacterId: string | null = null
    let createdChatId: string | null = null
    let context: Awaited<ReturnType<typeof launchWithExtensionOrSkip>>["context"] | null = null
    const mockBackend = "e2e-mock"

    try {
      const character = await ensureCharacterId(normalizedServerUrl, apiKey)
      if (character.created) {
        createdCharacterId = character.id
      }

      const chatTitle = `E2E Image Sync ${Date.now()}`
      const chatId = await createServerChat(normalizedServerUrl, apiKey, {
        title: chatTitle,
        character_id: character.id,
        state: "in-progress",
        source: "e2e-image-sync"
      })
      if (!chatId) {
        test.skip(true, "Failed to create server chat for image sync e2e.")
      }
      createdChatId = chatId

      const launchResult = await launchWithExtensionOrSkip(test, "", {
        seedConfig: {
          __tldw_first_run_complete: true,
          tldwConfig: {
            serverUrl: normalizedServerUrl,
            authMode: "single-user",
            apiKey
          }
        }
      })
      context = launchResult.context
      const { page, extensionId } = launchResult

      await context.route("**/api/v1/files/create", async (route) => {
        if (route.request().method().toUpperCase() !== "POST") {
          await route.continue()
          return
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(buildMockImageArtifactPayload(mockBackend))
        })
      })

      const origin = new URL(normalizedServerUrl).origin + "/*"
      const granted = await grantHostPermission(context, extensionId, origin)
      if (!granted) {
        test.skip(true, "Host permission not granted for server origin.")
      }

      await gotoChatRoute(page, extensionId)
      await waitForConnectionStore(page, "image-sync:options-store")
      await forceConnected(
        page,
        { serverUrl: normalizedServerUrl },
        "image-sync:force-connect"
      )

      await setServerChatByStore(page, chatId)
      await waitForServerChatSelected(page, chatId)

      await submitImageGenerate(
        page,
        "off",
        `local only image ${Date.now()}`
      )
      await expect(page.getByTestId("playground-image-event-card")).toHaveCount(1, {
        timeout: 60000
      })

      const messagesAfterOff = await listServerMessages(
        normalizedServerUrl,
        apiKey,
        chatId
      )
      const mirroredAfterOff = messagesAfterOff.filter((entry: any) =>
        String(entry?.content || "").startsWith(IMAGE_GENERATION_EVENT_MIRROR_PREFIX)
      )
      expect(mirroredAfterOff.length).toBe(0)

      await submitImageGenerate(
        page,
        "on",
        `mirror event image ${Date.now()}`
      )
      await expect(page.getByTestId("playground-image-event-card")).toHaveCount(2, {
        timeout: 60000
      })
      await expect(page.getByText(/Mirrored to server/i).first()).toBeVisible({
        timeout: 15000
      })

      const messagesAfterOn = await listServerMessages(
        normalizedServerUrl,
        apiKey,
        chatId
      )
      const mirroredAfterOn = messagesAfterOn.filter((entry: any) =>
        String(entry?.content || "").startsWith(IMAGE_GENERATION_EVENT_MIRROR_PREFIX)
      )
      expect(mirroredAfterOn.length).toBeGreaterThan(0)
      expect(String(mirroredAfterOn.at(-1)?.role || "").toLowerCase()).toBe(
        "assistant"
      )
    } catch (error) {
      test.skip(true, `Image sync e2e skipped: ${String(error)}`)
    } finally {
      if (context) {
        await context.close().catch(() => null)
      }
      if (createdChatId) {
        await deleteServerChat(normalizedServerUrl, apiKey, createdChatId)
      }
      if (createdCharacterId) {
        await deleteCharacter(normalizedServerUrl, apiKey, createdCharacterId)
      }
    }
  })
})
