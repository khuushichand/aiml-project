import React from "react"

import {
  blockQueuedRequest,
  buildQueuedRequest,
  moveQueuedRequestToFront,
  type QueuedRequest,
  type QueuedRequestInput
} from "@/utils/chat-request-queue"

type UseQueuedRequestsOptions = {
  isConnectionReady: boolean
  isStreaming: boolean
  queue: QueuedRequest[]
  setQueue: (queue: QueuedRequest[]) => void
  sendQueuedRequest: (item: QueuedRequest) => Promise<void>
  stopStreamingRequest: () => void
}

export function useQueuedRequests({
  isConnectionReady,
  isStreaming,
  queue,
  setQueue,
  sendQueuedRequest,
  stopStreamingRequest
}: UseQueuedRequestsOptions) {
  const enqueue = React.useCallback(
    (partial: QueuedRequestInput) => {
      const nextItem = buildQueuedRequest(partial)
      setQueue([...queue, nextItem])
      return nextItem
    },
    [queue, setQueue]
  )

  const remove = React.useCallback(
    (requestId: string) => {
      setQueue(queue.filter((item) => item.id !== requestId))
    },
    [queue, setQueue]
  )

  const clear = React.useCallback(() => {
    setQueue([])
  }, [setQueue])

  const update = React.useCallback(
    (requestId: string, promptText: string) => {
      setQueue(
        queue.map((item) =>
          item.id === requestId
            ? {
                ...item,
                promptText,
                message: promptText,
                updatedAt: Date.now()
              }
            : item
        )
      )
    },
    [queue, setQueue]
  )

  const move = React.useCallback(
    (requestId: string, direction: "up" | "down") => {
      const currentIndex = queue.findIndex((item) => item.id === requestId)
      if (currentIndex === -1) return
      const targetIndex =
        direction === "up" ? currentIndex - 1 : currentIndex + 1
      if (targetIndex < 0 || targetIndex >= queue.length) return
      const reordered = [...queue]
      const [target] = reordered.splice(currentIndex, 1)
      reordered.splice(targetIndex, 0, target)
      setQueue(reordered)
    },
    [queue, setQueue]
  )

  const markBlocked = React.useCallback(
    (requestId: string, blockedReason: string) => {
      setQueue(
        queue.map((item) =>
          item.id === requestId ? blockQueuedRequest(item, blockedReason) : item
        )
      )
    },
    [queue, setQueue]
  )

  const runNow = React.useCallback(
    async (requestId: string) => {
      const reordered = moveQueuedRequestToFront(queue, requestId).map(
        (item, index) =>
          index === 0
            ? {
                ...item,
                status: "queued",
                blockedReason: null,
                updatedAt: Date.now()
              }
            : item
      )
      setQueue(reordered)
      if (isStreaming) {
        stopStreamingRequest()
      }
      return reordered[0] ?? null
    },
    [isStreaming, queue, setQueue, stopStreamingRequest]
  )

  const flushNext = React.useCallback(async () => {
    const next = queue[0]
    if (
      !next ||
      isStreaming ||
      !isConnectionReady ||
      next.status === "blocked" ||
      next.status === "sending"
    ) {
      return null
    }

    const sendingItem: QueuedRequest = {
      ...next,
      status: "sending",
      blockedReason: null,
      updatedAt: Date.now()
    }

    setQueue([sendingItem, ...queue.slice(1)])

    try {
      await sendQueuedRequest(sendingItem)
      setQueue(queue.slice(1))
      return sendingItem
    } catch (error) {
      const blockedReason =
        error instanceof Error ? error.message : "dispatch_failed"
      setQueue([blockQueuedRequest(next, blockedReason), ...queue.slice(1)])
      return null
    }
  }, [isConnectionReady, isStreaming, queue, sendQueuedRequest, setQueue])

  return {
    clear,
    enqueue,
    flushNext,
    markBlocked,
    move,
    remove,
    update,
    runNow
  }
}
