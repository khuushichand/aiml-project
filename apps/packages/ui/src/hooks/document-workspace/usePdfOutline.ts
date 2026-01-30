import { useQuery } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw"
import { useConnectionStore } from "@/store/connection"
import type { TocItem, DocumentOutline } from "@/components/DocumentWorkspace/types"

export interface OutlineEntry {
  level: number
  title: string
  page: number
}

export interface DocumentOutlineResponse {
  media_id: number
  has_outline: boolean
  entries: OutlineEntry[]
  total_pages: number
}

/**
 * Converts flat outline entries to hierarchical TocItem structure
 */
function buildHierarchy(entries: OutlineEntry[]): TocItem[] {
  if (entries.length === 0) return []

  const items: TocItem[] = []
  const stack: { item: TocItem; level: number }[] = []

  for (const entry of entries) {
    const item: TocItem = {
      title: entry.title,
      page: entry.page,
      level: entry.level,
      children: []
    }

    // Pop items from stack that are at same or higher level
    while (stack.length > 0 && stack[stack.length - 1].level >= entry.level) {
      stack.pop()
    }

    if (stack.length === 0) {
      // Top-level item
      items.push(item)
    } else {
      // Child of the last item in stack
      const parent = stack[stack.length - 1].item
      if (!parent.children) {
        parent.children = []
      }
      parent.children.push(item)
    }

    stack.push({ item, level: entry.level })
  }

  return items
}

/**
 * Hook to fetch document outline/table of contents from the server.
 *
 * @param mediaId - The media ID to fetch outline for (null to disable query)
 * @returns Query result with outline data, loading state, and error
 */
export function usePdfOutline(mediaId: number | null) {
  const isConnected = useConnectionStore((s) => s.state.isConnected)
  const mode = useConnectionStore((s) => s.state.mode)
  const isServerAvailable = isConnected && mode !== "demo"

  return useQuery({
    queryKey: ["document-outline", mediaId],
    queryFn: async (): Promise<DocumentOutline | null> => {
      if (mediaId === null) return null

      const response = await tldwClient.getDocumentOutline(mediaId)

      // Convert flat entries to hierarchical structure
      const items = buildHierarchy(response.entries)

      return {
        documentId: response.media_id,
        items
      }
    },
    enabled: mediaId !== null && isServerAvailable,
    staleTime: 10 * 60 * 1000, // Cache for 10 minutes (outlines don't change)
    retry: 1,
    refetchOnWindowFocus: false
  })
}

/**
 * Hook to get total pages from outline response.
 * Useful when you need page count without the full outline.
 */
export function useDocumentPageCount(mediaId: number | null) {
  const isConnected = useConnectionStore((s) => s.state.isConnected)
  const mode = useConnectionStore((s) => s.state.mode)
  const isServerAvailable = isConnected && mode !== "demo"

  return useQuery({
    queryKey: ["document-page-count", mediaId],
    queryFn: async (): Promise<number> => {
      if (mediaId === null) return 0

      const response = await tldwClient.getDocumentOutline(mediaId)
      return response.total_pages
    },
    enabled: mediaId !== null && isServerAvailable,
    staleTime: 10 * 60 * 1000,
    retry: 1,
    refetchOnWindowFocus: false
  })
}
