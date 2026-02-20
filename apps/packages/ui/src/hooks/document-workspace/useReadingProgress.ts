import { useEffect, useRef, useCallback } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw"
import { useConnectionStore } from "@/store/connection"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import type { ViewMode } from "@/components/DocumentWorkspace/types"
import {
  isNotFoundError,
  shouldRetryDocumentWorkspaceQuery,
} from "./request-retry"

/**
 * Sync reading progress using navigator.sendBeacon for guaranteed delivery on page unload.
 * Similar to annotation sync, this ensures reading progress is saved even if the page
 * is closed immediately.
 *
 * @returns true if sendBeacon was used, false if not available or failed
 */
function syncReadingProgressWithBeacon(
  serverUrl: string | null,
  mediaId: number,
  progress: {
    current_page: number
    total_pages: number
    zoom_level?: number
    view_mode?: ViewMode
    cfi?: string
    percentage?: number
  }
): boolean {
  if (!serverUrl || progress.total_pages === 0) {
    return false
  }

  // sendBeacon is not available in all environments (e.g., some older browsers, Node.js)
  if (typeof navigator === "undefined" || !navigator.sendBeacon) {
    return false
  }

  try {
    const url = `${serverUrl}/api/v1/media/${mediaId}/progress`
    const payload = JSON.stringify(progress)

    // sendBeacon returns true if the browser successfully queued the request
    const blob = new Blob([payload], { type: "application/json" })
    return navigator.sendBeacon(url, blob)
  } catch (error) {
    console.error("sendBeacon for reading progress failed:", error)
    return false
  }
}

export interface ReadingProgress {
  media_id: number
  current_page: number
  total_pages: number
  zoom_level: number
  view_mode: ViewMode
  percent_complete: number
  cfi?: string
  last_read_at: string
}

export interface ReadingProgressNotFound {
  media_id: number
  has_progress: false
}

type ReadingProgressResponse = ReadingProgress | ReadingProgressNotFound

function isReadingProgress(
  response: ReadingProgressResponse
): response is ReadingProgress {
  return "current_page" in response
}

/**
 * Hook to fetch reading progress from the backend.
 *
 * Note: This hook only applies server progress on initial load (when no local
 * viewerState exists for the document). When switching between already-open
 * documents, the Zustand store preserves per-document state, so we don't
 * override it with server data. Server progress is used as a fallback for
 * cold starts and fresh document opens.
 */
export function useReadingProgress(mediaId: number | null) {
  const isConnected = useConnectionStore((s) => s.state.isConnected)
  const mode = useConnectionStore((s) => s.state.mode)
  const isServerAvailable = isConnected && mode !== "demo"

  const setCurrentPage = useDocumentWorkspaceStore((s) => s.setCurrentPage)
  const setZoomLevel = useDocumentWorkspaceStore((s) => s.setZoomLevel)
  const setViewMode = useDocumentWorkspaceStore((s) => s.setViewMode)
  const setCurrentCfi = useDocumentWorkspaceStore((s) => s.setCurrentCfi)
  const setCurrentPercentage = useDocumentWorkspaceStore((s) => s.setCurrentPercentage)
  const openDocuments = useDocumentWorkspaceStore((s) => s.openDocuments)
  const setProgressHealth = useDocumentWorkspaceStore((s) => s.setProgressHealth)

  // Track which documents have had server progress applied (only apply once per session)
  const appliedProgressRef = useRef<Set<number>>(new Set())

  return useQuery<ReadingProgressResponse | null>({
    queryKey: ["reading-progress", mediaId],
    queryFn: async (): Promise<ReadingProgressResponse | null> => {
      if (mediaId === null) return null

      let response
      try {
        response = await tldwClient.getReadingProgress(mediaId)
      } catch (error) {
        const status = (error as { status?: number })?.status
        if (status === 500) {
          setProgressHealth("error")
        } else {
          setProgressHealth("unknown")
        }
        throw error
      }
      setProgressHealth("ok")

      // Only apply server progress if:
      // 1. We haven't already applied progress for this document this session
      // 2. The document doesn't have local viewerState (fresh open)
      const doc = openDocuments.find((d) => d.id === mediaId)
      const hasLocalState = doc?.viewerState !== undefined
      const alreadyApplied = appliedProgressRef.current.has(mediaId)

      if (response.current_page && response.zoom_level && response.view_mode) {
        if (!hasLocalState && !alreadyApplied) {
          setCurrentPage(response.current_page)
          setZoomLevel(response.zoom_level)
          setViewMode(response.view_mode as ViewMode)
          // Restore EPUB position if CFI is available
          if (response.cfi) {
            setCurrentCfi(response.cfi)
            setCurrentPercentage(response.percent_complete ?? 0)
          }
          appliedProgressRef.current.add(mediaId)
        }
      }

      // Normalize response
      if (response.has_progress === false) {
        return { media_id: response.media_id, has_progress: false }
      }

      return {
        media_id: response.media_id,
        current_page: response.current_page!,
        total_pages: response.total_pages!,
        zoom_level: response.zoom_level!,
        view_mode: response.view_mode as ViewMode,
        percent_complete: response.percent_complete!,
        cfi: response.cfi,
        last_read_at: response.last_read_at!
      }
    },
    enabled: mediaId !== null && isServerAvailable,
    staleTime: 60 * 1000, // Cache for 1 minute
    retry: (failureCount, error) =>
      shouldRetryDocumentWorkspaceQuery(failureCount, error, 1),
    refetchOnWindowFocus: false
  })
}

