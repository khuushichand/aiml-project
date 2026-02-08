import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn(),
  bgUpload: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args),
  bgUpload: (...args: unknown[]) => mocks.bgUpload(...args)
}))

import { fetchJobOutputTemplates } from "@/services/watchlists"

describe("watchlists template option services", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("fetches canonical output templates with query params and maps payload", async () => {
    mocks.bgRequest.mockResolvedValueOnce({
      items: [
        {
          id: 11,
          name: "briefing_markdown",
          format: "md",
          updated_at: "2026-01-15T00:00:00Z"
        },
        {
          id: "22",
          name: "newsletter_html",
          format: "html"
        }
      ],
      total: 2
    })

    const result = await fetchJobOutputTemplates({ q: "brief", limit: 20, offset: 5 })

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/outputs/templates?q=brief&limit=20&offset=5",
        method: "GET"
      })
    )
    expect(result).toEqual({
      items: [
        {
          id: "11",
          name: "briefing_markdown",
          format: "md",
          updated_at: "2026-01-15T00:00:00Z"
        },
        {
          id: "22",
          name: "newsletter_html",
          format: "html",
          updated_at: null
        }
      ],
      total: 2
    })
  })

  it("drops invalid template names and falls back defaults for optional fields", async () => {
    mocks.bgRequest.mockResolvedValueOnce({
      items: [
        { id: 1, name: "" },
        { id: 2, name: "   " },
        { id: 3, name: "valid_template", format: 42, updated_at: 10 }
      ]
    })

    const result = await fetchJobOutputTemplates()

    expect(result).toEqual({
      items: [
        {
          id: "3",
          name: "valid_template",
          format: "md",
          updated_at: null
        }
      ],
      total: 1
    })
  })
})
