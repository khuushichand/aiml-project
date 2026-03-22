import { test, expect, skipIfServerUnavailable, assertNoCriticalErrors } from "../utils/fixtures"
import type { Page } from "@playwright/test"
import { TEST_CONFIG, fetchWithApiKey } from "../utils/helpers"
import { expectApiCall } from "../utils/api-assertions"

interface SeededReadingItem {
  itemId: string
  title: string
  quote: string
  highlightId?: string
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

const seedAppAuth = async (page: Page) => {
  await page.context().addInitScript((cfg) => {
    try {
      localStorage.setItem(
        "tldwConfig",
        JSON.stringify({
          serverUrl: cfg.serverUrl,
          apiKey: cfg.apiKey,
          authMode: "single-user"
        })
      )
      localStorage.setItem("__tldw_first_run_complete", "true")
      localStorage.setItem("__tldw_allow_offline", "true")
    } catch {
      // Ignore localStorage failures in hardened browser contexts.
    }
  }, { serverUrl: TEST_CONFIG.serverUrl, apiKey: TEST_CONFIG.apiKey })
}

const createReadingItem = async (label: string): Promise<SeededReadingItem> => {
  const quote = `stage3-quote-${Date.now()}`
  const title = `Stage3 ${label} ${Date.now()}`
  const response = await fetchWithApiKey(
    `${TEST_CONFIG.serverUrl}/api/v1/reading/save`,
    TEST_CONFIG.apiKey,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: `https://example.com/${Date.now()}-${Math.random().toString(36).slice(2)}`,
        title,
        content: `This is seeded content for ${label}. ${quote} appears here for selection testing.`,
        notes: ""
      })
    }
  )
  if (!response.ok) {
    throw new Error(`Failed to seed reading item: ${response.status} ${await response.text()}`)
  }
  const payload = await response.json()
  return { itemId: String(payload.id), title, quote }
}

const waitForReadingItemIndexed = async (title: string, expectedItemId: string) => {
  const endpoint =
    `${TEST_CONFIG.serverUrl}/api/v1/reading/items?page=1&size=25&q=${encodeURIComponent(title)}`
  for (let attempt = 0; attempt < 10; attempt += 1) {
    const response = await fetchWithApiKey(endpoint, TEST_CONFIG.apiKey)
    if (response.ok) {
      const payload = await response.json()
      const items: Array<{ id?: number | string }> = Array.isArray(payload?.items)
        ? payload.items
        : []
      if (items.some((item) => String(item.id) === expectedItemId)) {
        return
      }
    }
    await sleep(500)
  }
  throw new Error(`Seeded reading item was not queryable by title: ${title}`)
}

const createHighlight = async (itemId: string, quote: string): Promise<string> => {
  const response = await fetchWithApiKey(
    `${TEST_CONFIG.serverUrl}/api/v1/reading/items/${itemId}/highlight`,
    TEST_CONFIG.apiKey,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        item_id: Number(itemId),
        quote,
        color: "yellow",
        note: "seeded stale candidate"
      })
    }
  )
  if (!response.ok) {
    throw new Error(`Failed to seed highlight: ${response.status} ${await response.text()}`)
  }
  const payload = await response.json()
  return String(payload.id)
}

const patchHighlightState = async (highlightId: string, state: "active" | "stale") => {
  const response = await fetchWithApiKey(
    `${TEST_CONFIG.serverUrl}/api/v1/reading/highlights/${highlightId}`,
    TEST_CONFIG.apiKey,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state })
    }
  )
  if (!response.ok) {
    throw new Error(`Failed to patch highlight state: ${response.status} ${await response.text()}`)
  }
}

const listHighlights = async (itemId: string): Promise<Array<{ id: number; quote: string; state: string }>> => {
  const response = await fetchWithApiKey(
    `${TEST_CONFIG.serverUrl}/api/v1/reading/items/${itemId}/highlights`,
    TEST_CONFIG.apiKey
  )
  if (!response.ok) {
    throw new Error(`Failed to list highlights: ${response.status} ${await response.text()}`)
  }
  return await response.json()
}

const openCollectionsPage = async (page: Page) => {
  const collectionsUrl = `${TEST_CONFIG.webUrl.replace(/\/$/, "")}/collections`
  await page.goto(collectionsUrl, { waitUntil: "domcontentloaded" })
  await expect(page.getByRole("heading", { name: /Collections/i })).toBeVisible({ timeout: 25_000 })
}

const openReadingItemByTitle = async (
  page: Page,
  title: string
) => {
  const searchInput = page.getByPlaceholder(/Search articles/i)
  await expect(searchInput).toBeVisible({ timeout: 20_000 })
  await searchInput.fill(title)

  const refreshButton = page.getByRole("button", { name: /Refresh/i })
  if (await refreshButton.isVisible().catch(() => false)) {
    await refreshButton.click()
  }

  const card = page
    .locator("div[role='button']")
    .filter({ has: page.getByRole("heading", { name: title, exact: false }) })
    .first()
  await expect(card).toBeVisible({ timeout: 20_000 })
  await card.click()
  await expect(page.locator(".reading-item-detail-drawer")).toBeVisible({ timeout: 15_000 })
}

