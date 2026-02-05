import { useQuery } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw"
import { useConnectionStore } from "@/store/connection"

/**
 * A single reference/citation extracted from the document.
 */
export interface ReferenceEntry {
  raw_text: string
  title?: string
  authors?: string
  year?: number
  venue?: string
  doi?: string
  arxiv_id?: string
  url?: string
  // Enriched fields from external APIs
  citation_count?: number
  semantic_scholar_id?: string
  open_access_pdf?: string
}

/**
 * Response from the references endpoint.
 */
export interface DocumentReferencesResponse {
  media_id: number
  has_references: boolean
  references: ReferenceEntry[]
  enrichment_source?: string
}

/**
 * Hook to fetch document references/bibliography.
 *
 * This endpoint parses the document content to find a references section,
 * extracts individual references, and optionally enriches them with
 * external API data (citation counts, open access PDFs).
 *
 * @param mediaId - The media ID to fetch references for (null to disable query)
 * @param enrich - Whether to enrich with external API data (default: false)
 * @returns Query result with references, loading state, and error
 */
export function useDocumentReferences(
  mediaId: number | null,
  enrich: boolean = false
) {
  const isConnected = useConnectionStore((s) => s.state.isConnected)
  const mode = useConnectionStore((s) => s.state.mode)
  const isServerAvailable = isConnected && mode !== "demo"

  return useQuery({
    queryKey: ["document-references", mediaId, enrich],
    queryFn: async (): Promise<DocumentReferencesResponse | null> => {
      if (mediaId === null) return null
      return await tldwClient.getDocumentReferences(mediaId, { enrich })
    },
    enabled: mediaId !== null && isServerAvailable,
    staleTime: 10 * 60 * 1000, // Cache for 10 minutes
    retry: 1,
    refetchOnWindowFocus: false,
  })
}

/**
 * Helper to build a URL for a reference.
 */
export function getReferenceUrl(ref: ReferenceEntry): string | undefined {
  if (ref.url) return ref.url
  if (ref.doi) return `https://doi.org/${ref.doi}`
  if (ref.arxiv_id) return `https://arxiv.org/abs/${ref.arxiv_id}`
  if (ref.semantic_scholar_id) {
    return `https://www.semanticscholar.org/paper/${ref.semantic_scholar_id}`
  }
  return undefined
}

/**
 * Helper to format reference citation count.
 */
export function formatCitationCount(count?: number): string {
  if (count === undefined || count === null) return ""
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}k`
  }
  return String(count)
}
