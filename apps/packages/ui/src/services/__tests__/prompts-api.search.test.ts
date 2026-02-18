import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  apiSend: vi.fn()
}))

vi.mock("@/services/api-send", () => ({
  apiSend: (...args: unknown[]) =>
    (mocks.apiSend as (...args: unknown[]) => unknown)(...args)
}))

const importPromptsApi = async () => import("@/services/prompts-api")

describe("prompts-api search", () => {
  beforeEach(() => {
    vi.resetModules()
    mocks.apiSend.mockReset()
  })

  it("builds search query with fields, paging, and deleted flag", async () => {
    const { buildPromptSearchQuery } = await importPromptsApi()
    const query = buildPromptSearchQuery({
      searchQuery: "hello world",
      searchFields: ["name", "keywords"],
      page: 3,
      resultsPerPage: 50,
      includeDeleted: true
    })

    expect(query).toContain("search_query=hello+world")
    expect(query).toContain("search_fields=name")
    expect(query).toContain("search_fields=keywords")
    expect(query).toContain("page=3")
    expect(query).toContain("results_per_page=50")
    expect(query).toContain("include_deleted=true")
  })

  it("calls the prompts search endpoint and returns response data", async () => {
    mocks.apiSend.mockResolvedValue({
      ok: true,
      status: 200,
      data: {
        items: [{ id: 7, uuid: "u-7", name: "Prompt 7" }],
        total_matches: 1,
        page: 2,
        per_page: 10
      }
    })
    const { searchPromptsServer } = await importPromptsApi()
    const result = await searchPromptsServer({
      searchQuery: "prompt",
      page: 2,
      resultsPerPage: 10
    })

    expect(mocks.apiSend).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "POST"
      })
    )
    const call = mocks.apiSend.mock.calls[0]?.[0]
    expect(call.path).toContain("/api/v1/prompts/search?")
    expect(call.path).toContain("search_query=prompt")
    expect(result.total_matches).toBe(1)
    expect(result.items).toHaveLength(1)
  })

  it("uses safe defaults when endpoint returns empty payload", async () => {
    mocks.apiSend.mockResolvedValue({
      ok: true,
      status: 200
    })
    const { searchPromptsServer } = await importPromptsApi()
    const result = await searchPromptsServer({
      searchQuery: "missing",
      page: 4,
      resultsPerPage: 25
    })

    expect(result).toEqual({
      items: [],
      total_matches: 0,
      page: 4,
      per_page: 25
    })
  })

  it("throws when the search endpoint returns an error", async () => {
    mocks.apiSend.mockResolvedValue({
      ok: false,
      status: 500,
      error: "boom"
    })
    const { searchPromptsServer } = await importPromptsApi()

    await expect(searchPromptsServer({ searchQuery: "x" })).rejects.toThrow("boom")
  })

  it("builds export query and calls export endpoint for markdown", async () => {
    mocks.apiSend.mockResolvedValue({
      ok: true,
      status: 200,
      data: {
        message: "ok",
        file_content_b64: "YWJj"
      }
    })

    const { buildPromptExportQuery, exportPromptsServer } = await importPromptsApi()
    expect(buildPromptExportQuery("csv")).toContain("export_format=csv")

    const result = await exportPromptsServer("markdown")
    expect(mocks.apiSend).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "GET"
      })
    )
    const call = mocks.apiSend.mock.calls[mocks.apiSend.mock.calls.length - 1]?.[0]
    expect(call.path).toContain("/api/v1/prompts/export?")
    expect(call.path).toContain("export_format=markdown")
    expect(result.file_content_b64).toBe("YWJj")
  })

  it("calls export endpoint for csv format", async () => {
    mocks.apiSend.mockResolvedValue({
      ok: true,
      status: 200,
      data: {
        message: "ok",
        file_content_b64: "Y3N2"
      }
    })

    const { exportPromptsServer } = await importPromptsApi()
    const result = await exportPromptsServer("csv")

    const call = mocks.apiSend.mock.calls[mocks.apiSend.mock.calls.length - 1]?.[0]
    expect(call.path).toContain("export_format=csv")
    expect(result.file_content_b64).toBe("Y3N2")
  })

  it("returns empty export response shape when payload is missing", async () => {
    mocks.apiSend.mockResolvedValue({
      ok: true,
      status: 200
    })

    const { exportPromptsServer } = await importPromptsApi()
    const result = await exportPromptsServer("csv")

    expect(result).toEqual({
      message: ""
    })
  })

  it("throws when export endpoint returns an error", async () => {
    mocks.apiSend.mockResolvedValue({
      ok: false,
      status: 500,
      error: "export failed"
    })

    const { exportPromptsServer } = await importPromptsApi()
    await expect(exportPromptsServer("markdown")).rejects.toThrow("export failed")
  })
})
