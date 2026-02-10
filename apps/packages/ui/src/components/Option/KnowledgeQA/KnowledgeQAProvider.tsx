/**
 * KnowledgeQAProvider - Context provider for Knowledge QA state management
 */

import React, {
  createContext,
  useContext,
  useReducer,
  useCallback,
  useMemo,
  useEffect,
  useRef,
  type ReactNode,
} from "react"
import { useStorage } from "@plasmohq/storage/hook"
import type {
  KnowledgeQAState,
  KnowledgeQAActions,
  KnowledgeQAContextValue,
  RagResult,
  RagContextData,
  SearchHistoryItem,
  KnowledgeQAMessage,
  KnowledgeQAThread,
  CitationRef,
} from "./types"
import {
  DEFAULT_RAG_SETTINGS,
  applyRagPreset,
  buildRagSearchRequest,
  type RagSettings,
  type RagPresetName,
} from "@/services/rag/unified-rag"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { useAntdMessage } from "@/hooks/useAntdMessage"
import { KNOWLEDGE_QA_KEYWORD } from "./constants"

const LOCAL_THREAD_PREFIX = "local-"
const DEFAULT_CHARACTER_NAME = "Helpful AI Assistant"
const KNOWLEDGE_QA_SETTINGS_OVERRIDES: Partial<RagSettings> = {
  enable_web_fallback: true,
  parent_context_size: 100,
  agentic_time_budget_sec: 30,
  agentic_max_redundancy: 1,
}

// Initial state
const initialState: KnowledgeQAState = {
  query: "",
  isSearching: false,
  results: [],
  answer: null,
  citations: [],
  error: null,

  currentThreadId: null,
  messages: [],
  threads: [],

  preset: "balanced",
  settings: { ...DEFAULT_RAG_SETTINGS, ...KNOWLEDGE_QA_SETTINGS_OVERRIDES },
  expertMode: false,

  searchHistory: [],
  historySidebarOpen: true,

  settingsPanelOpen: false,
  focusedSourceIndex: null,
}

const isLocalThreadId = (id: string | null | undefined) =>
  Boolean(id && id.startsWith(LOCAL_THREAD_PREFIX))

// Action types
type Action =
  | { type: "SET_QUERY"; payload: string }
  | { type: "SET_SEARCHING"; payload: boolean }
  | { type: "SET_RESULTS"; payload: { results: RagResult[]; answer: string | null; citations: CitationRef[] } }
  | { type: "SET_ERROR"; payload: string | null }
  | { type: "CLEAR_RESULTS" }
  | { type: "SET_THREAD_ID"; payload: string | null }
  | { type: "SET_MESSAGES"; payload: KnowledgeQAMessage[] }
  | { type: "ADD_MESSAGE"; payload: KnowledgeQAMessage }
  | { type: "SET_THREADS"; payload: KnowledgeQAThread[] }
  | { type: "ADD_THREAD"; payload: KnowledgeQAThread }
  | { type: "SET_PRESET"; payload: RagPresetName }
  | {
      type: "HYDRATE_DEFAULTS"
      payload: { preset: RagPresetName; settings: RagSettings }
    }
  | { type: "SET_SETTINGS"; payload: RagSettings }
  | { type: "UPDATE_SETTING"; payload: { key: keyof RagSettings; value: unknown } }
  | { type: "TOGGLE_EXPERT_MODE" }
  | { type: "SET_SEARCH_HISTORY"; payload: SearchHistoryItem[] }
  | { type: "ADD_HISTORY_ITEM"; payload: SearchHistoryItem }
  | { type: "REMOVE_HISTORY_ITEM"; payload: string }
  | { type: "SET_SETTINGS_PANEL_OPEN"; payload: boolean }
  | { type: "SET_HISTORY_SIDEBAR_OPEN"; payload: boolean }
  | { type: "SET_FOCUSED_SOURCE"; payload: number | null }

