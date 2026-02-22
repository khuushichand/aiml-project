import fs from "node:fs/promises"
import path from "node:path"
import type { APIRequestContext, Locator, Page } from "@playwright/test"
import {
  test,
  expect,
  skipIfServerUnavailable
} from "../utils/fixtures"
import { TEST_CONFIG } from "../utils/helpers"

type VerificationCase = {
  mediaId: number
  searchQuery: string
  expectedNodeCount: number
  expectedPage: number
  sectionTitle: string
}

type ScrollSnapshot = {
  containerTop: number
  windowY: number
  docTop: number
}

type VerificationResult = {
  mediaId: number
  mediaTitle: string
  expectedNodeCount: number
  actualNodeCountFromApi: number
  actualNodeCountFromBadge: number | null
  expectedPage: number
  pageBadge: string
  sectionTitle: string
  maxScrollDelta: number
  screenshotPath: string
}

const CASES: VerificationCase[] = [
  {
    mediaId: 121,
    searchQuery: "Query Decomposition for RAG",
    expectedNodeCount: 22,
    expectedPage: 8,
    sectionTitle: "Conclusions"
  },
  {
    mediaId: 123,
    searchQuery: "CC_Frankenstein_Reader_W1",
    expectedNodeCount: 30,
    expectedPage: 265,
    sectionTitle: "Chapter 24"
  },
  {
    mediaId: 143,
    searchQuery: "Dark Energy After DESI DR2",
    expectedNodeCount: 47,
    expectedPage: 21,
    sectionTitle: "VIII. Conclusions and outlook"
  }
]

const RESULTS_DIR = path.join("test-results")
const REPORT_PATH = path.join(RESULTS_DIR, "media-navigation-ux-report.json")

const normalizeWhitespace = (value: string): string =>
  value.replace(/\s+/g, " ").trim()

const isMediaDetailResponse = (url: string): boolean => {
  if (!url.includes("/api/v1/media/")) return false
  if (url.includes("/api/v1/media/search")) return false
  if (url.includes("/navigation")) return false
  if (url.includes("/versions")) return false
  if (url.includes("/file")) return false
  return /\/api\/v1\/media\/\d+/.test(url)
}

const parseNodeCountFromResponse = (payload: unknown): number => {
  if (!payload || typeof payload !== "object") return 0
  const maybeNodes = (payload as { nodes?: unknown }).nodes
  return Array.isArray(maybeNodes) ? maybeNodes.length : 0
}

const parseNodeCountFromStatusText = (text: string | null): number | null => {
  const normalized = normalizeWhitespace(text || "")
  const match = normalized.match(/(?:Sections|Generated sections):\s*(\d+)/i)
  if (!match) return null
  const parsed = Number.parseInt(match[1], 10)
  return Number.isFinite(parsed) ? parsed : null
}

const getScrollSnapshot = async (page: Page): Promise<ScrollSnapshot> =>
  page.evaluate(() => {
    const container = document.querySelector(
      "div.flex-1.overflow-y-auto.p-4"
    ) as HTMLElement | null
    const docScroller =
      document.scrollingElement instanceof HTMLElement
        ? document.scrollingElement
        : document.documentElement

    return {
      containerTop: container?.scrollTop ?? 0,
      windowY: window.scrollY ?? 0,
      docTop: docScroller?.scrollTop ?? 0
    }
  })

const computeScrollDelta = (before: ScrollSnapshot, after: ScrollSnapshot): number =>
  Math.max(
    Math.abs(after.containerTop - before.containerTop),
    Math.abs(after.windowY - before.windowY),
    Math.abs(after.docTop - before.docTop)
  )

const waitForSignificantScroll = async (
  page: Page,
  before: ScrollSnapshot,
  threshold = 80,
  timeoutMs = 5000
): Promise<number> => {
  const startedAt = Date.now()
  let maxDelta = 0

  while (Date.now() - startedAt < timeoutMs) {
    await page.waitForTimeout(160)
    const current = await getScrollSnapshot(page)
    const delta = computeScrollDelta(before, current)
    if (delta > maxDelta) maxDelta = delta
    if (maxDelta >= threshold) return maxDelta
  }

  return maxDelta
}

const getMediaTitle = async (
  request: APIRequestContext,
  mediaId: number
): Promise<string> => {
  const urlCandidates = [
    `${TEST_CONFIG.serverUrl}/api/v1/media/${mediaId}?include_content=false`,
    `${TEST_CONFIG.serverUrl}/api/v1/media/${mediaId}`
  ]

  for (const url of urlCandidates) {
    const resp = await request.get(url, {
      headers: {
        "x-api-key": TEST_CONFIG.apiKey
      }
    })
    if (!resp.ok()) continue
    const payload = await resp.json().catch(() => null)
    const titleCandidates = [
      payload?.title,
      payload?.source?.title,
      payload?.media?.title,
      payload?.data?.title,
      payload?.item?.title,
      payload?.media_item?.title,
      payload?.filename,
      payload?.source?.filename
    ]
      .map((v: unknown) => (typeof v === "string" ? v.trim() : ""))
      .filter(Boolean)

    if (titleCandidates.length > 0) return titleCandidates[0]
  }

  throw new Error(`Could not load media title for ID ${mediaId}`)
}

