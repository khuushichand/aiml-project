import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  runtimeId: undefined as string | undefined,
  sendMessage: vi.fn(),
  bgRequest: vi.fn(),
  bgUpload: vi.fn()
}))

vi.mock("wxt/browser", () => ({
  browser: {
    runtime: {
      get id() {
        return mocks.runtimeId
      },
      sendMessage: (...args: unknown[]) => mocks.sendMessage(...args)
    }
  }
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args),
  bgUpload: (...args: unknown[]) => mocks.bgUpload(...args)
}))

import {
  __resetQuickIngestRuntimeHealthForTests,
  cancelQuickIngestSession,
  startQuickIngestSession,
  submitQuickIngestBatch
} from "@/services/tldw/quick-ingest-batch"

describe("submitQuickIngestBatch", () => {
  beforeEach(() => {
    __resetQuickIngestRuntimeHealthForTests()
    vi.useRealTimers()
    mocks.runtimeId = undefined
    mocks.sendMessage.mockReset()
    mocks.bgRequest.mockReset()
    mocks.bgUpload.mockReset()
  })

  it("uses direct upload path when extension runtime id is unavailable", async () => {
    mocks.bgUpload.mockResolvedValue({
      batch_id: "batch-1",
      jobs: [{ id: 101 }]
    })
    mocks.bgRequest.mockResolvedValue({
      ok: true,
      data: {
        status: "completed",
        result: { media_id: "m1" }
      }
    })

    const result = await submitQuickIngestBatch({
      entries: [
        {
          id: "entry-1",
          url: "https://example.com/article",
          type: "document"
        }
      ],
      files: [],
      storeRemote: true,
      processOnly: false,
      common: {
        perform_analysis: true,
        perform_chunking: false,
        overwrite_existing: false
      },
      advancedValues: {}
    })

    expect(mocks.sendMessage).not.toHaveBeenCalled()
    expect(mocks.bgUpload).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/media/ingest/jobs",
        method: "POST",
        fields: expect.objectContaining({
          media_type: "document",
          urls: ["https://example.com/article"]
        })
      })
    )
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/media/ingest/jobs/101",
        method: "GET"
      })
    )
    expect(result.ok).toBe(true)
    expect(result.results?.[0]).toMatchObject({
      id: "entry-1",
      status: "ok"
    })
  })

  it("cancels direct-session tracked batches through backend cancel endpoint", async () => {
    mocks.bgUpload.mockResolvedValue({
      batch_id: "batch-direct-cancel",
      jobs: [{ id: 777 }]
    })

    let statusPollCount = 0
    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      const path = String(request?.path || "")
      if (path.includes("/api/v1/media/ingest/jobs/cancel?batch_id=batch-direct-cancel")) {
        return { ok: true, data: { success: true } }
      }
      if (path === "/api/v1/media/ingest/jobs/777") {
        statusPollCount += 1
        return { ok: true, data: { status: statusPollCount > 1 ? "cancelled" : "processing" } }
      }
      return { ok: false, error: "unexpected path" }
    })

    const runPromise = submitQuickIngestBatch({
      entries: [
        {
          id: "entry-cancel-1",
          url: "https://example.com/cancel-me",
          type: "document"
        }
      ],
      files: [],
      storeRemote: true,
      processOnly: false,
      __quickIngestSessionId: "direct-session-1",
      common: {
        perform_analysis: true,
        perform_chunking: false,
        overwrite_existing: false
      },
      advancedValues: {}
    })

    await vi.waitFor(() => {
      expect(mocks.bgRequest).toHaveBeenCalledWith(
        expect.objectContaining({
          path: "/api/v1/media/ingest/jobs/777",
          method: "GET"
        })
      )
    })

    const cancelResponse = await cancelQuickIngestSession({
      sessionId: "direct-session-1",
      reason: "user_cancelled"
    })
    const runResult = await runPromise

    expect(cancelResponse).toEqual({ ok: true })
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: expect.stringContaining(
          "/api/v1/media/ingest/jobs/cancel?batch_id=batch-direct-cancel"
        ),
        method: "POST"
      })
    )
    expect(runResult.results?.[0]).toMatchObject({
      id: "entry-cancel-1",
      status: "error"
    })
  })

  it("uses extension message transport when extension runtime is available", async () => {
    mocks.runtimeId = "ext-1"
    mocks.sendMessage
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({
      ok: true,
      results: [{ id: "entry-1", status: "ok", type: "document" }]
      })

    const result = await submitQuickIngestBatch({
      entries: [
        {
          id: "entry-1",
          url: "https://example.com/article",
          type: "document"
        }
      ],
      files: [],
      storeRemote: true,
      processOnly: false,
      common: {
        perform_analysis: true,
        perform_chunking: false,
        overwrite_existing: false
      },
      advancedValues: {}
    })

    expect(mocks.sendMessage).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        type: "tldw:ping"
      })
    )
    expect(mocks.sendMessage).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        type: "tldw:quick-ingest-batch",
        payload: expect.objectContaining({
          entries: expect.any(Array)
        })
      })
    )
    expect(mocks.bgUpload).not.toHaveBeenCalled()
    expect(mocks.bgRequest).not.toHaveBeenCalled()
    expect(result.ok).toBe(true)
  })

  it("falls back to direct mode when runtime ping preflight times out", async () => {
    vi.useFakeTimers()
    mocks.runtimeId = "ext-1"
    mocks.sendMessage.mockImplementation(() => new Promise(() => undefined))
    mocks.bgUpload.mockResolvedValue({
      batch_id: "batch-direct-fallback",
      jobs: [{ id: 808 }]
    })
    mocks.bgRequest.mockResolvedValue({
      ok: true,
      data: {
        status: "completed",
        result: { media_id: "m-fallback" }
      }
    })

    const resultPromise = submitQuickIngestBatch({
      entries: [
        {
          id: "entry-fallback",
          url: "https://example.com/runtime-fallback",
          type: "document"
        }
      ],
      files: [],
      storeRemote: true,
      processOnly: false,
      common: {
        perform_analysis: true,
        perform_chunking: false,
        overwrite_existing: false
      },
      advancedValues: {}
    })

    await vi.advanceTimersByTimeAsync(401)
    const result = await resultPromise

    expect(mocks.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "tldw:ping"
      })
    )
    expect(mocks.bgUpload).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/media/ingest/jobs",
        method: "POST"
      })
    )
    expect(result.results?.[0]).toMatchObject({
      id: "entry-fallback",
      status: "ok"
    })
  })

  it("routes html process-only entries through process-web-scraping", async () => {
    mocks.bgRequest.mockResolvedValue({ content: "processed" })

    const result = await submitQuickIngestBatch({
      entries: [
        {
          id: "entry-html",
          url: "https://example.com/page",
          type: "html"
        }
      ],
      files: [],
      storeRemote: false,
      processOnly: true,
      common: {
        perform_analysis: true,
        perform_chunking: false,
        overwrite_existing: false
      },
      advancedValues: {
        custom_headers: '{"x-test":"1"}'
      }
    })

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/media/process-web-scraping",
        method: "POST",
        body: expect.objectContaining({
          url_input: "https://example.com/page",
          scrape_method: "Individual URLs"
        })
      })
    )
    expect(result.results?.[0]).toMatchObject({
      id: "entry-html",
      status: "ok",
      type: "html"
    })
  })

  it("routes local files through direct process endpoints in web runtime", async () => {
    mocks.bgUpload.mockResolvedValue({ result: "ok" })

    const result = await submitQuickIngestBatch({
      entries: [],
      files: [
        {
          id: "file-1",
          name: "notes.txt",
          type: "text/plain",
          data: [1, 2, 3]
        }
      ],
      storeRemote: false,
      processOnly: true,
      common: {
        perform_analysis: true,
        perform_chunking: true,
        overwrite_existing: false
      },
      advancedValues: {}
    })

    expect(mocks.bgUpload).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/media/process-documents",
        method: "POST",
        file: expect.objectContaining({
          name: "notes.txt"
        })
      })
    )
    expect(result.results?.[0]).toMatchObject({
      id: "file-1",
      status: "ok"
    })
  })

  it("starts a quick ingest session via extension transport and returns session id ack", async () => {
    mocks.runtimeId = "ext-1"
    mocks.sendMessage
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({
      ok: true,
      sessionId: "qi-session-123"
      })

    const ack = await startQuickIngestSession({
      entries: [
        {
          id: "entry-1",
          url: "https://example.com/article",
          type: "document"
        }
      ],
      files: [],
      storeRemote: true,
      processOnly: false,
      common: {
        perform_analysis: true,
        perform_chunking: false,
        overwrite_existing: false
      },
      advancedValues: {}
    })

    expect(mocks.sendMessage).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        type: "tldw:ping"
      })
    )
    expect(mocks.sendMessage).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        type: "tldw:quick-ingest/start",
        payload: expect.objectContaining({
          entries: expect.any(Array)
        })
      })
    )
    expect(ack).toEqual({
      ok: true,
      sessionId: "qi-session-123"
    })
  })

  it("returns a direct session ack when runtime ping preflight times out", async () => {
    vi.useFakeTimers()
    mocks.runtimeId = "ext-1"
    mocks.sendMessage.mockImplementation(() => new Promise(() => undefined))

    const ackPromise = startQuickIngestSession({
      entries: [
        {
          id: "entry-1",
          url: "https://example.com/article",
          type: "document"
        }
      ],
      files: [],
      storeRemote: true,
      processOnly: false,
      common: {
        perform_analysis: true,
        perform_chunking: false,
        overwrite_existing: false
      },
      advancedValues: {}
    })

    await vi.advanceTimersByTimeAsync(401)
    const ack = await ackPromise

    expect(mocks.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "tldw:ping"
      })
    )
    expect(ack.ok).toBe(true)
    expect(ack.sessionId).toMatch(/^qi-direct-/)
  })

  it("sends explicit cancel message with session id", async () => {
    mocks.runtimeId = "ext-1"
    mocks.sendMessage.mockResolvedValueOnce({ ok: true }).mockResolvedValueOnce({
      ok: true
    })

    const response = await cancelQuickIngestSession({
      sessionId: "qi-session-123",
      reason: "user_cancelled"
    })

    expect(mocks.sendMessage).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        type: "tldw:ping"
      })
    )
    expect(mocks.sendMessage).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        type: "tldw:quick-ingest/cancel",
        payload: {
          sessionId: "qi-session-123",
          reason: "user_cancelled"
        }
      })
    )
    expect(response).toEqual({ ok: true })
  })
})
