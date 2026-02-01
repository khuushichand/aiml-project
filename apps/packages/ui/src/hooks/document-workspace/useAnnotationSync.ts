import { useEffect, useRef, useCallback, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw"
import { useConnectionStore } from "@/store/connection"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import type { Annotation, AnnotationColor } from "@/components/DocumentWorkspace/types"

// Retry configuration
const MAX_RETRY_ATTEMPTS = 3
const INITIAL_RETRY_DELAY_MS = 1000 // 1 second
const MAX_RETRY_DELAY_MS = 8000 // 8 seconds

/**
 * Sync annotations using navigator.sendBeacon for guaranteed delivery on page unload.
 * sendBeacon is specifically designed for this use case - it queues the request
 * and guarantees delivery even if the page is closed immediately.
 *
 * @returns true if sendBeacon was used, false if not available or failed
 */
function syncAnnotationsWithBeacon(
  serverUrl: string | null,
  mediaId: number,
  pendingAnnotations: Annotation[]
): boolean {
  if (!serverUrl || pendingAnnotations.length === 0) {
    return false
  }

  // sendBeacon is not available in all environments (e.g., some older browsers, Node.js)
  if (typeof navigator === "undefined" || !navigator.sendBeacon) {
    return false
  }

  try {
    const url = `${serverUrl}/api/v1/media/${mediaId}/annotations/sync`
    const payload = JSON.stringify({
      annotations: pendingAnnotations.map((ann) => ({
        location: String(ann.location),
        text: ann.text,
        color: ann.color,
        note: ann.note,
        annotation_type: ann.annotationType ?? "highlight"
      })),
      client_ids: pendingAnnotations.map((ann) => ann.id)
    })

    // sendBeacon returns true if the browser successfully queued the request
    const blob = new Blob([payload], { type: "application/json" })
    return navigator.sendBeacon(url, blob)
  } catch (error) {
    console.error("sendBeacon failed:", error)
    return false
  }
}

/**
 * Hook to automatically sync pending annotations to the backend.
 *
 * This hook watches the store's pendingAnnotations and syncs them
 * to the backend when connection is available. Includes automatic
 * retry with exponential backoff on failure.
 *
 * @param mediaId - The active document's media ID
 * @param debounceMs - Debounce time in milliseconds (default: 2000)
 */
export function useAnnotationSync(
  mediaId: number | null,
  debounceMs: number = 2000
) {
  const queryClient = useQueryClient()
  const isConnected = useConnectionStore((s) => s.state.isConnected)
  const mode = useConnectionStore((s) => s.state.mode)
  const isServerAvailable = isConnected && mode !== "demo"

  const pendingAnnotations = useDocumentWorkspaceStore(
    (s) => s.pendingAnnotations
  )
  const annotationSyncStatus = useDocumentWorkspaceStore(
    (s) => s.annotationSyncStatus
  )
  const setAnnotationSyncStatus = useDocumentWorkspaceStore(
    (s) => s.setAnnotationSyncStatus
  )

  const syncTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  // Clear retry timeout on cleanup
  useEffect(() => {
    return () => {
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current)
      }
    }
  }, [])

  // Reset retry count when sync succeeds or annotations change
  useEffect(() => {
    if (annotationSyncStatus === "synced") {
      setRetryCount(0)
    }
  }, [annotationSyncStatus])

  // Mutation for batch sync
  const syncMutation = useMutation({
    mutationFn: async ({
      mediaId,
      annotations,
      clientIds
    }: {
      mediaId: number
      annotations: Array<{
        location: string
        text: string
        color?: AnnotationColor
        note?: string
        annotation_type?: "highlight" | "page_note"
      }>
      clientIds: string[]
    }) => {
      return await tldwClient.syncAnnotations(
        mediaId,
        annotations,
        clientIds
      )
    },
    onSuccess: (_data, { mediaId }) => {
      queryClient.invalidateQueries({ queryKey: ["document-annotations", mediaId] })
      setAnnotationSyncStatus("synced")
      setRetryCount(0)
    },
    onError: () => {
      // Schedule retry with exponential backoff if under max attempts
      if (retryCount < MAX_RETRY_ATTEMPTS) {
        const delay = Math.min(
          INITIAL_RETRY_DELAY_MS * Math.pow(2, retryCount),
          MAX_RETRY_DELAY_MS
        )
        setRetryCount((prev) => prev + 1)
        setAnnotationSyncStatus("pending") // Keep as pending to trigger retry

        retryTimeoutRef.current = setTimeout(() => {
          // The debounced effect will pick this up
        }, delay)

        console.warn(
          `Annotation sync failed, will retry in ${delay}ms (attempt ${retryCount + 1}/${MAX_RETRY_ATTEMPTS})`
        )
      } else {
        // Max retries exceeded, set error status
        setAnnotationSyncStatus("error")
        console.error(
          `Annotation sync failed after ${MAX_RETRY_ATTEMPTS} attempts`
        )
      }
    }
  })

  // Sync function
  const syncPendingAnnotations = useCallback(async () => {
    if (
      !mediaId ||
      !isServerAvailable ||
      pendingAnnotations.length === 0 ||
      syncMutation.isPending
    ) {
      return
    }

    const annotationsToSync = pendingAnnotations.map((ann) => ({
      location: String(ann.location),
      text: ann.text,
      color: ann.color,
      note: ann.note,
      annotation_type: ann.annotationType ?? "highlight"
    }))

    const clientIds = pendingAnnotations.map((ann) => ann.id)

    try {
      await syncMutation.mutateAsync({
        mediaId,
        annotations: annotationsToSync,
        clientIds
      })
    } catch (error) {
      console.error("Failed to sync annotations:", error)
    }
  }, [mediaId, isServerAvailable, pendingAnnotations, syncMutation])

  // Debounced sync effect
  useEffect(() => {
    if (annotationSyncStatus !== "pending" || !isServerAvailable) {
      return
    }

    // Clear existing timeout
    if (syncTimeoutRef.current) {
      clearTimeout(syncTimeoutRef.current)
    }

    // Set new debounced sync
    syncTimeoutRef.current = setTimeout(() => {
      syncPendingAnnotations()
    }, debounceMs)

    return () => {
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current)
      }
    }
  }, [annotationSyncStatus, isServerAvailable, debounceMs, syncPendingAnnotations])

  // Force sync (useful for immediate save)
  const forceSync = useCallback(() => {
    if (syncTimeoutRef.current) {
      clearTimeout(syncTimeoutRef.current)
    }
    syncPendingAnnotations()
  }, [syncPendingAnnotations])

  // Manual retry function for user-initiated retries
  const retrySync = useCallback(() => {
    if (annotationSyncStatus === "error") {
      setRetryCount(0)
      setAnnotationSyncStatus("pending")
    }
  }, [annotationSyncStatus, setAnnotationSyncStatus])

  return {
    isSyncing: syncMutation.isPending,
    syncStatus: annotationSyncStatus,
    forceSync,
    retrySync,
    retryCount,
    maxRetries: MAX_RETRY_ATTEMPTS,
    error: syncMutation.error
  }
}

