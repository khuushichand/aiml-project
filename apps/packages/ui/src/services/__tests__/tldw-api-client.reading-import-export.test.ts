import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn(),
  bgUpload: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args),
  bgUpload: (...args: unknown[]) => mocks.bgUpload(...args),
  bgStream: vi.fn()
}))

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: vi.fn(async () => null),
    set: vi.fn(async () => undefined),
    remove: vi.fn(async () => undefined)
  }),
  safeStorageSerde: {
    serialize: (value: unknown) => value,
    deserialize: (value: unknown) => value
  }
}))

import { TldwApiClient } from "@/services/tldw/TldwApiClient"

describe("TldwApiClient reading import/export stage 2 wiring", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("uploads reading imports with source and merge_tags", async () => {
    mocks.bgUpload.mockResolvedValue({
      job_id: 9,
      job_uuid: "job-9",
      status: "queued"
    })

    const client = new TldwApiClient()
    ;(client as any).ensureConfigForRequest = vi.fn(async () => ({ ok: true }))

    const file = {
      name: "pocket.json",
      type: "application/json",
      arrayBuffer: vi.fn(async () => new TextEncoder().encode("{}").buffer)
    } as unknown as File
    const response = await client.importReadingList({
      source: "pocket",
      file,
      merge_tags: false
    })

    expect(response).toEqual({
      job_id: 9,
      job_uuid: "job-9",
      status: "queued"
    })
    expect(mocks.bgUpload).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/reading/import",
        method: "POST",
        fileFieldName: "file",
        fields: {
          source: "pocket",
          merge_tags: false
        }
      })
    )
  })

  it("calls reading import job status endpoints", async () => {
    mocks.bgRequest.mockResolvedValueOnce({ jobs: [], total: 0, limit: 10, offset: 5 })
    mocks.bgRequest.mockResolvedValueOnce({ job_id: 12, status: "processing" })

    const client = new TldwApiClient()

    const listResult = await client.listReadingImportJobs({
      status: "processing",
      limit: 10,
      offset: 5
    })
    const detailResult = await client.getReadingImportJob(12)

    expect(listResult).toEqual({ jobs: [], total: 0, limit: 10, offset: 5 })
    expect(detailResult).toEqual({ job_id: 12, status: "processing" })

    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        path: "/api/v1/reading/import/jobs?status=processing&limit=10&offset=5",
        method: "GET"
      })
    )
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        path: "/api/v1/reading/import/jobs/12",
        method: "GET"
      })
    )
  })

  it("passes include_highlights and include_notes to reading export requests", async () => {
    mocks.bgRequest.mockResolvedValueOnce({
      ok: true,
      data: new ArrayBuffer(0),
      headers: {
        "content-disposition": 'attachment; filename="reading_filtered.zip"',
        "content-type": "application/zip"
      }
    })

    const client = new TldwApiClient()

    const result = await client.exportReadingList({
      format: "zip",
      status: ["saved"],
      tags: ["research"],
      favorite: true,
      q: "llm",
      domain: "example.com",
      include_highlights: true,
      include_notes: false
    })

    expect(result.filename).toBe("reading_filtered.zip")
    expect(result.blob.type).toBe("application/zip")

    const requestArg = mocks.bgRequest.mock.calls[0][0] as { path: string; method: string }
    expect(requestArg.method).toBe("GET")
    expect(requestArg.path).toContain("/api/v1/reading/export?")
    expect(requestArg.path).toContain("format=zip")
    expect(requestArg.path).toContain("status=saved")
    expect(requestArg.path).toContain("tags=research")
    expect(requestArg.path).toContain("favorite=true")
    expect(requestArg.path).toContain("q=llm")
    expect(requestArg.path).toContain("domain=example.com")
    expect(requestArg.path).toContain("include_highlights=true")
    expect(requestArg.path).toContain("include_notes=false")
  })

  it("calls reading items bulk endpoint and normalizes response shape", async () => {
    mocks.bgRequest.mockResolvedValueOnce({
      total: 2,
      succeeded: 1,
      failed: 1,
      results: [
        { item_id: 101, success: true },
        { item_id: 202, success: false, error: "item_not_found" }
      ]
    })

    const client = new TldwApiClient()
    const result = await client.bulkUpdateReadingItems({
      item_ids: ["101", "202"],
      action: "add_tags",
      tags: ["research"]
    })

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/reading/items/bulk",
        method: "POST",
        body: {
          item_ids: [101, 202],
          action: "add_tags",
          status: undefined,
          favorite: undefined,
          tags: ["research"],
          hard: undefined
        }
      })
    )
    expect(result).toEqual({
      total: 2,
      succeeded: 1,
      failed: 1,
      results: [
        { item_id: "101", success: true, error: null },
        { item_id: "202", success: false, error: "item_not_found" }
      ]
    })
  })

  it("rejects reading items bulk calls without numeric ids", async () => {
    const client = new TldwApiClient()
    await expect(
      client.bulkUpdateReadingItems({
        item_ids: ["abc", "-1"],
        action: "delete"
      })
    ).rejects.toThrow("item_ids_required")
    expect(mocks.bgRequest).not.toHaveBeenCalled()
  })
})