const selectPhraseInContent = async (
  page: Page,
  phrase: string
): Promise<boolean> => {
  return await page.evaluate((needle) => {
    const root = document.querySelector(".reading-item-detail-drawer .prose")
    if (!root) return false

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
    let textNode: Text | null = null
    let start = -1
    while (walker.nextNode()) {
      const candidate = walker.currentNode as Text
      const index = candidate.textContent?.indexOf(needle) ?? -1
      if (index >= 0) {
        textNode = candidate
        start = index
        break
      }
    }
    if (!textNode || start < 0) return false

    const range = document.createRange()
    range.setStart(textNode, start)
    range.setEnd(textNode, start + needle.length)
    const selection = window.getSelection()
    if (!selection) return false
    selection.removeAllRanges()
    selection.addRange(range)
    root.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }))
    return true
  }, phrase)
}

test.describe("Collections Stage 3 Skeleton", () => {
  test("selection quick actions can create highlight from reader content", async ({
    authedPage,
    serverInfo,
    diagnostics
  }) => {
    skipIfServerUnavailable(serverInfo)
    await seedAppAuth(authedPage)
    const seed = await createReadingItem("Selection")
    await waitForReadingItemIndexed(seed.title, seed.itemId)

    await openCollectionsPage(authedPage)
    await openReadingItemByTitle(authedPage, seed.title)
    await expect(authedPage.locator(".reading-item-detail-drawer .prose")).toContainText(seed.quote, {
      timeout: 15_000
    })

    const selectionOk = await selectPhraseInContent(authedPage, seed.quote)
    expect(selectionOk).toBeTruthy()

    await expect(
      authedPage.getByText(/Selected text captured|Selected text matches an existing highlight/i)
    ).toBeVisible({ timeout: 10_000 })

    const highlightApiCall = expectApiCall(authedPage, {
      method: "POST",
      url: "/api/v1/reading/"
    })
    await authedPage
      .locator(".reading-item-detail-drawer")
      .getByRole("button", { name: /Add Highlight|Update/i })
      .first()
      .click()
    const { response: highlightResponse } = await highlightApiCall
    expect(highlightResponse.status()).toBeLessThan(400)
    await expect(
      authedPage.getByText(/Selected text captured|Selected text matches an existing highlight/i)
    ).not.toBeVisible({ timeout: 10_000 })

    const highlights = await listHighlights(seed.itemId)
    expect(highlights.some((h) => h.quote.includes(seed.quote))).toBeTruthy()

    await assertNoCriticalErrors(diagnostics)
  })

  test("stale highlights show badge in Highlights tab", async ({
    authedPage,
    serverInfo,
    diagnostics
  }) => {
    skipIfServerUnavailable(serverInfo)
    await seedAppAuth(authedPage)
    const seed = await createReadingItem("StaleBadge")
    await waitForReadingItemIndexed(seed.title, seed.itemId)
    const highlightId = await createHighlight(seed.itemId, seed.quote)
    await patchHighlightState(highlightId, "stale")

    await openCollectionsPage(authedPage)
    const highlightsTab = authedPage.locator(".collections-tabs").getByRole("tab", { name: /Highlights/i })
    await expect(highlightsTab).toBeVisible({ timeout: 20_000 })
    await highlightsTab.click()
    const highlightsPanel = authedPage.getByRole("tabpanel", { name: /Highlights/i })

    const searchInput = authedPage.getByPlaceholder(/Search highlights/i)
    await expect(searchInput).toBeVisible({ timeout: 15_000 })
    await searchInput.fill(seed.quote)

    await expect(highlightsPanel.getByText("Stale", { exact: true })).toBeVisible({
      timeout: 15_000
    })
    await expect(highlightsPanel.locator("blockquote", { hasText: seed.quote })).toBeVisible({
      timeout: 15_000
    })

    await assertNoCriticalErrors(diagnostics)
  })

  test("notes show dirty/saving states and persist after autosave", async ({
    authedPage,
    serverInfo,
    diagnostics
  }) => {
    skipIfServerUnavailable(serverInfo)
    await seedAppAuth(authedPage)
    const seed = await createReadingItem("NotesAutosave")
    await waitForReadingItemIndexed(seed.title, seed.itemId)
    const noteText = `autosave-note-${Date.now()}`

    await openCollectionsPage(authedPage)
    await openReadingItemByTitle(authedPage, seed.title)

    await authedPage.getByRole("tab", { name: /Notes/i }).click()
    await authedPage.getByRole("button", { name: /Add Notes|Edit Notes/i }).click()

    const notesBox = authedPage.locator(".reading-item-detail-drawer textarea").first()
    const saveApiCall = expectApiCall(authedPage, { url: "/api/v1/reading/" })
    await notesBox.fill(noteText)

    await expect(authedPage.getByText(/Unsaved changes/i)).toBeVisible({ timeout: 5_000 })
    await expect(authedPage.getByText(/All changes saved/i)).toBeVisible({ timeout: 12_000 })
    const { response: saveResponse } = await saveApiCall
    expect(saveResponse.status()).toBeLessThan(400)

    await authedPage
      .locator(".reading-item-detail-drawer")
      .getByRole("button", { name: "Close" })
      .click()
    await expect(authedPage.locator(".reading-item-detail-drawer")).not.toBeVisible({
      timeout: 10_000
    })

    await openReadingItemByTitle(authedPage, seed.title)
    await authedPage.getByRole("tab", { name: /Notes/i }).click()
    await expect(authedPage.getByText(noteText)).toBeVisible({ timeout: 10_000 })

    await assertNoCriticalErrors(diagnostics)
  })
})
