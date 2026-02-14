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

type FetchServerChatsPage = (params: {
  limit: number
  offset: number
}) => Promise<{
  chats: ServerChatSummary[]
  total: number
}>

export const isRecoverableServerChatHistoryError = (error: unknown): boolean => {
  return isRecoverableAuthConfigError(error)
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

export const fetchAllServerChatPages = async (
  fetchPage: FetchServerChatsPage,
  options?: {
    limit?: number
    maxPages?: number
  }
): Promise<ServerChatSummary[]> => {
  const limit = Math.max(1, options?.limit ?? SERVER_CHAT_FETCH_LIMIT)
  const maxPages = Math.max(1, options?.maxPages ?? SERVER_CHAT_FETCH_MAX_PAGES)
  const allChats: ServerChatSummary[] = []

  let offset = 0
  let total: number | null = null

  for (let page = 0; page < maxPages; page += 1) {
    const { chats, total: pageTotal } = await fetchPage({ limit, offset })
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

export const useServerChatHistory = (
  searchQuery: string,
  options?: { enabled?: boolean }
) => {
  const { isConnected } = useConnectionState()
  const checkConnection = useConnectionStore((state) => state.checkOnce)
  const normalizedQuery = searchQuery.trim().toLowerCase()
  const isEnabled = isConnected && (options?.enabled ?? true)

  const query = useQuery({
    queryKey: ["serverChatHistory"],
    enabled: isEnabled,
    queryFn: async (): Promise<ServerChatHistoryItem[]> => {
      await tldwClient.initialize().catch(() => null)
      try {
        const chats = await fetchAllServerChatPages(({ limit, offset }) =>
          tldwClient.listChatsWithMeta({
            limit,
            offset,
            ordering: "-updated_at"
          })
        )

        return mapServerChatHistoryItems(chats)
      } catch (e) {
        if (isRecoverableServerChatHistoryError(e)) {
          // Keep sidebar/chat shell usable while connection state catches up.
          void checkConnection().catch(() => null)
          return []
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
    () => filterServerChatHistoryItems(query.data || [], normalizedQuery),
    [query.data, normalizedQuery]
  )

  return {
    ...query,
    data: filteredData
  }
}