// Reducer
function reducer(state: KnowledgeQAState, action: Action): KnowledgeQAState {
  switch (action.type) {
    case "SET_QUERY":
      return { ...state, query: action.payload }
    case "SET_SEARCHING":
      return { ...state, isSearching: action.payload, error: action.payload ? null : state.error }
    case "SET_RESULTS":
      return {
        ...state,
        results: action.payload.results,
        answer: action.payload.answer,
        citations: action.payload.citations,
        isSearching: false,
      }
    case "SET_ERROR":
      return { ...state, error: action.payload, isSearching: false }
    case "CLEAR_RESULTS":
      return { ...state, results: [], answer: null, citations: [], error: null }
    case "SET_THREAD_ID":
      return { ...state, currentThreadId: action.payload }
    case "SET_MESSAGES":
      return { ...state, messages: action.payload }
    case "ADD_MESSAGE":
      return { ...state, messages: [...state.messages, action.payload] }
    case "SET_THREADS":
      return { ...state, threads: action.payload }
    case "ADD_THREAD":
      return { ...state, threads: [action.payload, ...state.threads] }
    case "SET_PRESET": {
      const presetSettings =
        action.payload === "custom"
          ? state.settings
          : applyRagPreset(action.payload as Exclude<RagPresetName, "custom">)
      return {
        ...state,
        preset: action.payload,
        settings:
          action.payload === "custom"
            ? state.settings
            : {
                ...presetSettings,
                ...KNOWLEDGE_QA_SETTINGS_OVERRIDES,
                enable_web_fallback: state.settings.enable_web_fallback,
              },
      }
    }
    case "HYDRATE_DEFAULTS":
      return {
        ...state,
        preset: action.payload.preset,
        settings: action.payload.settings,
      }
    case "SET_SETTINGS":
      return { ...state, settings: action.payload, preset: "custom" }
    case "UPDATE_SETTING":
      return {
        ...state,
        settings: { ...state.settings, [action.payload.key]: action.payload.value },
        preset: "custom",
      }
    case "TOGGLE_EXPERT_MODE":
      return { ...state, expertMode: !state.expertMode }
    case "SET_SEARCH_HISTORY":
      return { ...state, searchHistory: action.payload }
    case "ADD_HISTORY_ITEM":
      return { ...state, searchHistory: [action.payload, ...state.searchHistory.slice(0, 99)] }
    case "REMOVE_HISTORY_ITEM":
      return { ...state, searchHistory: state.searchHistory.filter((h) => h.id !== action.payload) }
    case "SET_SETTINGS_PANEL_OPEN":
      return { ...state, settingsPanelOpen: action.payload }
    case "SET_HISTORY_SIDEBAR_OPEN":
      return { ...state, historySidebarOpen: action.payload }
    case "SET_FOCUSED_SOURCE":
      return { ...state, focusedSourceIndex: action.payload }
    default:
      return state
  }
}

// Context
const KnowledgeQAContext = createContext<KnowledgeQAContextValue | null>(null)

// Parse citation indices from generated answer [1], [2], etc.
function parseCitations(answer: string, results: RagResult[]): CitationRef[] {
  const citationMatches = answer.match(/\[(\d+)\]/g) || []
  const indices = citationMatches
    .map((m) => parseInt(m.replace(/[\[\]]/g, ""), 10))
    .filter((i) => i >= 1 && i <= results.length)

  const uniqueIndices = [...new Set(indices)]
  return uniqueIndices.map((index) => ({
    index,
    documentId: results[index - 1]?.id || `doc_${index}`,
    excerpt: results[index - 1]?.content || results[index - 1]?.text,
  }))
}

