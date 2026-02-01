import { useQuery } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw"
import { useConnectionStore } from "@/store/connection"
import type { DocumentMetadata, DocumentType } from "@/components/DocumentWorkspace/types"

interface MediaDetailResponse {
  id: number
  uuid?: string
  title?: string
  author?: string
  content?: string
  content_hash?: string
  type?: string
  keywords?: string[]
  metadata?: Record<string, unknown>
  created_at?: string
  last_modified?: string
  file_size?: number
  page_count?: number
  versions?: unknown[]
}

/**
 * Infer document type from media type string
 */
function inferDocumentType(mediaType?: string): DocumentType {
  if (!mediaType) return "pdf"
  const lower = mediaType.toLowerCase()
  if (lower.includes("epub")) return "epub"
  return "pdf"
}

/**
 * Parse authors from author string (may be comma-separated)
 */
function parseAuthors(author?: string): string[] | undefined {
  if (!author) return undefined
  return author
    .split(/[,;&]/)
    .map((a) => a.trim())
    .filter(Boolean)
}

/**
 * Hook to fetch document metadata from the server.
 *
 * Uses the existing GET /api/v1/media/{media_id} endpoint.
 *
 * @param mediaId - The media ID to fetch metadata for (null to disable query)
 * @returns Query result with metadata, loading state, and error
 */
export function useDocumentMetadata(mediaId: number | null) {
  const isConnected = useConnectionStore((s) => s.state.isConnected)
  const mode = useConnectionStore((s) => s.state.mode)
  const isServerAvailable = isConnected && mode !== "demo"

  return useQuery({
    queryKey: ["document-metadata", mediaId],
    queryFn: async (): Promise<DocumentMetadata | null> => {
      if (mediaId === null) return null

      const response: MediaDetailResponse = await tldwClient.getMediaDetails(
        mediaId,
        {
          include_content: false,
          include_versions: false
        }
      )

      const metadata = response.metadata || {}

      return {
        id: response.id,
        title: response.title || "Untitled",
        authors: parseAuthors(response.author),
        abstract: metadata.abstract as string | undefined,
        keywords: response.keywords,
        pageCount:
          response.page_count ?? (metadata.page_count as number | undefined),
        createdDate: response.created_at
          ? new Date(response.created_at)
          : undefined,
        modifiedDate: response.last_modified
          ? new Date(response.last_modified)
          : undefined,
        fileSize: response.file_size,
        type: inferDocumentType(response.type)
      }
    },
    enabled: mediaId !== null && isServerAvailable,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    retry: 1,
    refetchOnWindowFocus: false
  })
}