/**
 * Mutation hook to update reading progress
 */
export function useUpdateReadingProgress() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      mediaId,
      progress
    }: {
      mediaId: number
      progress: {
        current_page: number
        total_pages: number
        zoom_level?: number
        view_mode?: ViewMode
        cfi?: string
        percentage?: number
      }
    }) => {
      return await tldwClient.updateReadingProgress(mediaId, progress)
    },
    onSuccess: (_data, { mediaId }) => {
      queryClient.invalidateQueries({ queryKey: ["reading-progress", mediaId] })
    }
  })
}

/**
 * Hook that automatically saves reading progress with debouncing.
 *
 * Monitors the store's currentPage, zoomLevel, and viewMode,
 * and saves changes to the backend after a debounce period.
 *
 * @param mediaId - The active document's media ID
 * @param debounceMs - Debounce time in milliseconds (default: 5000)
 */
export function useReadingProgressAutoSave(
  mediaId: number | null,
  debounceMs: number = 5000
) {
  const isConnected = useConnectionStore((s) => s.state.isConnected)
  const mode = useConnectionStore((s) => s.state.mode)
  const isServerAvailable = isConnected && mode !== "demo"

  const currentPage = useDocumentWorkspaceStore((s) => s.currentPage)
  const totalPages = useDocumentWorkspaceStore((s) => s.totalPages)
  const zoomLevel = useDocumentWorkspaceStore((s) => s.zoomLevel)
  const viewMode = useDocumentWorkspaceStore((s) => s.viewMode)
  const currentCfi = useDocumentWorkspaceStore((s) => s.currentCfi)
  const currentPercentage = useDocumentWorkspaceStore((s) => s.currentPercentage)

  const updateMutation = useUpdateReadingProgress()
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const missingMediaIdsRef = useRef<Set<number>>(new Set())
  const lastSavedRef = useRef<{
    page: number
    zoom: number
    mode: ViewMode
    cfi: string | null
  } | null>(null)

  // Check if there are unsaved changes
  const hasChanges = useCallback(() => {
    if (!lastSavedRef.current) return true
    return (
      lastSavedRef.current.page !== currentPage ||
      lastSavedRef.current.zoom !== zoomLevel ||
      lastSavedRef.current.mode !== viewMode ||
      lastSavedRef.current.cfi !== currentCfi
    )
  }, [currentPage, zoomLevel, viewMode, currentCfi])

  // Save function
  const saveProgress = useCallback(async () => {
    if (
      !mediaId ||
      !isServerAvailable ||
      totalPages === 0 ||
      !hasChanges() ||
      missingMediaIdsRef.current.has(mediaId)
    ) {
      return
    }

    try {
      await updateMutation.mutateAsync({
        mediaId,
        progress: {
          current_page: currentPage,
          total_pages: totalPages,
          zoom_level: zoomLevel,
          view_mode: viewMode,
          // Include CFI and percentage for EPUB documents
          ...(currentCfi ? { cfi: currentCfi, percentage: currentPercentage } : {})
        }
      })

      missingMediaIdsRef.current.delete(mediaId)
      lastSavedRef.current = {
        page: currentPage,
        zoom: zoomLevel,
        mode: viewMode,
        cfi: currentCfi
      }
    } catch (error) {
      if (mediaId && isNotFoundError(error)) {
        missingMediaIdsRef.current.add(mediaId)
        return
      }
      console.error("Failed to save reading progress:", error)
    }
  }, [
    mediaId,
    isServerAvailable,
    currentPage,
    totalPages,
    zoomLevel,
    viewMode,
    currentCfi,
    currentPercentage,
    hasChanges,
    updateMutation
  ])

  // Debounced auto-save effect
  useEffect(() => {
    if (!mediaId || !isServerAvailable || totalPages === 0) {
      return
    }

    // Clear existing timeout
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current)
    }

    // Set new debounced save
    saveTimeoutRef.current = setTimeout(() => {
      saveProgress()
    }, debounceMs)

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current)
      }
    }
  }, [mediaId, isServerAvailable, currentPage, zoomLevel, viewMode, currentCfi, totalPages, debounceMs, saveProgress])

  // Force save (useful for immediate save)
  const forceSave = useCallback(() => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current)
    }
    saveProgress()
  }, [saveProgress])

  return {
    isSaving: updateMutation.isPending,
    forceSave,
    error: updateMutation.error
  }
}

