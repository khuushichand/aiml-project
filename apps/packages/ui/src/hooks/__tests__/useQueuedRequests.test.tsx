import { act, renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { buildQueuedRequest } from "@/utils/chat-request-queue"
import { useQueuedRequests } from "@/hooks/chat/useQueuedRequests"

describe("useQueuedRequests", () => {
  it("promotes a queued request to the front and stops streaming before run-now", async () => {
    const stopStreamingRequest = vi.fn()
    const queue = [
      buildQueuedRequest({ promptText: "one" }),
      buildQueuedRequest({ promptText: "two" })
    ]
    const setQueue = vi.fn()

    const { result } = renderHook(() =>
      useQueuedRequests({
        isConnectionReady: true,
        isStreaming: true,
        queue,
        setQueue,
        sendQueuedRequest: vi.fn(),
        stopStreamingRequest
      })
    )

    await act(async () => {
      await result.current.runNow(queue[1].id)
    })

    expect(stopStreamingRequest).toHaveBeenCalledTimes(1)
    expect(setQueue).toHaveBeenCalledWith([
      expect.objectContaining({
        id: queue[1].id,
        status: "queued",
        blockedReason: null
      }),
      queue[0]
    ])
  })

  it("enqueues normalized queued requests and only flushes when connection is ready", async () => {
    const sendQueuedRequest = vi.fn().mockResolvedValue(undefined)
    let queue = [buildQueuedRequest({ promptText: "existing" })]
    const setQueue = vi.fn((nextQueue) => {
      queue = nextQueue
    })

    const { result, rerender } = renderHook(
      ({
        ready,
        streaming
      }: {
        ready: boolean
        streaming: boolean
      }) =>
        useQueuedRequests({
          isConnectionReady: ready,
          isStreaming: streaming,
          queue,
          setQueue,
          sendQueuedRequest,
          stopStreamingRequest: vi.fn()
        }),
      {
        initialProps: { ready: false, streaming: false }
      }
    )

    await act(async () => {
      result.current.enqueue({ message: "queued later" })
    })

    expect(queue.at(-1)?.promptText).toBe("queued later")

    await act(async () => {
      await result.current.flushNext()
    })

    expect(sendQueuedRequest).not.toHaveBeenCalled()

    rerender({ ready: true, streaming: false })

    await act(async () => {
      await result.current.flushNext()
    })

    expect(sendQueuedRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        promptText: "existing",
        status: "sending"
      })
    )
  })

  it("removes the flushed request after a successful send", async () => {
    const first = buildQueuedRequest({ promptText: "first" })
    const second = buildQueuedRequest({ promptText: "second" })
    let queue = [first, second]
    const setQueue = vi.fn((nextQueue) => {
      queue = nextQueue
    })
    const sendQueuedRequest = vi.fn().mockResolvedValue(undefined)

    const { result } = renderHook(() =>
      useQueuedRequests({
        isConnectionReady: true,
        isStreaming: false,
        queue,
        setQueue,
        sendQueuedRequest,
        stopStreamingRequest: vi.fn()
      })
    )

    await act(async () => {
      await result.current.flushNext()
    })

    expect(sendQueuedRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        id: first.id,
        status: "sending"
      })
    )
    expect(queue.map((item) => item.id)).toEqual([second.id])
  })

  it("blocks the next queued request when dispatch fails", async () => {
    const first = buildQueuedRequest({ promptText: "first" })
    const second = buildQueuedRequest({ promptText: "second" })
    let queue = [first, second]
    const setQueue = vi.fn((nextQueue) => {
      queue = nextQueue
    })
    const sendQueuedRequest = vi
      .fn()
      .mockRejectedValue(new Error("selected model unavailable"))

    const { result } = renderHook(() =>
      useQueuedRequests({
        isConnectionReady: true,
        isStreaming: false,
        queue,
        setQueue,
        sendQueuedRequest,
        stopStreamingRequest: vi.fn()
      })
    )

    await act(async () => {
      await result.current.flushNext()
    })

    expect(queue[0]).toMatchObject({
      id: first.id,
      status: "blocked",
      blockedReason: "selected model unavailable"
    })
    expect(queue[1]?.id).toBe(second.id)
  })
})
