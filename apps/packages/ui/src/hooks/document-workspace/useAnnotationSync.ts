import { useEffect, useRef, useCallback } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw"
import { useConnectionStore } from "@/store/connection"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import type { Annotation, AnnotationColor } from "@/components/DocumentWorkspace/types"

/**
 * Hook to automatically sync pending annotations to the backend.
 *
 * This hook watches the store's pendingAnnotations and syncs them
 * to the backend when connection is available.
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
    },
    onError: () => {
      setAnnotationSyncStatus("error")
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

  return {
    isSyncing: syncMutation.isPending,
    syncStatus: annotationSyncStatus,
    forceSync,
    error: syncMutation.error
  }
}

/**
 * Hook that syncs annotations when the document is closed or changed.
 * Call this from the document workspace page component.
 */
export function useAnnotationSyncOnClose(mediaId: number | null) {
  const { forceSync } = useAnnotationSync(mediaId, 0)
  const annotationSyncStatus = useDocumentWorkspaceStore(
    (s) => s.annotationSyncStatus
  )
  const previousMediaIdRef = useRef<number | null>(mediaId)

  // Sync when document changes
  useEffect(() => {
    if (previousMediaIdRef.current !== mediaId && annotationSyncStatus === "pending") {
      forceSync()
    }
    previousMediaIdRef.current = mediaId
  }, [mediaId, annotationSyncStatus, forceSync])

  // Sync on unmount / page close
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (annotationSyncStatus === "pending") {
        forceSync()
      }
    }

    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload)
      if (annotationSyncStatus === "pending") {
        forceSync()
      }
    }
  }, [annotationSyncStatus, forceSync])
}
