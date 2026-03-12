import { useCallback, useEffect, useRef } from "react"
import type { ItemProgress, ItemProgressStatus } from "./types"
import { useIngestWizard } from "./IngestWizardContext"

// ---------------------------------------------------------------------------
// Types for SSE events from the backend
// ---------------------------------------------------------------------------

type SSESnapshotEvent = {
  domain: string
  batch_id: string | null
  jobs: SSEJobSnapshot[]
}

type SSEJobSnapshot = {
  id: number
  status: string
  progress_percent?: number
  progress_message?: string
  error?: string | null
}

type SSEJobEvent = {
  event_id: number
  job_id: number
  event_type: string
  attrs: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map backend job status strings to wizard ItemProgressStatus. */
const mapBackendStatus = (status: string): ItemProgressStatus => {
  switch (status.toLowerCase()) {
    case "pending":
    case "queued":
      return "queued"
    case "uploading":
      return "uploading"
    case "processing":
    case "running":
      return "processing"
    case "analyzing":
      return "analyzing"
    case "storing":
      return "storing"
    case "completed":
    case "complete":
      return "complete"
    case "failed":
    case "error":
      return "failed"
    case "cancelled":
    case "canceled":
      return "cancelled"
    default:
      return "processing"
  }
}

/** Derive a human-readable stage label from backend progress_message or status. */
const deriveStageLabel = (
  status: string,
  progressMessage?: string
): string => {
  if (progressMessage) return progressMessage
  switch (status.toLowerCase()) {
    case "pending":
    case "queued":
      return "Queued"
    case "uploading":
      return "Uploading"
    case "processing":
    case "running":
      return "Processing"
    case "analyzing":
      return "Analyzing"
    case "storing":
      return "Storing"
    case "completed":
    case "complete":
      return "Complete"
    case "failed":
    case "error":
      return "Failed"
    case "cancelled":
    case "canceled":
      return "Cancelled"
    default:
      return status
  }
}

// ---------------------------------------------------------------------------
// Options
// ---------------------------------------------------------------------------

type UseIngestSSEOptions = {
  /** Batch ID to scope SSE events to (from job submission response). */
  batchId?: string
  /** Map from backend job_id to wizard queue item id. */
  jobIdToQueueId: Map<number, string>
  /** Whether to connect to SSE (only when processing step is active). */
  enabled: boolean
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Connect to the backend SSE stream for ingest job events and update
 * wizard processing state in real-time.
 *
 * Uses `bgRequest` to resolve the server base URL, then opens a native
 * `EventSource` connection. Automatically reconnects on error with
 * exponential backoff (max 10s).
 */
export function useIngestSSE({
  batchId,
  jobIdToQueueId,
  enabled,
}: UseIngestSSEOptions): void {
  const { updateItemProgress, updateProcessingState } = useIngestWizard()
  const eventSourceRef = useRef<EventSource | null>(null)
  const afterIdRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectDelayRef = useRef(1000)
  const enabledRef = useRef(enabled)
  enabledRef.current = enabled

  const jobIdToQueueIdRef = useRef(jobIdToQueueId)
  jobIdToQueueIdRef.current = jobIdToQueueId

  const handleSnapshot = useCallback(
    (snapshot: SSESnapshotEvent) => {
      const map = jobIdToQueueIdRef.current
      let allTerminal = true
      let completedCount = 0
      let totalCount = 0

      for (const job of snapshot.jobs) {
        const queueId = map.get(job.id)
        if (!queueId) continue

        totalCount++
        const status = mapBackendStatus(job.status)
        const isTerminal =
          status === "complete" || status === "failed" || status === "cancelled"
        if (!isTerminal) allTerminal = false
        if (status === "complete") completedCount++

        const progress: ItemProgress = {
          id: queueId,
          status,
          progressPercent: job.progress_percent ?? (isTerminal ? 100 : 0),
          currentStage: deriveStageLabel(job.status, job.progress_message),
          estimatedRemaining: 0,
          error: job.error ?? undefined,
        }
        updateItemProgress(progress)
      }

      if (allTerminal && totalCount > 0) {
        updateProcessingState({
          status: completedCount === totalCount ? "complete" : "error",
        })
      }
    },
    [updateItemProgress, updateProcessingState]
  )

  const handleJobEvent = useCallback(
    (event: SSEJobEvent) => {
      const map = jobIdToQueueIdRef.current
      const queueId = map.get(event.job_id)
      if (!queueId) return

      afterIdRef.current = Math.max(afterIdRef.current, event.event_id)

      const attrs = event.attrs || {}
      const status = mapBackendStatus(
        (attrs.status as string) || event.event_type || "processing"
      )
      const progressPercent =
        typeof attrs.progress_percent === "number"
          ? attrs.progress_percent
          : undefined

      const progress: ItemProgress = {
        id: queueId,
        status,
        progressPercent: progressPercent ?? (status === "complete" ? 100 : 0),
        currentStage: deriveStageLabel(
          (attrs.status as string) || event.event_type,
          attrs.progress_message as string | undefined
        ),
        estimatedRemaining: 0,
        error: (attrs.error as string) ?? undefined,
      }
      updateItemProgress(progress)

      // Check if this was a terminal event and update overall state
      if (
        status === "complete" ||
        status === "failed" ||
        status === "cancelled"
      ) {
        // We rely on the snapshot to determine overall completion
        // Individual terminal events just update the item
      }
    },
    [updateItemProgress]
  )

  const connect = useCallback(() => {
    if (!enabledRef.current) return

    // Build SSE URL
    const params = new URLSearchParams()
    if (batchId) params.set("batch_id", batchId)
    if (afterIdRef.current > 0)
      params.set("after_id", String(afterIdRef.current))

    const queryString = params.toString()
    const path = `/api/v1/media/ingest/jobs/events/stream${
      queryString ? `?${queryString}` : ""
    }`

    // Resolve full URL via bgRequest's base URL resolution
    let baseUrl = ""
    try {
      // Try to get base URL from the page context
      const meta = document.querySelector('meta[name="tldw-api-base"]')
      if (meta) {
        baseUrl = meta.getAttribute("content") || ""
      }
      if (!baseUrl) {
        // Fallback: use current origin
        baseUrl = window.location.origin
      }
    } catch {
      baseUrl = window.location.origin
    }

    const url = `${baseUrl}${path}`

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    const es = new EventSource(url)
    eventSourceRef.current = es

    es.addEventListener("snapshot", (e) => {
      try {
        const data = JSON.parse(e.data) as SSESnapshotEvent
        handleSnapshot(data)
        // Reset reconnect delay on successful connection
        reconnectDelayRef.current = 1000
      } catch {
        // Ignore parse errors
      }
    })

    es.addEventListener("job", (e) => {
      try {
        const data = JSON.parse(e.data) as SSEJobEvent
        handleJobEvent(data)
      } catch {
        // Ignore parse errors
      }
    })

    es.onerror = () => {
      es.close()
      eventSourceRef.current = null

      if (!enabledRef.current) return

      // Exponential backoff reconnection
      const delay = reconnectDelayRef.current
      reconnectDelayRef.current = Math.min(delay * 2, 10000)

      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null
        if (enabledRef.current) {
          connect()
        }
      }, delay)
    }
  }, [batchId, handleSnapshot, handleJobEvent])

  // Connect/disconnect based on enabled state
  useEffect(() => {
    if (enabled) {
      connect()
    }

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
    }
  }, [enabled, connect])
}

export default useIngestSSE
