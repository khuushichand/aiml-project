import { useInfiniteQuery } from "@tanstack/react-query"

import {
  listFlashcards,
  type Flashcard,
  type FlashcardListResponse
} from "@/services/flashcards"
import {
  applyManageClientSort,
  cardHasAllTags,
  getManageServerOrderBy,
  normalizeManageTags,
  type DueStatus,
  type UseFlashcardQueriesOptions,
  useFlashcardsEnabled
} from "./useFlashcardQueries"

export const DOCUMENT_VIEW_SUPPORTED_SORTS = ["due", "created"] as const

export type DocumentManageSortBy = (typeof DOCUMENT_VIEW_SUPPORTED_SORTS)[number]

export interface FlashcardDocumentQueryParams {
  deckId?: number | null
  query?: string
  tag?: string
  tags?: string[]
  dueStatus?: DueStatus
  sortBy?: DocumentManageSortBy
  pageSize?: number
}

export interface FlashcardDocumentPage {
  items: Flashcard[]
  nextPageParam?: number
  isTruncated: boolean
  total: number
}

const DOCUMENT_PAGE_SIZE = 100
const DOCUMENT_SCAN_PAGE_SIZE = 500
const DOCUMENT_MAX_SCAN = 10000

const getListTotal = (response: FlashcardListResponse) =>
  Number(response.total ?? response.count ?? 0)

async function fetchSingleTagDocumentPage(
  params: Required<Pick<FlashcardDocumentQueryParams, "dueStatus" | "sortBy" | "pageSize">> &
    Pick<FlashcardDocumentQueryParams, "deckId" | "query"> & {
      primaryTag?: string
    },
  pageIndex: number
): Promise<FlashcardDocumentPage> {
  const response = await listFlashcards({
    deck_id: params.deckId ?? undefined,
    q: params.query || undefined,
    tag: params.primaryTag || undefined,
    due_status: params.dueStatus,
    limit: params.pageSize,
    offset: pageIndex * params.pageSize,
    order_by: getManageServerOrderBy(params.sortBy)
  })
  const items = applyManageClientSort(response.items || [], params.sortBy)

  return {
    items,
    nextPageParam: items.length < params.pageSize ? undefined : pageIndex + 1,
    isTruncated: false,
    total: getListTotal(response)
  }
}

async function fetchMultiTagDocumentPage(
  params: Required<Pick<FlashcardDocumentQueryParams, "dueStatus" | "sortBy" | "pageSize">> &
    Pick<FlashcardDocumentQueryParams, "deckId" | "query"> & {
      normalizedTags: string[]
      primaryTag: string
    },
  pageIndex: number
): Promise<FlashcardDocumentPage> {
  const targetCount = (pageIndex + 1) * params.pageSize
  const matched: Flashcard[] = []
  let offset = 0
  let total = 0
  let reachedEnd = false

  while (offset < DOCUMENT_MAX_SCAN && matched.length < targetCount) {
    const response = await listFlashcards({
      deck_id: params.deckId ?? undefined,
      q: params.query || undefined,
      tag: params.primaryTag,
      due_status: params.dueStatus,
      limit: DOCUMENT_SCAN_PAGE_SIZE,
      offset,
      order_by: getManageServerOrderBy(params.sortBy)
    })
    total = getListTotal(response)
    const items = response.items || []

    if (items.length === 0) {
      reachedEnd = true
      break
    }

    matched.push(...items.filter((card) => cardHasAllTags(card, params.normalizedTags)))

    if (items.length < DOCUMENT_SCAN_PAGE_SIZE) {
      reachedEnd = true
      break
    }

    offset += DOCUMENT_SCAN_PAGE_SIZE
  }

  const sorted = applyManageClientSort(matched, params.sortBy)
  const pageStart = pageIndex * params.pageSize
  const pageItems = sorted.slice(pageStart, pageStart + params.pageSize)
  const isTruncated = total > DOCUMENT_MAX_SCAN || offset >= DOCUMENT_MAX_SCAN
  const hasMoreMatchesLoaded = sorted.length > pageStart + params.pageSize

  return {
    items: pageItems,
    nextPageParam:
      pageItems.length < params.pageSize && !hasMoreMatchesLoaded && reachedEnd && !isTruncated
        ? undefined
        : pageItems.length > 0
          ? pageIndex + 1
          : undefined,
    isTruncated,
    total
  }
}

export function useFlashcardDocumentQuery(
  params: FlashcardDocumentQueryParams,
  options?: UseFlashcardQueriesOptions
) {
  const { flashcardsEnabled } = useFlashcardsEnabled()
  const normalizedTags = normalizeManageTags(params.tags, params.tag)
  const primaryTag = normalizedTags[0]
  const dueStatus = params.dueStatus ?? "all"
  const sortBy = params.sortBy ?? "due"
  const pageSize = params.pageSize ?? DOCUMENT_PAGE_SIZE

  const query = useInfiniteQuery({
    queryKey: [
      "flashcards:document",
      params.deckId ?? null,
      params.query ?? "",
      normalizedTags.join("|"),
      dueStatus,
      sortBy,
      pageSize
    ],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const pageIndex =
        typeof pageParam === "number" && Number.isFinite(pageParam) ? pageParam : 0
      if (normalizedTags.length > 1 && primaryTag) {
        return fetchMultiTagDocumentPage(
          {
            deckId: params.deckId,
            query: params.query,
            dueStatus,
            sortBy,
            pageSize,
            normalizedTags,
            primaryTag
          },
          pageIndex
        )
      }
      return fetchSingleTagDocumentPage(
        {
          deckId: params.deckId,
          query: params.query,
          dueStatus,
          sortBy,
          pageSize,
          primaryTag
        },
        pageIndex
      )
    },
    getNextPageParam: (lastPage) => lastPage.nextPageParam,
    enabled: options?.enabled ?? flashcardsEnabled
  })

  const pages = query.data?.pages || []
  const items = pages.flatMap((page) => page.items)

  return {
    ...query,
    items,
    isTruncated: pages.some((page) => page.isTruncated),
    supportedSorts: [...DOCUMENT_VIEW_SUPPORTED_SORTS]
  }
}
