import { useEffect, useRef, useCallback } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw"
import { useConnectionStore } from "@/store/connection"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import type { ViewMode } from "@/components/DocumentWorkspace/types"

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

  // Track which documents have had server progress applied (only apply once per session)
  const appliedProgressRef = useRef<Set<number>>(new Set())

  return useQuery<ReadingProgressResponse | null>({
    queryKey: ["reading-progress", mediaId],
    queryFn: async (): Promise<ReadingProgressResponse | null> => {
      if (mediaId === null) return null

      const response = await tldwClient.getReadingProgress(mediaId)

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
    retry: 1,
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
    if (!mediaId || !isServerAvailable || totalPages === 0 || !hasChanges()) {
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

      lastSavedRef.current = {
        page: currentPage,
        zoom: zoomLevel,
        mode: viewMode,
        cfi: currentCfi
      }
    } catch (error) {
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
 */
export function useReadingProgressSaveOnClose(mediaId: number | null) {
  const { forceSave } = useReadingProgressAutoSave(mediaId, 0)
  const totalPages = useDocumentWorkspaceStore((s) => s.totalPages)
  const previousMediaIdRef = useRef<number | null>(mediaId)

  // Save when document changes
  useEffect(() => {
    if (previousMediaIdRef.current !== mediaId && previousMediaIdRef.current !== null) {
      forceSave()
    }
    previousMediaIdRef.current = mediaId
  }, [mediaId, forceSave])

  // Save on unmount / page close
  useEffect(() => {
    const handleBeforeUnload = () => {
      forceSave()
    }

    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload)
      if (totalPages > 0) {
        forceSave()
      }
    }
  }, [forceSave, totalPages])
}
