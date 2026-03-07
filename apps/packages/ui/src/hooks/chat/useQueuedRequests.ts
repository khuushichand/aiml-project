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
      const reordered = moveQueuedRequestToFront(queue, requestId)
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
    if (!next || isStreaming || !isConnectionReady) return null
    await sendQueuedRequest(next)
    return next
  }, [isConnectionReady, isStreaming, queue, sendQueuedRequest])

  return {
    enqueue,
    flushNext,
    markBlocked,
    remove,
    runNow
  }
}