/**
 * Hook that saves reading progress when the document is closed or changed.
 * Pass the forceSave callback returned by useReadingProgressAutoSave to avoid
 * duplicating autosave effects.
 *
 * Uses navigator.sendBeacon for page unload events to guarantee delivery,
 * since regular async requests may not complete before the page closes.
 */
export function useReadingProgressSaveOnClose(
  mediaId: number | null,
  forceSave: () => void
) {
  const totalPages = useDocumentWorkspaceStore((s) => s.totalPages)
  const currentPage = useDocumentWorkspaceStore((s) => s.currentPage)
  const zoomLevel = useDocumentWorkspaceStore((s) => s.zoomLevel)
  const viewMode = useDocumentWorkspaceStore((s) => s.viewMode)
  const currentCfi = useDocumentWorkspaceStore((s) => s.currentCfi)
  const currentPercentage = useDocumentWorkspaceStore((s) => s.currentPercentage)
  const serverUrl = useConnectionStore((s) => s.state.serverUrl)
  const previousMediaIdRef = useRef<number | null>(mediaId)
  const forceSaveRef = useRef(forceSave)
  const totalPagesRef = useRef(totalPages)
  const currentPageRef = useRef(currentPage)
  const zoomLevelRef = useRef(zoomLevel)
  const viewModeRef = useRef(viewMode)
  const currentCfiRef = useRef(currentCfi)
  const currentPercentageRef = useRef(currentPercentage)
  const serverUrlRef = useRef(serverUrl)
  const mediaIdRef = useRef(mediaId)

  useEffect(() => {
    forceSaveRef.current = forceSave
  }, [forceSave])

  useEffect(() => {
    totalPagesRef.current = totalPages
    currentPageRef.current = currentPage
    zoomLevelRef.current = zoomLevel
    viewModeRef.current = viewMode
    currentCfiRef.current = currentCfi
    currentPercentageRef.current = currentPercentage
  }, [totalPages, currentPage, zoomLevel, viewMode, currentCfi, currentPercentage])

  useEffect(() => {
    serverUrlRef.current = serverUrl
  }, [serverUrl])

  useEffect(() => {
    mediaIdRef.current = mediaId
  }, [mediaId])

  // Save when document changes (normal async sync is fine here)
  useEffect(() => {
    if (previousMediaIdRef.current !== mediaId && previousMediaIdRef.current !== null) {
      forceSaveRef.current()
    }
    previousMediaIdRef.current = mediaId
  }, [mediaId])

  // Save on unmount / page close
  // Use sendBeacon for beforeunload to guarantee delivery
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (mediaIdRef.current !== null && totalPagesRef.current > 0) {
        // Build progress object
        const progress: {
          current_page: number
          total_pages: number
          zoom_level?: number
          view_mode?: ViewMode
          cfi?: string
          percentage?: number
        } = {
          current_page: currentPageRef.current,
          total_pages: totalPagesRef.current,
          zoom_level: zoomLevelRef.current,
          view_mode: viewModeRef.current
        }

        // Include CFI and percentage for EPUB documents
        if (currentCfiRef.current) {
          progress.cfi = currentCfiRef.current
          progress.percentage = currentPercentageRef.current
        }

        // Try sendBeacon first (guaranteed delivery on page close)
        const beaconSent = syncReadingProgressWithBeacon(
          serverUrlRef.current,
          mediaIdRef.current,
          progress
        )

        // Fall back to regular sync if beacon fails (might not complete)
        if (!beaconSent) {
          forceSaveRef.current()
        }
      }
    }

    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload)
      // On unmount (not page close), regular async sync is fine
      if (totalPagesRef.current > 0) {
        forceSaveRef.current()
      }
    }
  }, [])
}