/**
 * Hook that syncs annotations when the document is closed or changed.
 * Call this from the document workspace page component.
 *
 * Uses navigator.sendBeacon for page unload events to guarantee delivery,
 * since regular async requests may not complete before the page closes.
 */
export function useAnnotationSyncOnClose(mediaId: number | null) {
  const { forceSync } = useAnnotationSync(mediaId, 0)
  const annotationSyncStatus = useDocumentWorkspaceStore(
    (s) => s.annotationSyncStatus
  )
  const pendingAnnotations = useDocumentWorkspaceStore(
    (s) => s.pendingAnnotations
  )
  const serverUrl = useConnectionStore((s) => s.state.serverUrl)
  const previousMediaIdRef = useRef<number | null>(mediaId)

  // Sync when document changes (normal async sync is fine here)
  useEffect(() => {
    if (previousMediaIdRef.current !== mediaId && annotationSyncStatus === "pending") {
      forceSync()
    }
    previousMediaIdRef.current = mediaId
  }, [mediaId, annotationSyncStatus, forceSync])

  // Sync on unmount / page close
  // Use sendBeacon for beforeunload to guarantee delivery
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (annotationSyncStatus === "pending" && mediaId !== null) {
        // Try sendBeacon first (guaranteed delivery on page close)
        const beaconSent = syncAnnotationsWithBeacon(
          serverUrl,
          mediaId,
          pendingAnnotations
        )
        // Fall back to regular sync if beacon fails (might not complete)
        if (!beaconSent) {
          forceSync()
        }
      }
    }

    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload)
      // On unmount (not page close), regular async sync is fine
      if (annotationSyncStatus === "pending") {
        forceSync()
      }
    }
  }, [annotationSyncStatus, forceSync, mediaId, pendingAnnotations, serverUrl])
}
