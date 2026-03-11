import { useQuery } from "@tanstack/react-query"
import { useMemo } from "react"
import { useConnectionState } from "@/hooks/useConnectionState"
import { useConnectionStore } from "@/store/connection"
import { isRecoverableAuthConfigError } from "@/services/auth-errors"
import { tldwClient, type ServerChatSummary } from "@/services/tldw/TldwApiClient"

export type ServerChatHistoryItem = ServerChatSummary & {
  createdAtMs: number
  updatedAtMs?: number | null
}

const SERVER_CHAT_FETCH_LIMIT = 200
const SERVER_CHAT_FETCH_MAX_PAGES = 50
const SERVER_CHAT_SEARCH_LIMIT = 50

type FetchServerChatsPage = (params: {
  limit: number
  offset: number
  signal?: AbortSignal
}) => Promise<{
  chats: ServerChatSummary[]
  total: number
}>

const isAbortLikeError = (error: unknown): boolean => {
  const message =
    error instanceof Error
      ? error.message
      : typeof error === "string"
        ? error
        : String((error as { message?: unknown } | null)?.message || "")
  const normalizedMessage = message.toLowerCase()
  const name =
    error instanceof Error
      ? error.name
      : String((error as { name?: unknown } | null)?.name || "")
  return name === "AbortError" || normalizedMessage.includes("abort")
}

const isRateLimitedError = (error: unknown): boolean => {
  const status = (error as { status?: unknown } | null)?.status
  if (typeof status === "number" && Number.isFinite(status) && status === 429) {
    return true
  }

  const message =
    error instanceof Error
      ? error.message
      : typeof error === "string"
        ? error
        : String((error as { message?: unknown } | null)?.message || "")
  const normalized = message.toLowerCase()
  if (!normalized) return false

  return (
    normalized.includes("rate_limited") ||
    normalized.includes("rate limit") ||
    normalized.includes("too many requests")
  )
}

export const isRecoverableServerChatHistoryError = (error: unknown): boolean => {
  return (
    isRecoverableAuthConfigError(error) ||
    isAbortLikeError(error) ||
    isRateLimitedError(error)
  )
}

export const mapServerChatHistoryItems = (
  chats: ServerChatSummary[]
): ServerChatHistoryItem[] =>
  chats.map((chat) => ({
    ...chat,
    createdAtMs: Date.parse(chat.created_at || ""),
    updatedAtMs: chat.updated_at ? Date.parse(chat.updated_at) : null
  }))

export const filterServerChatHistoryItems = (
  items: ServerChatHistoryItem[],
  query: string
): ServerChatHistoryItem[] => {
  const normalizedQuery = query.trim().toLowerCase()
  if (!normalizedQuery) {
    return items
  }

  return items.filter((item) => {
    const haystack = `${item.title || ""} ${item.topic_label || ""} ${item.state || ""}`.toLowerCase()
    return haystack.includes(normalizedQuery)
  })
}

export const deriveServerChatHistoryViewState = ({
  previousData,
  error
}: {
  previousData: ServerChatHistoryItem[]
  error: unknown
}): {
  data: ServerChatHistoryItem[]
  sidebarRefreshState: "recoverable-error"
  hasUsableData: boolean
  isShowingStaleData: boolean
} => ({
  data: previousData,
  sidebarRefreshState: "recoverable-error",
  hasUsableData: previousData.length > 0,
  isShowingStaleData: previousData.length > 0
})

export const fetchAllServerChatPages = async (
  fetchPage: FetchServerChatsPage,
  options?: {
    limit?: number
    maxPages?: number
    signal?: AbortSignal
  }
): Promise<ServerChatSummary[]> => {
  const limit = Math.max(1, options?.limit ?? SERVER_CHAT_FETCH_LIMIT)
  const maxPages = Math.max(1, options?.maxPages ?? SERVER_CHAT_FETCH_MAX_PAGES)
  const allChats: ServerChatSummary[] = []

  let offset = 0
  let total: number | null = null

  for (let page = 0; page < maxPages; page += 1) {
    let response: { chats: ServerChatSummary[]; total: number }
    try {
      response = await fetchPage({
        limit,
        offset,
        signal: options?.signal
      })
    } catch (error) {
      // Keep already-fetched chat history visible if a later page gets rate-limited.
      if (allChats.length > 0 && isRateLimitedError(error)) {
        break
      }
      throw error
    }
    const { chats, total: pageTotal } = response
    const batch = Array.isArray(chats) ? chats : []

    if (typeof pageTotal === "number" && Number.isFinite(pageTotal) && pageTotal >= 0) {
      total = pageTotal
    }

    if (batch.length === 0) {
      break
    }

    allChats.push(...batch)
    offset += batch.length

    const reachedTotal = total !== null && offset >= total
    const reachedLastPage = batch.length < limit

    if (reachedTotal || reachedLastPage) {
      break
    }
  }

  return allChats
}

