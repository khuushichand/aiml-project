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
  type ReactNode,
} from "react"
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
  settings: DEFAULT_RAG_SETTINGS,
  expertMode: false,

  searchHistory: [],
  historySidebarOpen: true,

  settingsPanelOpen: false,
  focusedSourceIndex: null,
}

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
    case "SET_PRESET":
      return {
        ...state,
        preset: action.payload,
        settings: action.payload === "custom" ? state.settings : applyRagPreset(action.payload as Exclude<RagPresetName, "custom">),
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

  // Initialize client
  useEffect(() => {
    tldwClient.initialize().catch(console.error)
  }, [])

  // Actions
  const setQuery = useCallback((query: string) => {
    dispatch({ type: "SET_QUERY", payload: query })
  }, [])

  const search = useCallback(async () => {
    const trimmedQuery = state.query.trim()
    if (!trimmedQuery) return

    dispatch({ type: "SET_SEARCHING", payload: true })

    try {
      const { options } = buildRagSearchRequest({
        ...state.settings,
        query: trimmedQuery,
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

      // Add to search history
      const historyItem: SearchHistoryItem = {
        id: crypto.randomUUID(),
        query: trimmedQuery,
        timestamp: new Date().toISOString(),
        sourcesCount: results.length,
        hasAnswer: !!answer,
        preset: state.preset,
      }
      dispatch({ type: "ADD_HISTORY_ITEM", payload: historyItem })
    } catch (error) {
      console.error("Search failed:", error)
      dispatch({
        type: "SET_ERROR",
        payload: error instanceof Error ? error.message : "Search failed",
      })
    }
  }, [state.query, state.settings, state.preset])

  const clearResults = useCallback(() => {
    dispatch({ type: "CLEAR_RESULTS" })
  }, [])

  const createNewThread = useCallback(async (): Promise<string> => {
    try {
      // Create a new conversation via API
      const response = await tldwClient.createChat({
        title: `Knowledge QA - ${new Date().toLocaleDateString()}`,
        source: "knowledge_qa",
      })

      const threadId = response?.id || crypto.randomUUID()
      const newThread: KnowledgeQAThread = {
        id: threadId,
        title: response?.title || "New Knowledge QA Thread",
        createdAt: new Date().toISOString(),
        lastModifiedAt: new Date().toISOString(),
        state: "in-progress",
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
      const localId = crypto.randomUUID()
      dispatch({ type: "SET_THREAD_ID", payload: localId })
      dispatch({ type: "SET_MESSAGES", payload: [] })
      return localId
    }
  }, [])

  const selectThread = useCallback(async (threadId: string) => {
    dispatch({ type: "SET_THREAD_ID", payload: threadId })

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
      if (!question.trim()) return

      // Ensure we have a thread
      let threadId = state.currentThreadId
      if (!threadId) {
        threadId = await createNewThread()
      }

      // Add user message
      const userMessage: KnowledgeQAMessage = {
        id: crypto.randomUUID(),
        conversationId: threadId,
        role: "user",
        content: question,
        timestamp: new Date().toISOString(),
      }
      dispatch({ type: "ADD_MESSAGE", payload: userMessage })

      dispatch({ type: "SET_SEARCHING", payload: true })

      try {
        // Search for context
        const { options } = buildRagSearchRequest({
          ...state.settings,
          query: question,
        })

        const response = await tldwClient.ragSearch(question, options)
        const results: RagResult[] =
          response?.results || response?.documents || response?.docs || []
        const answer =
          response?.generated_answer || response?.answer || response?.response || null
        const citations = answer ? parseCitations(answer, results) : []

        dispatch({
          type: "SET_RESULTS",
          payload: { results, answer, citations },
        })

        // Add assistant message with RAG context
        if (answer) {
          const assistantMessage: KnowledgeQAMessage = {
            id: crypto.randomUUID(),
            conversationId: threadId,
            role: "assistant",
            content: answer,
            timestamp: new Date().toISOString(),
            ragContext: {
              search_query: question,
              search_mode: state.settings.search_mode,
              settings_snapshot: {
                top_k: state.settings.top_k,
                enable_reranking: state.settings.enable_reranking,
                enable_citations: state.settings.enable_citations,
              },
              retrieved_documents: results.map((r) => ({
                id: r.id,
                source_type: r.metadata?.source_type,
                title: r.metadata?.title,
                score: r.score,
                excerpt: r.content || r.text || r.chunk,
                url: r.metadata?.url,
              })),
              generated_answer: answer,
              timestamp: new Date().toISOString(),
            },
          }
          dispatch({ type: "ADD_MESSAGE", payload: assistantMessage })
        }
      } catch (error) {
        console.error("Follow-up failed:", error)
        dispatch({
          type: "SET_ERROR",
          payload: error instanceof Error ? error.message : "Follow-up failed",
        })
      }
    },
    [state.currentThreadId, state.settings, createNewThread]
  )

  const setPreset = useCallback((preset: RagPresetName) => {
    dispatch({ type: "SET_PRESET", payload: preset })
  }, [])

  const updateSetting = useCallback(<K extends keyof RagSettings>(key: K, value: RagSettings[K]) => {
    dispatch({ type: "UPDATE_SETTING", payload: { key, value } })
  }, [])

  const resetSettings = useCallback(() => {
    dispatch({ type: "SET_SETTINGS", payload: DEFAULT_RAG_SETTINGS })
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

  const deleteHistoryItem = useCallback(async (id: string) => {
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
  }, [])

  const setSettingsPanelOpen = useCallback((open: boolean) => {
    dispatch({ type: "SET_SETTINGS_PANEL_OPEN", payload: open })
  }, [])

  const setHistorySidebarOpen = useCallback((open: boolean) => {
    dispatch({ type: "SET_HISTORY_SIDEBAR_OPEN", payload: open })
  }, [])

  const focusSource = useCallback((index: number | null) => {
    dispatch({ type: "SET_FOCUSED_SOURCE", payload: index })
  }, [])

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
        const result = await response.json()
        return result?.success ?? false
      } catch (error) {
        console.error("Failed to persist RAG context:", error)
        return false
      }
    },
    []
  )

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
