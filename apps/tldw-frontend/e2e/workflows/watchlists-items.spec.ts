import type { Page, Route } from "@playwright/test"
import {
  test,
  expect,
  skipIfServerUnavailable,
  assertNoCriticalErrors
} from "../utils/fixtures"
import { seedAuth, waitForConnection } from "../utils/helpers"

type MockScrapedItem = {
  id: number
  run_id: number
  job_id: number
  source_id: number
  media_id: number | null
  media_uuid: string | null
  url: string
  title: string
  summary: string
  content: string
  published_at: string
  tags: string[]
  status: "ingested" | "filtered"
  reviewed: boolean
  created_at: string
}

const MOCK_SOURCES = [
  {
    id: 101,
    name: "BBC New",
    url: "https://feeds.bbci.co.uk/news/rss.xml",
    source_type: "rss",
    active: true,
    tags: ["news"],
    created_at: "2026-02-17T12:00:00Z",
    updated_at: "2026-02-17T12:00:00Z"
  },
  {
    id: 102,
    name: "cnBeta.COM",
    url: "https://www.cnbeta.com/rss.xml",
    source_type: "rss",
    active: true,
    tags: ["tech"],
    created_at: "2026-02-17T12:00:00Z",
    updated_at: "2026-02-17T12:00:00Z"
  }
]

const buildMockItems = (): MockScrapedItem[] => [
  {
    id: 9001,
    run_id: 500,
    job_id: 300,
    source_id: 101,
    media_id: null,
    media_uuid: null,
    url: "https://example.com/article-woodland",
    title: "Woodland Creatures Waken from Branches and Twigs",
    summary: "A profile of modern sculpture and environmental art.",
    content:
      '<p>Woodland sculpture is seeing a revival this season.</p><p>Artists are building large installations from reclaimed branches.</p><img src="https://images.example.com/woodland.jpg" alt="woodland" />',
    published_at: "2026-01-27T10:12:00Z",
    tags: ["art", "news"],
    status: "ingested",
    reviewed: false,
    created_at: "2026-01-27T10:12:00Z"
  },
  {
    id: 9002,
    run_id: 500,
    job_id: 300,
    source_id: 102,
    media_id: null,
    media_uuid: null,
    url: "https://example.com/article-rtx",
    title: "RTX 5090D power draw reaches 1765W in stress test",
    summary: "Lab notes from a high-load benchmark run.",
    content:
      "<p>Benchmarking reports an extremely high sustained draw under synthetic load.</p>",
    published_at: "2026-01-27T09:54:00Z",
    tags: ["hardware"],
    status: "ingested",
    reviewed: true,
    created_at: "2026-01-27T09:54:00Z"
  }
]

const jsonResponse = async (route: Route, payload: unknown) => {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(payload)
  })
}

