import { useQuery } from "@tanstack/react-query"
import type { NavItem } from "epubjs"
import type { TocItem, DocumentOutline } from "@/components/DocumentWorkspace/types"

/**
 * Converts epub.js NavItem structure to our TocItem structure.
 * NavItems use href for navigation, TocItems use page numbers.
 * For EPUB, we store the href in a custom property and use -1 for page.
 */
function convertNavToTocItems(nav: NavItem[], level: number = 0): TocItem[] {
  return nav.map((item, idx) => ({
    title: item.label.trim(),
    page: idx + 1, // Sequential numbering for display
    level,
    href: item.href, // Store href for EPUB navigation
    children: item.subitems ? convertNavToTocItems(item.subitems, level + 1) : undefined
  }))
}

export interface UseEpubOutlineOptions {
  /** Whether to enable the query */
  enabled?: boolean
}

/**
 * Hook to get TOC/outline from an EPUB's navigation.
 *
 * Unlike PDF outline which is fetched from server, EPUB outline
 * is extracted client-side from the epub.js book instance.
 *
 * @param toc - The navigation TOC from epub.js (book.navigation.toc)
 * @param documentId - The document ID for cache key
 * @param options - Query options
 */
export function useEpubOutline(
  toc: NavItem[] | null | undefined,
  documentId: number | null,
  options?: UseEpubOutlineOptions
) {
  const enabled = options?.enabled ?? true

  return useQuery({
    queryKey: ["epub-outline", documentId],
    queryFn: async (): Promise<DocumentOutline | null> => {
      if (!toc || documentId === null) return null

      const items = convertNavToTocItems(toc)

      return {
        documentId,
        items
      }
    },
    enabled: toc !== null && toc !== undefined && documentId !== null && enabled,
    staleTime: Infinity, // TOC doesn't change
    refetchOnWindowFocus: false
  })
}

/**
 * Flatten TOC items for easier searching and navigation.
 */
export function flattenTocItems(items: TocItem[]): TocItem[] {
  const result: TocItem[] = []

  function traverse(items: TocItem[]) {
    for (const item of items) {
      result.push(item)
      if (item.children) {
        traverse(item.children)
      }
    }
  }

  traverse(items)
  return result
}

/**
 * Find the TOC item that matches a given href.
 */
export function findTocItemByHref(items: TocItem[], href: string): TocItem | undefined {
  const flat = flattenTocItems(items)
  // Match by href (may include anchor)
  const hrefBase = href.split("#")[0]
  return flat.find((item) => {
    if (!item.href) return false
    const itemHrefBase = item.href.split("#")[0]
    return itemHrefBase === hrefBase || href.includes(itemHrefBase)
  })
}
