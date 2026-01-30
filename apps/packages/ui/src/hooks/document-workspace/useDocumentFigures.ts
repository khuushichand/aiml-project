import { useQuery } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw"
import { useConnectionStore } from "@/store/connection"

export interface DocumentFigure {
  id: string
  page: number
  width: number
  height: number
  format: string
  data_url?: string
  caption?: string
}

export interface DocumentFiguresResponse {
  media_id: number
  has_figures: boolean
  figures: DocumentFigure[]
  total_count: number
}

/**
 * Hook to fetch document figures/images from the server.
 *
 * @param mediaId - The media ID to fetch figures for (null to disable query)
 * @param options - Query options
 * @returns Query result with figures data, loading state, and error
 */
export function useDocumentFigures(
  mediaId: number | null,
  options?: { minSize?: number }
) {
  const isConnected = useConnectionStore((s) => s.state.isConnected)
  const mode = useConnectionStore((s) => s.state.mode)
  const isServerAvailable = isConnected && mode !== "demo"

  return useQuery<DocumentFiguresResponse | null>({
    queryKey: ["document-figures", mediaId, options?.minSize],
    queryFn: async (): Promise<DocumentFiguresResponse | null> => {
      if (mediaId === null) return null

      const response = await tldwClient.getDocumentFigures(mediaId, {
        minSize: options?.minSize
      })

      return {
        media_id: response.media_id,
        has_figures: response.has_figures,
        figures: response.figures,
        total_count: response.total_count
      }
    },
    enabled: mediaId !== null && isServerAvailable,
    staleTime: 10 * 60 * 1000, // Cache for 10 minutes
    retry: 1,
    refetchOnWindowFocus: false
  })
}