// Provider component
export function KnowledgeQAProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [storedPreset] = useStorage<RagPresetName>("ragSearchPreset", "balanced")
  const [storedSettings] = useStorage<RagSettings>(
    "ragSearchSettingsV2",
    DEFAULT_RAG_SETTINGS
  )
  const hydratedDefaultsRef = useRef<string | null>(null)
  const message = useAntdMessage()
  const defaultCharacterIdRef = useRef<number | null>(null)
  const defaultCharacterPromiseRef = useRef<Promise<number | null> | null>(null)

  // Initialize client
  useEffect(() => {
    tldwClient.initialize().catch(console.error)
  }, [])

  useEffect(() => {
    if (state.currentThreadId || state.messages.length > 0) {
      hydratedDefaultsRef.current = null
      return
    }

    const normalizedSettings: RagSettings = {
      ...DEFAULT_RAG_SETTINGS,
      ...(storedSettings || {}),
      ...KNOWLEDGE_QA_SETTINGS_OVERRIDES,
      enable_web_fallback:
        typeof storedSettings?.enable_web_fallback === "boolean"
          ? storedSettings.enable_web_fallback
          : true,
    }
    const serialized = JSON.stringify({
      preset: storedPreset,
      settings: normalizedSettings,
    })
    if (serialized === hydratedDefaultsRef.current) {
      return
    }
    hydratedDefaultsRef.current = serialized

    dispatch({
      type: "HYDRATE_DEFAULTS",
      payload: {
        preset: storedPreset,
        settings: normalizedSettings,
      },
    })
  }, [
    state.currentThreadId,
    state.messages.length,
    storedPreset,
    storedSettings,
  ])

  const resolveDefaultCharacterId = useCallback(async (): Promise<number | null> => {
    if (defaultCharacterIdRef.current != null) {
      return defaultCharacterIdRef.current
    }
    if (defaultCharacterPromiseRef.current) {
      return await defaultCharacterPromiseRef.current
    }

    const resolver = (async () => {
      try {
        await tldwClient.initialize()
        const searchResults = await tldwClient
          .searchCharacters(DEFAULT_CHARACTER_NAME, { limit: 5 })
          .catch(() => [])
        const match =
          searchResults.find(
            (c: any) =>
              typeof c?.name === "string" &&
              c.name.toLowerCase() === DEFAULT_CHARACTER_NAME.toLowerCase()
          ) || searchResults[0]
        if (match && typeof match.id === "number") {
          defaultCharacterIdRef.current = match.id
          return match.id
        }

        const listResults = await tldwClient.listCharacters({ limit: 10 }).catch(() => [])
        const fallback =
          listResults.find(
            (c: any) =>
              typeof c?.name === "string" &&
              c.name.toLowerCase() === DEFAULT_CHARACTER_NAME.toLowerCase()
          ) || listResults[0]
        if (fallback && typeof fallback.id === "number") {
          defaultCharacterIdRef.current = fallback.id
          return fallback.id
        }
      } catch (error) {
        console.warn("Failed to resolve default character:", error)
      }
      return null
    })()

    defaultCharacterPromiseRef.current = resolver
    try {
      return await resolver
    } finally {
      defaultCharacterPromiseRef.current = null
    }
  }, [])

  const tagConversationKeyword = useCallback(
    async (conversationId: string, version?: number | null): Promise<void> => {
      if (!conversationId || version == null) return
      try {
        const conversationResponse = await tldwClient.fetchWithAuth(
          `/api/v1/chat/conversations/${conversationId}`
        )
        const conversationData = await conversationResponse.json()
        const currentKeywords = Array.isArray(conversationData?.keywords)
          ? conversationData.keywords
          : Array.isArray(conversationData?.conversation?.keywords)
            ? conversationData.conversation.keywords
            : []
        const mergedKeywords: string[] = []
        const seenKeywords = new Set<string>()
        for (const keyword of [...currentKeywords, KNOWLEDGE_QA_KEYWORD]) {
          const normalized = String(keyword ?? "").trim()
          if (!normalized) continue
          const normalizedKey = normalized.toLowerCase()
          if (seenKeywords.has(normalizedKey)) continue
          seenKeywords.add(normalizedKey)
          mergedKeywords.push(normalized)
        }

        await tldwClient.fetchWithAuth(`/api/v1/chat/conversations/${conversationId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            version,
            keywords: mergedKeywords,
          }),
        })
      } catch (error) {
        console.warn("Failed to tag Knowledge QA conversation:", error)
      }
    },
    []
  )

  // Actions
  const setQuery = useCallback((query: string) => {
    dispatch({ type: "SET_QUERY", payload: query })
  }, [])

  const createNewThread = useCallback(async (title?: string): Promise<string> => {
    try {
      const characterId = await resolveDefaultCharacterId()
      if (!characterId) {
        throw new Error("Default character unavailable")
      }

      const resolvedTitle = title?.trim()
        ? title.trim()
        : `Knowledge QA - ${new Date().toLocaleDateString()}`

      // Create a new conversation via API
      const response = await tldwClient.createChat({
        character_id: characterId,
        title: resolvedTitle,
        state: "in-progress",
        source: "knowledge_qa",
      })

      const threadId = response?.id
      if (!threadId) {
        throw new Error("Chat creation returned no ID")
      }

      const version =
        typeof response?.version === "number" ? response.version : null
      if (version != null) {
        await tagConversationKeyword(String(threadId), version)
      } else {
        try {
          const current = await tldwClient.getChat(String(threadId))
          const currentVersion =
            typeof current?.version === "number" ? current.version : null
          if (currentVersion != null) {
            await tagConversationKeyword(String(threadId), currentVersion)
          }
        } catch (error) {
          console.warn("Failed to fetch conversation version for tagging:", error)
        }
      }
      const normalizedState: "in-progress" | "resolved" =
        response?.state === "resolved" ? "resolved" : "in-progress"
      const newThread: KnowledgeQAThread = {
        id: threadId,
        title: response?.title || resolvedTitle || "New Knowledge QA Thread",
        createdAt: new Date().toISOString(),
        lastModifiedAt: new Date().toISOString(),
        state: normalizedState,
        messageCount: 0,
        source: "knowledge_qa",
      }

      dispatch({ type: "ADD_THREAD", payload: newThread })
      dispatch({ type: "SET_THREAD_ID", payload: threadId })
      dispatch({ type: "SET_MESSAGES", payload: [] })

      return threadId
    } catch (error) {
      console.error("Failed to create thread:", error)
      // Return a local ID as fallback
      const localId = `${LOCAL_THREAD_PREFIX}${crypto.randomUUID()}`
      dispatch({ type: "SET_THREAD_ID", payload: localId })
      dispatch({ type: "SET_MESSAGES", payload: [] })
      return localId
    }
  }, [resolveDefaultCharacterId, tagConversationKeyword])

  const persistChatMessage = useCallback(
    async (
      threadId: string,
      role: "user" | "assistant" | "system",
      content: string,
      parentMessageId?: string | null
    ): Promise<{ id: string; timestamp?: string } | null> => {
      if (!threadId || isLocalThreadId(threadId)) return null
      try {
        const payload: Record<string, any> = { role, content }
        if (parentMessageId) {
          payload.parent_message_id = parentMessageId
        }
        const response = await tldwClient.addChatMessage(threadId, payload)
        const id = response?.id != null ? String(response.id) : null
        if (!id) return null
        return {
          id,
          timestamp: response?.created_at ? String(response.created_at) : undefined,
        }
      } catch (error) {
        console.warn("Failed to persist chat message:", error)
        return null
      }
    },
    []
  )

  const persistRagContext = useCallback(
    async (messageId: string, context: RagContextData): Promise<boolean> => {
      try {
        const response = await tldwClient.fetchWithAuth(
          `/api/v1/chat/messages/${messageId}/rag-context`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              message_id: messageId,
              rag_context: context,
            }),
          }
        )
        if (!response.ok) {
          let errorDetails: string | unknown = ""
          try {
            errorDetails = await response.text()
          } catch (textError) {
            errorDetails = textError
          }
          console.error("Failed to persist RAG context:", {
            status: response.status,
            error: errorDetails,
          })
          return false
        }
        const result = await response.json()
        return result?.success ?? false
      } catch (error) {
        console.error("Failed to persist RAG context:", error)
        return false
      }
    },
    []
  )

  const buildRagContext = useCallback(
    (question: string, results: RagResult[], answer: string | null): RagContextData => ({
      search_query: question,
      search_mode: state.settings.search_mode,
      settings_snapshot: {
        top_k: state.settings.top_k,
        enable_reranking: state.settings.enable_reranking,
        enable_citations: state.settings.enable_citations,
        enable_web_fallback: state.settings.enable_web_fallback,
        web_fallback_threshold: state.settings.web_fallback_threshold,
        web_search_engine: state.settings.web_search_engine,
        web_fallback_result_count: state.settings.web_fallback_result_count,
        web_fallback_merge_strategy: state.settings.web_fallback_merge_strategy,
      },
      retrieved_documents: results.map((r) => ({
        id: r.id,
        source_type: r.metadata?.source_type,
        title: r.metadata?.title,
        score: r.score,
        chunk_id: r.metadata?.chunk_id,
        excerpt: r.content || r.text || r.chunk,
        url: r.metadata?.url,
        page_number: r.metadata?.page_number,
      })),
      generated_answer: answer || undefined,
      timestamp: new Date().toISOString(),
    }),
    [state.settings]
  )

  const runKnowledgeQuery = useCallback(
    async (question: string, addToHistory: boolean) => {
      const trimmedQuery = question.trim()
      if (!trimmedQuery) return

      dispatch({ type: "SET_SEARCHING", payload: true })

      let threadId = state.currentThreadId
      if (!threadId) {
        threadId = await createNewThread(trimmedQuery)
      }

      const userTimestamp = new Date().toISOString()
      const persistedUser = threadId
        ? await persistChatMessage(threadId, "user", trimmedQuery, null)
        : null
      const userMessageId = persistedUser?.id || crypto.randomUUID()

      if (threadId) {
        const userMessage: KnowledgeQAMessage = {
          id: userMessageId,
          conversationId: threadId,
          role: "user",
          content: trimmedQuery,
          timestamp: persistedUser?.timestamp || userTimestamp,
        }
        dispatch({ type: "ADD_MESSAGE", payload: userMessage })
      }

      try {
        const { options } = buildRagSearchRequest({
          ...state.settings,
          query: trimmedQuery,
          enable_web_fallback: state.settings.enable_web_fallback,
        })

        const response = await tldwClient.ragSearch(trimmedQuery, options)

        // Extract results from various response formats
        const results: RagResult[] =
          response?.results || response?.documents || response?.docs || []

        // Extract generated answer
        const answer =
          response?.generated_answer || response?.answer || response?.response || null

        // Parse citations from answer
        const citations = answer ? parseCitations(answer, results) : []

        dispatch({
          type: "SET_RESULTS",
          payload: { results, answer, citations },
        })

        let assistantMessageId: string | null = null
        const ragContext = buildRagContext(trimmedQuery, results, answer)

        if (answer && threadId) {
          const persistedAssistant = await persistChatMessage(
            threadId,
            "assistant",
            answer,
            persistedUser?.id
          )
          assistantMessageId = persistedAssistant?.id || crypto.randomUUID()
          const assistantMessage: KnowledgeQAMessage = {
            id: assistantMessageId,
            conversationId: threadId,
            role: "assistant",
            content: answer,
            timestamp: persistedAssistant?.timestamp || new Date().toISOString(),
            ragContext,
          }
          dispatch({ type: "ADD_MESSAGE", payload: assistantMessage })

          if (persistedAssistant?.id) {
            await persistRagContext(persistedAssistant.id, ragContext)
          }
        }

        if (addToHistory) {
          const historyItem: SearchHistoryItem = {
            id: crypto.randomUUID(),
            query: trimmedQuery,
            timestamp: new Date().toISOString(),
            sourcesCount: results.length,
            hasAnswer: !!answer,
            preset: state.preset,
            conversationId: threadId && !isLocalThreadId(threadId) ? threadId : undefined,
            messageId: assistantMessageId || undefined,
            keywords: [KNOWLEDGE_QA_KEYWORD],
          }
          dispatch({ type: "ADD_HISTORY_ITEM", payload: historyItem })
        }
      } catch (error) {
        console.error("Search failed:", error)
        dispatch({
          type: "SET_ERROR",
          payload: error instanceof Error ? error.message : "Search failed",
        })
      }
    },
    [
      state.currentThreadId,
      state.settings,
      state.preset,
      createNewThread,
      persistChatMessage,
      persistRagContext,
      buildRagContext,
    ]
  )

  const search = useCallback(async () => {
    await runKnowledgeQuery(state.query, true)
  }, [state.query, runKnowledgeQuery])

  const clearResults = useCallback(() => {
    dispatch({ type: "CLEAR_RESULTS" })
    dispatch({ type: "SET_THREAD_ID", payload: null })
    dispatch({ type: "SET_MESSAGES", payload: [] })
  }, [])

  const selectThread = useCallback(async (threadId: string) => {
    dispatch({ type: "SET_THREAD_ID", payload: threadId })

    if (isLocalThreadId(threadId)) {
      dispatch({ type: "SET_MESSAGES", payload: [] })
      return
    }

    try {
      // Load messages with RAG context
      const response = await tldwClient.fetchWithAuth(
        `/api/v1/chat/conversations/${threadId}/messages-with-context?include_rag_context=true`
      )
      const messages = (await response.json()) as KnowledgeQAMessage[]
      dispatch({ type: "SET_MESSAGES", payload: messages })
    } catch (error) {
      console.error("Failed to load thread messages:", error)
      dispatch({ type: "SET_MESSAGES", payload: [] })
    }
  }, [])

  const askFollowUp = useCallback(
    async (question: string) => {
      await runKnowledgeQuery(question, false)
    },
    [runKnowledgeQuery]
  )

  const setPreset = useCallback((preset: RagPresetName) => {
    dispatch({ type: "SET_PRESET", payload: preset })
  }, [])

  const updateSetting = useCallback(<K extends keyof RagSettings>(key: K, value: RagSettings[K]) => {
    dispatch({ type: "UPDATE_SETTING", payload: { key, value } })
  }, [])

  const resetSettings = useCallback(() => {
    dispatch({ type: "SET_SETTINGS", payload: { ...DEFAULT_RAG_SETTINGS, ...KNOWLEDGE_QA_SETTINGS_OVERRIDES } })
    dispatch({ type: "SET_PRESET", payload: "balanced" })
  }, [])

  const toggleExpertMode = useCallback(() => {
    dispatch({ type: "TOGGLE_EXPERT_MODE" })
  }, [])

  const loadSearchHistory = useCallback(async () => {
    // Load from local storage for now
    try {
      const stored = localStorage.getItem("knowledge_qa_history")
      if (stored) {
        const history = JSON.parse(stored) as SearchHistoryItem[]
        dispatch({ type: "SET_SEARCH_HISTORY", payload: history })
      }
      // Best-effort: merge server conversation history for cross-session continuity
      try {
        const response = await tldwClient.fetchWithAuth(
          `/api/v1/chat/conversations?order_by=recency&limit=50&keywords=${encodeURIComponent(
            KNOWLEDGE_QA_KEYWORD
          )}`
        )
        if (response.ok) {
          const data = await response.json()
          const items: any[] = Array.isArray(data)
            ? data
            : data?.items || data?.conversations || data?.chats || data?.results || []
          const serverHistory: SearchHistoryItem[] = items
            .map((conv) => {
              const id =
                conv?.id ||
                conv?.conversation_id ||
                conv?.chat_id ||
                conv?.chatId
              if (!id) return null
              const keywords = Array.isArray(conv?.keywords) ? conv.keywords : []
              const hasKeyword = keywords.some(
                (kw: string) => String(kw).toLowerCase() === KNOWLEDGE_QA_KEYWORD.toLowerCase()
              )
              if (!hasKeyword) return null
              const title = typeof conv?.title === "string" ? conv.title : "Knowledge QA"
              const lastModified =
                conv?.last_modified ||
                conv?.lastModified ||
                conv?.last_modified_at ||
                conv?.lastModifiedAt ||
                conv?.created_at ||
                conv?.createdAt ||
                new Date().toISOString()
              const messageCount =
                typeof conv?.message_count === "number"
                  ? conv.message_count
                  : typeof conv?.messageCount === "number"
                    ? conv.messageCount
                    : 0
              return {
                id: String(id),
                query: title,
                timestamp: new Date(lastModified).toISOString(),
                sourcesCount: messageCount,
                hasAnswer: messageCount >= 2,
                conversationId: String(id),
                keywords,
              } as SearchHistoryItem
            })
            .filter(Boolean) as SearchHistoryItem[]

          if (serverHistory.length > 0) {
            const storedItems: SearchHistoryItem[] = stored
              ? (JSON.parse(stored) as SearchHistoryItem[])
              : []
            const mergedMap = new Map<string, SearchHistoryItem>()
            for (const item of storedItems) {
              const itemKeywords = Array.isArray(item.keywords) ? item.keywords : []
              const hasKeyword = itemKeywords.some(
                (kw) => String(kw).toLowerCase() === KNOWLEDGE_QA_KEYWORD.toLowerCase()
              )
              if (!hasKeyword) continue
              const key = item.conversationId
                ? `conv:${item.conversationId}`
                : `query:${item.query}`
              mergedMap.set(key, item)
            }
            for (const item of serverHistory) {
              const key = item.conversationId
                ? `conv:${item.conversationId}`
                : `query:${item.query}`
              if (!mergedMap.has(key)) {
                mergedMap.set(key, item)
              }
            }
            const merged = Array.from(mergedMap.values()).sort(
              (a, b) =>
                new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
            )
            dispatch({ type: "SET_SEARCH_HISTORY", payload: merged })
          }
        }
      } catch {
        // ignore server history fetch failures
      }
    } catch (error) {
      console.error("Failed to load search history:", error)
    }
  }, [])

  const restoreFromHistory = useCallback(
    async (item: SearchHistoryItem) => {
      dispatch({ type: "SET_QUERY", payload: item.query })
      if (item.preset) {
        dispatch({ type: "SET_PRESET", payload: item.preset })
      }
      if (item.conversationId) {
        await selectThread(item.conversationId)
      }
    },
    [selectThread]
  )

  const deleteHistoryItem = useCallback(
    async (id: string) => {
      const item = state.searchHistory.find((h) => h.id === id)
      const conversationId = item?.conversationId

      const toastKey = `knowledge-qa-delete-${id}`
      const attemptServerDelete = async () => {
        try {
          await tldwClient.deleteChat(conversationId as string)
          message.open({
            key: toastKey,
            type: "success",
            content: "Deleted from server history.",
            duration: 2.5,
          })
          return true
        } catch (error) {
          console.warn("Failed to delete Knowledge QA conversation:", error)
          message.open({
            key: toastKey,
            type: "error",
            duration: 4,
            content: (
              <span className="inline-flex items-center gap-2">
                <span>Failed to delete server history.</span>
                <button
                  className="text-primary underline"
                  onClick={() => {
                    attemptServerDelete().catch(() => undefined)
                  }}
                >
                  Retry
                </button>
              </span>
            ),
            className: "max-w-sm",
          })
          return false
        }
      }

      if (conversationId && !isLocalThreadId(conversationId)) {
        const ok = await attemptServerDelete()
        if (!ok) {
          return
        }
      } else {
        message.open({
          key: toastKey,
          type: "success",
          content: "Removed from local history.",
          duration: 2,
        })
      }

      dispatch({ type: "REMOVE_HISTORY_ITEM", payload: id })
      // Also remove from local storage
      try {
        const stored = localStorage.getItem("knowledge_qa_history")
        if (stored) {
          const history = JSON.parse(stored) as SearchHistoryItem[]
          const updated = history.filter((h) => h.id !== id)
          localStorage.setItem("knowledge_qa_history", JSON.stringify(updated))
        }
      } catch (error) {
        console.error("Failed to delete history item:", error)
      }
    },
    [message, state.searchHistory]
  )

  const setSettingsPanelOpen = useCallback((open: boolean) => {
    dispatch({ type: "SET_SETTINGS_PANEL_OPEN", payload: open })
  }, [])

  const setHistorySidebarOpen = useCallback((open: boolean) => {
    dispatch({ type: "SET_HISTORY_SIDEBAR_OPEN", payload: open })
  }, [])

  const focusSource = useCallback((index: number | null) => {
    dispatch({ type: "SET_FOCUSED_SOURCE", payload: index })
  }, [])

  const scrollToSource = useCallback((index: number) => {
    const element = document.getElementById(`source-card-${index}`)
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "center" })
      dispatch({ type: "SET_FOCUSED_SOURCE", payload: index })
    }
  }, [])

  // Save history to local storage when it changes
  useEffect(() => {
    if (state.searchHistory.length > 0) {
      localStorage.setItem("knowledge_qa_history", JSON.stringify(state.searchHistory))
    }
  }, [state.searchHistory])

  // Load history on mount
  useEffect(() => {
    loadSearchHistory()
  }, [loadSearchHistory])

  // Memoized context value
  const contextValue = useMemo<KnowledgeQAContextValue>(
    () => ({
      ...state,
      setQuery,
      search,
      clearResults,
      createNewThread,
      selectThread,
      askFollowUp,
      setPreset,
      updateSetting,
      resetSettings,
      toggleExpertMode,
      loadSearchHistory,
      restoreFromHistory,
      deleteHistoryItem,
      setSettingsPanelOpen,
      setHistorySidebarOpen,
      focusSource,
      persistRagContext,
      scrollToSource,
    }),
    [
      state,
      setQuery,
      search,
      clearResults,
      createNewThread,
      selectThread,
      askFollowUp,
      setPreset,
      updateSetting,
      resetSettings,
      toggleExpertMode,
      loadSearchHistory,
      restoreFromHistory,
      deleteHistoryItem,
      setSettingsPanelOpen,
      setHistorySidebarOpen,
      focusSource,
      persistRagContext,
      scrollToSource,
    ]
  )

  return (
    <KnowledgeQAContext.Provider value={contextValue}>
      {children}
    </KnowledgeQAContext.Provider>
  )
}

// Hook to use the context
export function useKnowledgeQA(): KnowledgeQAContextValue {
  const context = useContext(KnowledgeQAContext)
  if (!context) {
    throw new Error("useKnowledgeQA must be used within a KnowledgeQAProvider")
  }
  return context
}