const ensureSearchInputVisible = async (
  page: Page
) => {
  const searchInput = page.locator("input[placeholder*='Search media']").first()
  if (await searchInput.isVisible().catch(() => false)) return searchInput

  const searchToggle = page.getByRole("button", { name: /^Search$/i }).first()
  if (await searchToggle.isVisible().catch(() => false)) {
    const expanded = (await searchToggle.getAttribute("aria-expanded")) === "true"
    if (!expanded) {
      await searchToggle.click()
    }
  }

  await expect(searchInput).toBeVisible({ timeout: 10_000 })
  return searchInput
}

const findVisibleSearchButton = async (page: Page): Promise<Locator | null> => {
  const panelButton = page
    .locator("#media-search-panel")
    .getByRole("button", { name: /^Search$/i })
    .first()
  if (await panelButton.isVisible().catch(() => false)) {
    return panelButton
  }

  const buttons = page.getByRole("button", { name: /^Search$/i })
  const count = await buttons.count()
  for (let idx = count - 1; idx >= 0; idx -= 1) {
    const button = buttons.nth(idx)
    if (await button.isVisible().catch(() => false)) {
      return button
    }
  }
  return null
}

const tryFindMatchingMediaRow = async (
  page: Page,
  needles: string[],
  attempts = 8
): Promise<Locator | null> => {
  const normalizedNeedles = needles
    .map((needle) => normalizeWhitespace(needle).toLowerCase())
    .filter((needle) => needle.length > 0)

  const templatedRows = page.locator("[aria-label^='Select {{type}}: {{title}}']")
  const fallbackRows = page.locator("div[role='button'][aria-selected]")

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const rows = (await templatedRows.count()) > 0 ? templatedRows : fallbackRows
    const rowCount = await rows.count()
    for (let idx = 0; idx < Math.min(rowCount, 80); idx += 1) {
      const row = rows.nth(idx)
      const text = normalizeWhitespace((await row.textContent()) || "")
      const normalizedText = text.toLowerCase()
      if (normalizedNeedles.some((needle) => normalizedText.includes(needle))) {
        return row
      }
    }
    await page.waitForTimeout(450)
  }

  return null
}

const selectMediaResult = async (
  page: Page,
  mediaId: number,
  title: string,
  preferredQuery: string
) => {
  const searchInput = await ensureSearchInputVisible(page)
  const searchButton = await findVisibleSearchButton(page)
  const queryVariants = Array.from(
    new Set([preferredQuery, title, String(mediaId)])
  ).filter((query) => query.trim().length > 0)
  const rowNeedles = [
    title,
    preferredQuery,
    `media ${mediaId}`,
    String(mediaId)
  ]

  let matchingRow: Locator | null = null
  for (const query of queryVariants) {
    await searchInput.fill("")
    await page.waitForTimeout(180)
    await searchInput.fill(query)
    if (searchButton) {
      await searchButton.click({ force: true }).catch(() => {})
    }
    await searchInput.press("Enter").catch(() => {})
    await page.waitForTimeout(250)

    matchingRow = await tryFindMatchingMediaRow(page, rowNeedles)
    if (matchingRow) break
  }

  if (!matchingRow) {
    throw new Error(`Could not find media row for ID ${mediaId} after retries`)
  }

  const navResponsePromise = page.waitForResponse(
    (response) => {
      const url = response.url()
      return (
        url.includes(`/api/v1/media/${mediaId}/navigation`) &&
        response.request().method() === "GET"
      )
    },
    { timeout: 30_000 }
  )

  const detailResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes(`/api/v1/media/${mediaId}`) &&
      isMediaDetailResponse(response.url()) &&
      response.request().method() === "GET",
    { timeout: 30_000 }
  )

  await matchingRow.click({ force: true })

  const [navResponse, detailResponse] = await Promise.all([
    navResponsePromise,
    detailResponsePromise
  ])

  const selectedIdMatch = detailResponse.url().match(/\/api\/v1\/media\/(\d+)/)
  const selectedId = selectedIdMatch ? Number.parseInt(selectedIdMatch[1], 10) : NaN
  if (!Number.isFinite(selectedId) || selectedId !== mediaId) {
    throw new Error(
      `Selected media mismatch: expected ${mediaId}, got ${Number.isFinite(selectedId) ? selectedId : "unknown"}`
    )
  }

  const navPayload = await navResponse.json().catch(() => null)
  return parseNodeCountFromResponse(navPayload)
}

