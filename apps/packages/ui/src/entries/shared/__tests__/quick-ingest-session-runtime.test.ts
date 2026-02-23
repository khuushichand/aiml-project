import { describe, expect, it, vi } from "vitest"

import {
  createQuickIngestSessionRuntime
} from "@/entries/shared/quick-ingest-session-runtime"

describe("quick ingest session runtime", () => {
  it("returns immediate ack with session id and runs in background", async () => {
    const run = vi.fn(async () => ({ results: [{ id: "1", status: "ok" }] }))
    const emit = vi.fn()
    const runtime = createQuickIngestSessionRuntime({ run, emit })

    const ack = runtime.start({ entries: [], files: [] })

    expect(ack.ok).toBe(true)
    expect(typeof ack.sessionId).toBe("string")

    await vi.waitFor(() => {
      expect(run).toHaveBeenCalledTimes(1)
    })
  })

  it("emits completed event keyed by session id on success", async () => {
    const run = vi.fn(async () => ({ results: [{ id: "1", status: "ok" }] }))
    const emit = vi.fn()
    const runtime = createQuickIngestSessionRuntime({ run, emit })

    const ack = runtime.start({ entries: [], files: [] })

    await vi.waitFor(() => {
      expect(emit).toHaveBeenCalledWith(
        "tldw:quick-ingest/completed",
        expect.objectContaining({
          sessionId: ack.sessionId,
          results: expect.any(Array)
        })
      )
    })
  })

  it("marks cancelled sessions immediately and suppresses completed emission", async () => {
    let release: (() => void) | null = null
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    const run = vi.fn(async ({ registerAbortController }: any) => {
      registerAbortController(new AbortController())
      await gate
      return { results: [] }
    })
    const emit = vi.fn()
    const runtime = createQuickIngestSessionRuntime({ run, emit })

    const ack = runtime.start({ entries: [], files: [] })
    const cancelResp = runtime.cancel(ack.sessionId, "user_cancelled")

    expect(cancelResp).toEqual({ ok: true })
    expect(
      emit.mock.calls.some(
        ([type, payload]) =>
          type === "tldw:quick-ingest/cancelled" &&
          payload?.sessionId === ack.sessionId
      )
    ).toBe(true)

    release?.()
    await Promise.resolve()
    await Promise.resolve()

    expect(
      emit.mock.calls.some(
        ([type, payload]) =>
          type === "tldw:quick-ingest/completed" &&
          payload?.sessionId === ack.sessionId
      )
    ).toBe(false)
  })
})
