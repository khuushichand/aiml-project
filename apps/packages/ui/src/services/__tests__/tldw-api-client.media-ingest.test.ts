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

describe("TldwApiClient media ingest contract", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("uses multipart /media/add fields inferred from URL", async () => {
    mocks.bgUpload.mockResolvedValue({ results: [] })

    const client = new TldwApiClient()
    await client.addMedia("https://example.com/article")

    expect(mocks.bgUpload).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/media/add",
        method: "POST",
        fields: expect.objectContaining({
          media_type: "document",
          urls: ["https://example.com/article"]
        })
      })
    )
  })

  it("infers video media_type for youtube URLs", async () => {
    mocks.bgUpload.mockResolvedValue({ results: [] })

    const client = new TldwApiClient()
    await client.addMedia("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    expect(mocks.bgUpload).toHaveBeenCalledWith(
      expect.objectContaining({
        fields: expect.objectContaining({
          media_type: "video",
          urls: ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]
        })
      })
    )
  })

  it("keeps explicit media_type overrides", async () => {
    mocks.bgUpload.mockResolvedValue({ results: [] })

    const client = new TldwApiClient()
    await client.addMedia("https://example.com/file.mp4", {
      media_type: "audio"
    })

    expect(mocks.bgUpload).toHaveBeenCalledWith(
      expect.objectContaining({
        fields: expect.objectContaining({
          media_type: "audio",
          urls: ["https://example.com/file.mp4"]
        })
      })
    )
  })

  it("forwards timeout and ingest options with urls list", async () => {
    mocks.bgUpload.mockResolvedValue({ results: [] })

    const client = new TldwApiClient()
    await client.addMedia("https://example.com/video.mp4", {
      timeoutMs: 45000,
      perform_analysis: false,
      perform_chunking: true,
      overwrite_existing: false
    })

    expect(mocks.bgUpload).toHaveBeenCalledWith(
      expect.objectContaining({
        timeoutMs: 45000,
        fields: expect.objectContaining({
          media_type: "video",
          urls: ["https://example.com/video.mp4"],
          perform_analysis: false,
          perform_chunking: true,
          overwrite_existing: false
        })
      })
    )
  })
})