const setupWatchlistsItemsRoutes = async (page: Page) => {
  let items = buildMockItems()
  const counters = {
    patchCalls: 0
  }

  await page.route(/\/api\/v1\/watchlists\/sources(?:\?.*)?$/, async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue()
      return
    }

    const url = new URL(route.request().url())
    const q = (url.searchParams.get("q") || "").toLowerCase().trim()
    const filtered = q
      ? MOCK_SOURCES.filter(
          (source) =>
            source.name.toLowerCase().includes(q) ||
            source.url.toLowerCase().includes(q) ||
            source.tags.some((tag) => tag.toLowerCase().includes(q))
        )
      : MOCK_SOURCES

    await jsonResponse(route, {
      items: filtered,
      total: filtered.length,
      page: Number(url.searchParams.get("page") || "1"),
      size: Number(url.searchParams.get("size") || "200")
    })
  })

  await page.route(/\/api\/v1\/watchlists\/items\/\d+(?:\?.*)?$/, async (route) => {
    const method = route.request().method()
    const id = Number(route.request().url().split("/").pop()?.split("?")[0])
    const found = items.find((item) => item.id === id)

    if (!found) {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not found" })
      })
      return
    }

    if (method === "PATCH") {
      counters.patchCalls += 1
      const updates = route.request().postDataJSON() as Partial<MockScrapedItem>
      const updated = {
        ...found,
        reviewed:
          typeof updates.reviewed === "boolean" ? updates.reviewed : found.reviewed
      }
      items = items.map((item) => (item.id === id ? updated : item))
      await jsonResponse(route, updated)
      return
    }

    if (method === "GET") {
      await jsonResponse(route, found)
      return
    }

    await route.continue()
  })

  await page.route(/\/api\/v1\/watchlists\/items(?:\?.*)?$/, async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue()
      return
    }

    const url = new URL(route.request().url())
    const pageNum = Number(url.searchParams.get("page") || "1")
    const size = Number(url.searchParams.get("size") || "25")
    const sourceId = Number(url.searchParams.get("source_id") || "0")
    const reviewed = url.searchParams.get("reviewed")
    const status = url.searchParams.get("status")
    const since = url.searchParams.get("since")
    const query = (url.searchParams.get("q") || "").toLowerCase().trim()

    let filtered = [...items]

    if (sourceId > 0) {
      filtered = filtered.filter((item) => item.source_id === sourceId)
    }

    if (status === "ingested" || status === "filtered") {
      filtered = filtered.filter((item) => item.status === status)
    }

    if (reviewed === "true") {
      filtered = filtered.filter((item) => item.reviewed)
    } else if (reviewed === "false") {
      filtered = filtered.filter((item) => !item.reviewed)
    }

    if (since) {
      const sinceMs = Date.parse(since)
      if (!Number.isNaN(sinceMs)) {
        filtered = filtered.filter((item) => {
          const publishedMs = Date.parse(item.published_at || item.created_at)
          const createdMs = Date.parse(item.created_at)
          return publishedMs >= sinceMs || createdMs >= sinceMs
        })
      }
    }

    if (query) {
      filtered = filtered.filter((item) => {
        const haystack = `${item.title} ${item.summary} ${item.content}`.toLowerCase()
        return haystack.includes(query)
      })
    }

    filtered.sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at))

    const total = filtered.length
    const start = Math.max(0, (pageNum - 1) * size)
    const pagedItems = filtered.slice(start, start + size)

    await jsonResponse(route, {
      items: pagedItems,
      total,
      page: pageNum,
      size
    })
  })

  return counters
}

test.describe("Watchlists Items Reader", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test("uses most of the available horizontal space on large viewports", async ({
    authedPage,
    serverInfo,
    diagnostics
  }) => {
    skipIfServerUnavailable(serverInfo)

    await authedPage.setViewportSize({ width: 1800, height: 1100 })
    await setupWatchlistsItemsRoutes(authedPage)

    await authedPage.goto("/watchlists")
    await waitForConnection(authedPage)

    await authedPage.getByRole("tab", { name: /^Items$/ }).click()
    const layout = authedPage.getByTestId("watchlists-items-layout")
    await expect(layout).toBeVisible()

    const layoutWidth = await layout.evaluate((node) =>
      Math.round(node.getBoundingClientRect().width)
    )
    expect(layoutWidth).toBeGreaterThan(1450)

    await expect(authedPage.getByTestId("watchlists-items-left-pane")).toBeVisible()
    await expect(authedPage.getByTestId("watchlists-items-list-pane")).toBeVisible()
    await expect(authedPage.getByTestId("watchlists-items-reader-pane")).toBeVisible()

    await assertNoCriticalErrors(diagnostics)
  })

  test("renders selected feed item content and supports reviewed toggle", async ({
    authedPage,
    serverInfo,
    diagnostics
  }) => {
    skipIfServerUnavailable(serverInfo)

    const counters = await setupWatchlistsItemsRoutes(authedPage)

    await authedPage.goto("/watchlists")
    await waitForConnection(authedPage)

    await authedPage.getByRole("tab", { name: /^Items$/ }).click()

    const row1 = authedPage.getByTestId("watchlists-item-row-9001")
    await expect(row1).toBeVisible()

    const reader = authedPage.getByTestId("watchlists-item-reader")
    await expect(reader).toContainText("Woodland Creatures Waken from Branches and Twigs")
    await expect(reader).toContainText("Woodland sculpture is seeing a revival")

    const reviewButton = authedPage.getByRole("button", { name: /Mark as reviewed/i })
    await reviewButton.click()

    await expect(authedPage.getByRole("button", { name: /Mark as unreviewed/i })).toBeVisible()
    expect(counters.patchCalls).toBe(1)

    await authedPage.getByTestId("watchlists-item-row-9002").click()
    await expect(reader).toContainText("RTX 5090D power draw reaches 1765W in stress test")
    await expect(reader).toContainText("Benchmarking reports an extremely high sustained draw")

    await assertNoCriticalErrors(diagnostics)
  })
})