test.describe("Media Navigation UX Verification", () => {
  test("verifies section navigation UX for media 121/123/143 on live stack", async ({
    authedPage,
    serverInfo,
    request
  }) => {
    skipIfServerUnavailable(serverInfo)

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
          // ignore localStorage errors in test bootstrap
        }
        try {
          localStorage.setItem("__tldw_first_run_complete", "true")
        } catch {
          // ignore localStorage errors in test bootstrap
        }
        try {
          localStorage.setItem("__tldw_allow_offline", "true")
        } catch {
          // ignore localStorage errors in test bootstrap
        }
      },
      {
        serverUrl: TEST_CONFIG.serverUrl,
        apiKey: TEST_CONFIG.apiKey
      }
    )

    await fs.mkdir(RESULTS_DIR, { recursive: true })

    await authedPage.goto("/media", { waitUntil: "domcontentloaded" })
    await expect(
      authedPage.getByRole("heading", { name: /Media Inspector/i })
    ).toBeVisible({ timeout: 30_000 })

    const results: VerificationResult[] = []

    for (const item of CASES) {
      const mediaTitle = await getMediaTitle(request, item.mediaId)

      const actualNodeCountFromApi = await selectMediaResult(
        authedPage,
        item.mediaId,
        mediaTitle,
        item.searchQuery
      )

      const statusBadge = authedPage.locator("div.border-b.border-border.bg-surface.px-3.py-2 span").last()
      await expect(statusBadge).toBeVisible({ timeout: 20_000 })
      await expect(statusBadge).not.toContainText(/Loading sections/i, {
        timeout: 20_000
      })

      const actualNodeCountFromBadge = parseNodeCountFromStatusText(
        await statusBadge.textContent()
      )

      expect(actualNodeCountFromApi).toBeGreaterThanOrEqual(
        item.expectedNodeCount - 2
      )
      expect(actualNodeCountFromApi).toBeLessThanOrEqual(
        item.expectedNodeCount + 2
      )
      if (actualNodeCountFromBadge !== null) {
        expect(actualNodeCountFromBadge).toBe(actualNodeCountFromApi)
      }

      const sectionNavigator = authedPage.getByLabel("Chapters and sections")
      await expect(sectionNavigator).toBeVisible({ timeout: 20_000 })

      const quickJumpInput = sectionNavigator.getByPlaceholder("Jump to 12.5 or title")
      await expect(quickJumpInput).toBeVisible({ timeout: 10_000 })
      await quickJumpInput.fill(item.sectionTitle)

      const targetSectionButton = sectionNavigator
        .locator("button")
        .filter({ hasText: item.sectionTitle })
        .first()
      await expect(targetSectionButton).toBeVisible({ timeout: 15_000 })

      const before = await getScrollSnapshot(authedPage)
      await targetSectionButton.click()

      const contentCard = authedPage
        .locator("div.bg-surface.border.border-border.rounded-lg.mb-2.overflow-hidden")
        .first()
      const pageBadge = contentCard.getByText(
        new RegExp(`^Page\\s+${item.expectedPage}$`)
      )
      await expect(pageBadge).toBeVisible({ timeout: 20_000 })

      const maxScrollDelta = await waitForSignificantScroll(authedPage, before)
      expect(maxScrollDelta).toBeGreaterThan(80)

      const screenshotPath = path.join(
        RESULTS_DIR,
        `media-navigation-ux-${item.mediaId}.png`
      )
      await authedPage.screenshot({
        path: screenshotPath,
        fullPage: true
      })

      const pageBadgeText = normalizeWhitespace(
        (await pageBadge.textContent()) || ""
      )

      const result: VerificationResult = {
        mediaId: item.mediaId,
        mediaTitle,
        expectedNodeCount: item.expectedNodeCount,
        actualNodeCountFromApi,
        actualNodeCountFromBadge,
        expectedPage: item.expectedPage,
        pageBadge: pageBadgeText,
        sectionTitle: item.sectionTitle,
        maxScrollDelta,
        screenshotPath
      }
      results.push(result)

      // Keep test output readable in CI logs.
      console.log(
        `[media-navigation-ux] media=${item.mediaId} count=${actualNodeCountFromApi} badge="${pageBadgeText}" scrollDelta=${Math.round(
          maxScrollDelta
        )}`
      )
    }

    await fs.writeFile(REPORT_PATH, JSON.stringify(results, null, 2), "utf-8")

    expect(results).toHaveLength(CASES.length)
    for (const item of results) {
      expect(item.pageBadge).toBe(`Page ${item.expectedPage}`)
    }
  })
})
