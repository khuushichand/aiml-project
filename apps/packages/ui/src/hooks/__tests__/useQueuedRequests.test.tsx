import { act, renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { useQueuedRequests } from "@/hooks/chat/useQueuedRequests"
import { buildQueuedRequest, type QueuedRequest } from "@/utils/chat-request-queue"

const createQueueSetter = (queueRef: { current: QueuedRequest[] }) =>
  vi.fn((nextQueueOrUpdater: QueuedRequest[] | ((prev: QueuedRequest[]) => QueuedRequest[])) => {
    queueRef.current =
      typeof nextQueueOrUpdater === "function"
        ? nextQueueOrUpdater(queueRef.current)
        : nextQueueOrUpdater
  })

describe("useQueuedRequests", () => {
  it("promotes a queued request to the front and stops streaming before run-now", async () => {
    const stopStreamingRequest = vi.fn()
    const first = buildQueuedRequest({ promptText: "one" })
    const second = buildQueuedRequest({ promptText: "two" })
    const queueRef = {
      current: [first, second]
    }
    const setQueue = createQueueSetter(queueRef)

    const { result } = renderHook(() =>
      useQueuedRequests({
        isConnectionReady: true,
        isStreaming: true,
        queue: queueRef.current,
        setQueue,
        sendQueuedRequest: vi.fn(),
        stopStreamingRequest
      })
    )

    await act(async () => {
      await result.current.runNow(second.id)
    })

    expect(stopStreamingRequest).toHaveBeenCalledTimes(1)
    expect(queueRef.current).toEqual([
      expect.objectContaining({
        id: second.id,
        status: "queued",
        blockedReason: null
      }),
      expect.objectContaining({
        id: first.id
      })
    ])
  })

  it("enqueues normalized queued requests and only flushes when connection is ready", async () => {
    const sendQueuedRequest = vi.fn().mockResolvedValue(undefined)
    const queueRef = {
      current: [buildQueuedRequest({ promptText: "existing" })]
    }
    const setQueue = createQueueSetter(queueRef)

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
          queue: queueRef.current,
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

    expect(queueRef.current.at(-1)?.promptText).toBe("queued later")

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
    const queueRef = {
      current: [first, second]
    }
    const setQueue = createQueueSetter(queueRef)
    const sendQueuedRequest = vi.fn().mockResolvedValue(undefined)

    const { result } = renderHook(() =>
      useQueuedRequests({
        isConnectionReady: true,
        isStreaming: false,
        queue: queueRef.current,
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
    expect(queueRef.current.map((item) => item.id)).toEqual([second.id])
  })

  it("does not restore queued items after clear-all during an in-flight send", async () => {
    const first = buildQueuedRequest({ promptText: "first" })
    const second = buildQueuedRequest({ promptText: "second" })
    const queueRef = {
      current: [first, second]
    }
    const setQueue = createQueueSetter(queueRef)
    let resolveSend: (() => void) | null = null
    const sendQueuedRequest = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveSend = resolve
        })
    )

    const { result } = renderHook(() =>
      useQueuedRequests({
        isConnectionReady: true,
        isStreaming: false,
        queue: queueRef.current,
        setQueue,
        sendQueuedRequest,
        stopStreamingRequest: vi.fn()
      })
    )

    let flushPromise: Promise<QueuedRequest | null> | null = null
    await act(async () => {
      flushPromise = result.current.flushNext()
      await Promise.resolve()
    })

    expect(queueRef.current[0]).toMatchObject({
      id: first.id,
      status: "sending"
    })

    await act(async () => {
      result.current.clear()
    })

    expect(queueRef.current).toEqual([])

    await act(async () => {
      resolveSend?.()
      await flushPromise
    })

    expect(queueRef.current).toEqual([])
  })

  it("blocks the next queued request when dispatch fails", async () => {
    const first = buildQueuedRequest({ promptText: "first" })
    const second = buildQueuedRequest({ promptText: "second" })
    const queueRef = {
      current: [first, second]
    }
    const setQueue = createQueueSetter(queueRef)
    const sendQueuedRequest = vi
      .fn()
      .mockRejectedValue(new Error("selected model unavailable"))

    const { result } = renderHook(() =>
      useQueuedRequests({
        isConnectionReady: true,
        isStreaming: false,
        queue: queueRef.current,
        setQueue,
        sendQueuedRequest,
        stopStreamingRequest: vi.fn()
      })
    )

    await act(async () => {
      await result.current.flushNext()
    })

    expect(queueRef.current[0]).toMatchObject({
      id: first.id,
      status: "blocked",
      blockedReason: "selected model unavailable"
    })
    expect(queueRef.current[1]?.id).toBe(second.id)
  })
})
