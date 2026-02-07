import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw"
import { useConnectionStore } from "@/store/connection"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import type { Annotation, AnnotationColor, AnnotationType } from "@/components/DocumentWorkspace/types"

export interface AnnotationResponse {
  id: string
  media_id: number
  location: string
  text: string
  color: AnnotationColor
  note?: string
  annotation_type: AnnotationType
  chapter_title?: string
  percentage?: number
  created_at: string
  updated_at: string
}

export interface AnnotationsListResponse {
  media_id: number
  annotations: AnnotationResponse[]
  total_count: number
}

/**
 * Convert backend annotation response to frontend Annotation type
 */
function toAnnotation(response: AnnotationResponse): Annotation {
  return {
    id: response.id,
    documentId: response.media_id,
    location: isNaN(Number(response.location))
      ? response.location
      : Number(response.location),
    text: response.text,
    color: response.color,
    note: response.note,
    annotationType: response.annotation_type,
    chapterTitle: response.chapter_title,
    percentage: response.percentage,
    createdAt: new Date(response.created_at),
    updatedAt: new Date(response.updated_at)
  }
}

/**
 * Hook to fetch annotations for a document from the backend.
 * Automatically syncs to the store when loaded.
 */
export function useAnnotations(mediaId: number | null) {
  const isConnected = useConnectionStore((s) => s.state.isConnected)
  const mode = useConnectionStore((s) => s.state.mode)
  const isServerAvailable = isConnected && mode !== "demo"
  const setAnnotations = useDocumentWorkspaceStore((s) => s.setAnnotations)
  const setAnnotationSyncStatus = useDocumentWorkspaceStore(
    (s) => s.setAnnotationSyncStatus
  )
  const setAnnotationsHealth = useDocumentWorkspaceStore(
    (s) => s.setAnnotationsHealth
  )

  return useQuery<AnnotationsListResponse | null>({
    queryKey: ["document-annotations", mediaId],
    queryFn: async (): Promise<AnnotationsListResponse | null> => {
      if (mediaId === null) return null

      try {
        const response = await tldwClient.listAnnotations(mediaId)

        // Sync to store
        const annotations = response.annotations.map(toAnnotation)
        setAnnotations(annotations)
        setAnnotationSyncStatus("synced")

        setAnnotationsHealth("ok")
        return response
      } catch (error) {
        setAnnotationSyncStatus("error")
        const status = (error as { status?: number })?.status
        if (status && status >= 500) {
          setAnnotationsHealth("error")
        } else {
          setAnnotationsHealth("unknown")
        }
        throw error
      }
    },
    enabled: mediaId !== null && isServerAvailable,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    retry: 2,
    refetchOnWindowFocus: false
  })
}

/**
 * Mutation hook to create a new annotation
 */
export function useCreateAnnotation() {
  const queryClient = useQueryClient()
  const setAnnotationSyncStatus = useDocumentWorkspaceStore(
    (s) => s.setAnnotationSyncStatus
  )

  return useMutation({
    mutationFn: async ({
      mediaId,
      annotation
    }: {
      mediaId: number
      annotation: {
        location: string
        text: string
        color?: AnnotationColor
        note?: string
        annotation_type?: AnnotationType
      }
    }) => {
      const response = await tldwClient.createAnnotation(mediaId, annotation)
      return toAnnotation(response)
    },
    onSuccess: (annotation, { mediaId }) => {
      // Invalidate cache to refetch
      queryClient.invalidateQueries({ queryKey: ["document-annotations", mediaId] })
      setAnnotationSyncStatus("synced")
    },
    onError: () => {
      setAnnotationSyncStatus("error")
    }
  })
}

/**
 * Mutation hook to update an existing annotation
 */
export function useUpdateAnnotation() {
  const queryClient = useQueryClient()
  const updateAnnotation = useDocumentWorkspaceStore((s) => s.updateAnnotation)
  const setAnnotationSyncStatus = useDocumentWorkspaceStore(
    (s) => s.setAnnotationSyncStatus
  )

  return useMutation({
    mutationFn: async ({
      mediaId,
      annotationId,
      updates
    }: {
      mediaId: number
      annotationId: string
      updates: {
        text?: string
        color?: AnnotationColor
        note?: string
      }
    }) => {
      const response = await tldwClient.updateAnnotation(
        mediaId,
        annotationId,
        updates
      )
      return toAnnotation(response)
    },
    onMutate: async ({ annotationId, updates }) => {
      // Optimistic update
      updateAnnotation(annotationId, updates)
    },
    onSuccess: (_annotation, { mediaId }) => {
      queryClient.invalidateQueries({ queryKey: ["document-annotations", mediaId] })
      setAnnotationSyncStatus("synced")
    },
    onError: (_error, { mediaId }) => {
      // Refetch to restore correct state
      queryClient.invalidateQueries({ queryKey: ["document-annotations", mediaId] })
      setAnnotationSyncStatus("error")
    }
  })
}

/**
 * Mutation hook to delete an annotation
 */
export function useDeleteAnnotation() {
  const queryClient = useQueryClient()
  const removeAnnotation = useDocumentWorkspaceStore((s) => s.removeAnnotation)
  const setAnnotationSyncStatus = useDocumentWorkspaceStore(
    (s) => s.setAnnotationSyncStatus
  )

  return useMutation({
    mutationFn: async ({
      mediaId,
      annotationId
    }: {
      mediaId: number
      annotationId: string
    }) => {
      await tldwClient.deleteAnnotation(mediaId, annotationId)
      return annotationId
    },
    onMutate: async ({ annotationId }) => {
      // Optimistic delete
      removeAnnotation(annotationId)
    },
    onSuccess: (_annotationId, { mediaId }) => {
      queryClient.invalidateQueries({ queryKey: ["document-annotations", mediaId] })
      setAnnotationSyncStatus("synced")
    },
    onError: (_error, { mediaId }) => {
      // Refetch to restore correct state
      queryClient.invalidateQueries({ queryKey: ["document-annotations", mediaId] })
      setAnnotationSyncStatus("error")
    }
  })
}