type UseServerChatHistoryOptions = {
  enabled?: boolean
  includeDeleted?: boolean
  deletedOnly?: boolean
  mode?: "overview" | "search"
}

export const useServerChatHistory = (
  searchQuery: string,
  options?: UseServerChatHistoryOptions
) => {
  const { isConnected } = useConnectionState()
  const checkConnection = useConnectionStore((state) => state.checkOnce)
  const normalizedQuery = searchQuery.trim().toLowerCase()
  const mode = options?.mode ?? "overview"
  const includeDeleted = options?.includeDeleted ?? false
  const deletedOnly = options?.deletedOnly ?? false
  const canUseConversationSearch =
    mode === "search" &&
    normalizedQuery.length > 0 &&
    !includeDeleted &&
    !deletedOnly
  const queryStrategy = canUseConversationSearch
    ? "search-server"
    : mode === "search"
      ? "search-client"
      : "overview"
  const isEnabled =
    isConnected &&
    (options?.enabled ?? true) &&
    (mode !== "search" || normalizedQuery.length > 0)

  const query = useQuery({
    queryKey: [
      "serverChatHistory",
      {
        includeDeleted,
        deletedOnly,
        mode,
        q: mode === "search" ? normalizedQuery : "",
        strategy: queryStrategy
      }
    ],
    enabled: isEnabled,
    queryFn: async ({ signal }): Promise<ServerChatHistoryItem[]> => {
      await tldwClient.initialize().catch(() => null)
      try {
        if (canUseConversationSearch) {
          const response = await tldwClient.searchConversationsWithMeta(
            {
              query: normalizedQuery,
              limit: SERVER_CHAT_SEARCH_LIMIT,
              offset: 0,
              order_by: "recency"
            },
            { signal }
          )

          return mapServerChatHistoryItems(response.chats)
        }

        const chats = await fetchAllServerChatPages(
          ({ limit, offset, signal: pageSignal }) =>
            tldwClient.listChatsWithMeta(
              {
                limit,
                offset,
                ordering: "-updated_at",
                ...(includeDeleted ? { include_deleted: true } : {}),
                ...(deletedOnly ? { deleted_only: true } : {})
              },
              { signal: pageSignal }
            ),
          {
            signal
          }
        )

        return mapServerChatHistoryItems(chats)
      } catch (e) {
        if (isRecoverableServerChatHistoryError(e)) {
          // Keep sidebar/chat shell usable while connection state catches up.
          void checkConnection().catch(() => null)
          throw e
        }
        // eslint-disable-next-line no-console
        console.error(
          "[serverChatHistory] Failed to fetch server chats",
          e
        )
        throw e
      }
    },
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnMount: false,
    retry: (failureCount, error) =>
      !isRecoverableServerChatHistoryError(error) && failureCount < 1
  })

  const filteredData = useMemo(
    () =>
      canUseConversationSearch
        ? query.data || []
        : filterServerChatHistoryItems(query.data || [], normalizedQuery),
    [canUseConversationSearch, query.data, normalizedQuery]
  )

  const sidebarState = useMemo(() => {
    if (query.status === "success") {
      return {
        data: filteredData,
        sidebarRefreshState: "ready" as const,
        hasUsableData: filteredData.length > 0,
        isShowingStaleData: false
      }
    }

    if (query.status === "error") {
      if (isRecoverableServerChatHistoryError(query.error)) {
        return deriveServerChatHistoryViewState({
          previousData: filteredData,
          error: query.error
        })
      }

      return {
        data: filteredData,
        sidebarRefreshState: "hard-error" as const,
        hasUsableData: filteredData.length > 0,
        isShowingStaleData: false
      }
    }

    return {
      data: filteredData,
      sidebarRefreshState: "idle" as const,
      hasUsableData: filteredData.length > 0,
      isShowingStaleData: false
    }
  }, [filteredData, query.error, query.status])

  return {
    ...query,
    data: sidebarState.data,
    sidebarRefreshState: sidebarState.sidebarRefreshState,
    hasUsableData: sidebarState.hasUsableData,
    isShowingStaleData: sidebarState.isShowingStaleData
  }
}
