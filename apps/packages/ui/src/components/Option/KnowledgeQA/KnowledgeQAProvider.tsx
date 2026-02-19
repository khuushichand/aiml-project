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
  SearchRuntimeDetails,
  QueryStage,
  ScopeSnapshot,
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
import { trackKnowledgeQaSearchMetric } from "@/utils/knowledge-qa-search-metrics"
import { persistKnowledgeQaHistory } from "./historyStorage"
import { mapKnowledgeQaSearchErrorMessage } from "./errorMessages"
import { truncateAnswerPreview } from "./historyUtils"

const LOCAL_THREAD_PREFIX = "local-"
const DEFAULT_CHARACTER_NAME = "Helpful AI Assistant"
type CreateThreadOptions = {
  parentConversationId?: string
  forkedFromMessageId?: string
}
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
  hasSearched: false,
  results: [],
  answer: null,
  citations: [],
  searchDetails: null,
  error: null,

  currentThreadId: null,
  isLocalOnlyThread: false,
  messages: [],
  threads: [],

  preset: "balanced",
  settings: { ...DEFAULT_RAG_SETTINGS, ...KNOWLEDGE_QA_SETTINGS_OVERRIDES },
  expertMode: false,

  searchHistory: [],
  historySidebarOpen: true,

  settingsPanelOpen: false,
  focusedSourceIndex: null,
  evidenceRailOpen: false,
  evidenceRailTab: "sources",
  queryStage: "idle",
  lastSearchScope: null,
}

const isLocalThreadId = (id: string | null | undefined) =>
  Boolean(id && id.startsWith(LOCAL_THREAD_PREFIX))

function sliceMessagesForBranch(
  messages: KnowledgeQAMessage[],
  fromUserMessageId: string
): KnowledgeQAMessage[] {
  if (!fromUserMessageId) return []
  const userIndex = messages.findIndex(
    (message) => message.id === fromUserMessageId && message.role === "user"
  )
  if (userIndex < 0) return []

  let branchEndExclusive = messages.length
  for (let index = userIndex + 1; index < messages.length; index += 1) {
    if (messages[index].role === "user") {
      branchEndExclusive = index
      break
    }
  }

  return messages.slice(0, branchEndExclusive)
}

// Action types
type Action =
  | { type: "SET_QUERY"; payload: string }
  | { type: "SET_SEARCHING"; payload: boolean }
  | { type: "SET_RESULTS"; payload: { results: RagResult[]; answer: string | null; citations: CitationRef[] } }
  | { type: "SET_PARTIAL_RESULTS"; payload: { results: RagResult[]; answer: string | null; citations: CitationRef[] } }
  | { type: "SET_SEARCH_DETAILS"; payload: SearchRuntimeDetails | null }
  | { type: "SET_ERROR"; payload: string | null }
  | { type: "CLEAR_RESULTS" }
  | { type: "SET_THREAD_ID"; payload: string | null }
  | { type: "SET_LOCAL_ONLY_THREAD"; payload: boolean }
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
  | { type: "UPDATE_HISTORY_ITEM"; payload: { id: string; patch: Partial<SearchHistoryItem> } }
  | { type: "REMOVE_HISTORY_ITEM"; payload: string }
  | { type: "TOGGLE_HISTORY_PIN"; payload: string }
  | { type: "SET_SETTINGS_PANEL_OPEN"; payload: boolean }
  | { type: "SET_HISTORY_SIDEBAR_OPEN"; payload: boolean }
  | { type: "SET_FOCUSED_SOURCE"; payload: number | null }
  | { type: "SET_EVIDENCE_RAIL_OPEN"; payload: boolean }
  | { type: "SET_EVIDENCE_RAIL_TAB"; payload: "sources" | "details" }
  | { type: "SET_QUERY_STAGE"; payload: QueryStage }
  | { type: "SET_LAST_SEARCH_SCOPE"; payload: ScopeSnapshot | null }

// Reducer
function reducer(state: KnowledgeQAState, action: Action): KnowledgeQAState {
  switch (action.type) {
    case "SET_QUERY":
      return { ...state, query: action.payload }
    case "SET_SEARCHING":
      return {
        ...state,
        isSearching: action.payload,
        error: action.payload ? null : state.error,
      }
    case "SET_RESULTS":
      return {
        ...state,
        results: action.payload.results,
        answer: action.payload.answer,
        citations: action.payload.citations,
        hasSearched: true,
        isSearching: false,
        queryStage: "complete",
      }
    case "SET_PARTIAL_RESULTS":
      return {
        ...state,
        results: action.payload.results,
        answer: action.payload.answer,
        citations: action.payload.citations,
        hasSearched: true,
        isSearching: true,
      }
    case "SET_SEARCH_DETAILS":
      return { ...state, searchDetails: action.payload }
    case "SET_ERROR":
      return {
        ...state,
        error: action.payload,
        hasSearched: true,
        isSearching: false,
        queryStage: action.payload ? "error" : "idle",
      }
    case "CLEAR_RESULTS":
      return {
        ...state,
        results: [],
        answer: null,
        citations: [],
        searchDetails: null,
        error: null,
        hasSearched: false,
        queryStage: "idle",
      }
    case "SET_THREAD_ID":
      return { ...state, currentThreadId: action.payload }
    case "SET_LOCAL_ONLY_THREAD":
      return { ...state, isLocalOnlyThread: action.payload }
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
    case "UPDATE_HISTORY_ITEM":
      return {
        ...state,
        searchHistory: state.searchHistory.map((item) =>
          item.id === action.payload.id
            ? { ...item, ...action.payload.patch }
            : item
        ),
      }
    case "REMOVE_HISTORY_ITEM":
      return { ...state, searchHistory: state.searchHistory.filter((h) => h.id !== action.payload) }
    case "TOGGLE_HISTORY_PIN":
      return {
        ...state,
        searchHistory: state.searchHistory.map((item) =>
          item.id === action.payload
            ? { ...item, pinned: !item.pinned }
            : item
        ),
      }
    case "SET_SETTINGS_PANEL_OPEN":
      return { ...state, settingsPanelOpen: action.payload }
    case "SET_HISTORY_SIDEBAR_OPEN":
      return { ...state, historySidebarOpen: action.payload }
    case "SET_FOCUSED_SOURCE":
      return { ...state, focusedSourceIndex: action.payload }
    case "SET_EVIDENCE_RAIL_OPEN":
      return { ...state, evidenceRailOpen: action.payload }
    case "SET_EVIDENCE_RAIL_TAB":
      return { ...state, evidenceRailTab: action.payload }
    case "SET_QUERY_STAGE":
      return { ...state, queryStage: action.payload }
    case "SET_LAST_SEARCH_SCOPE":
      return { ...state, lastSearchScope: action.payload }
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

function normalizeMessageRole(role: unknown): KnowledgeQAMessage["role"] {
  const normalized = String(role ?? "").toLowerCase()
  if (normalized === "assistant" || normalized === "user" || normalized === "system") {
    return normalized
  }
  return "system"
}

function normalizeMessagesWithContext(
  payload: unknown,
  threadId: string
): KnowledgeQAMessage[] {
  if (!Array.isArray(payload)) return []

  return payload
    .map((entry, index) => {
      if (!entry || typeof entry !== "object") return null
      const candidate = entry as Record<string, unknown>
      const idRaw = candidate.id
      const id =
        typeof idRaw === "string" && idRaw.length > 0
          ? idRaw
          : `thread-message-${index + 1}`
      const content =
        typeof candidate.content === "string"
          ? candidate.content
          : String(candidate.content ?? "")
      const timestampCandidate = [
        candidate.timestamp,
        candidate.created_at,
        candidate.createdAt,
        candidate.updated_at,
      ].find((value) => typeof value === "string" && value.length > 0)
      const ragContextRaw = candidate.ragContext ?? candidate.rag_context

      return {
        id,
        conversationId: threadId,
        role: normalizeMessageRole(candidate.role),
        content,
        timestamp:
          typeof timestampCandidate === "string"
            ? timestampCandidate
            : new Date().toISOString(),
        ragContext:
          ragContextRaw && typeof ragContextRaw === "object"
            ? (ragContextRaw as RagContextData)
            : undefined,
      } as KnowledgeQAMessage
    })
    .filter((message): message is KnowledgeQAMessage => message != null)
}

function mapRagContextDocumentsToResults(
  retrievedDocuments: unknown
): RagResult[] {
  if (!Array.isArray(retrievedDocuments)) return []

  return retrievedDocuments.map((document, index) => {
    const doc = document as Record<string, unknown>
    return {
      id:
        typeof doc?.id === "string" && doc.id.length > 0
          ? doc.id
          : `doc-${index + 1}`,
      score: typeof doc?.score === "number" ? doc.score : undefined,
      content:
        typeof doc?.excerpt === "string"
          ? doc.excerpt
          : typeof doc?.content === "string"
            ? doc.content
            : undefined,
      text:
        typeof doc?.excerpt === "string"
          ? doc.excerpt
          : typeof doc?.text === "string"
            ? doc.text
            : undefined,
      metadata: {
        title:
          typeof doc?.title === "string" ? doc.title : `Source ${index + 1}`,
        source:
          typeof doc?.source === "string"
            ? doc.source
            : typeof doc?.source_type === "string"
              ? doc.source_type
              : undefined,
        source_type:
          typeof doc?.source_type === "string" ? doc.source_type : undefined,
        chunk_id: typeof doc?.chunk_id === "string" ? doc.chunk_id : undefined,
        url: typeof doc?.url === "string" ? doc.url : undefined,
        page_number:
          typeof doc?.page_number === "number" ? doc.page_number : undefined,
        ...(doc?.metadata &&
        typeof doc.metadata === "object" &&
        !Array.isArray(doc.metadata)
          ? (doc.metadata as Record<string, unknown>)
          : {}),
      },
    } as RagResult
  })
}

function deriveThreadHydrationState(messages: KnowledgeQAMessage[]): {
  query: string | null
  answer: string | null
  results: RagResult[]
  citations: CitationRef[]
  answerPreview?: string
  sourcesCount: number
} | null {
  if (messages.length === 0) return null

  const latestUserMessage = [...messages]
    .reverse()
    .find((message) => message.role === "user")
  const assistantMessages = messages.filter((message) => message.role === "assistant")
  const latestAssistantWithContext = [...assistantMessages]
    .reverse()
    .find((message) => message.ragContext)
  const latestAssistantMessage =
    latestAssistantWithContext || assistantMessages[assistantMessages.length - 1]

  if (!latestAssistantMessage) {
    return {
      query: latestUserMessage?.content || null,
      answer: null,
      results: [],
      citations: [],
      sourcesCount: 0,
    }
  }

  const ragContext = latestAssistantMessage.ragContext
  const results = mapRagContextDocumentsToResults(ragContext?.retrieved_documents)
  const answerCandidate =
    typeof ragContext?.generated_answer === "string" &&
    ragContext.generated_answer.trim().length > 0
      ? ragContext.generated_answer
      : latestAssistantMessage.content

  const answer =
    typeof answerCandidate === "string" && answerCandidate.trim().length > 0
      ? answerCandidate
      : null
  const citations = answer ? parseCitations(answer, results) : []
  const queryFromContext =
    typeof ragContext?.search_query === "string" &&
    ragContext.search_query.trim().length > 0
      ? ragContext.search_query
      : null
  const query = latestUserMessage?.content || queryFromContext

  return {
    query,
    answer,
    results,
    citations,
    answerPreview: truncateAnswerPreview(answer),
    sourcesCount: results.length,
  }
}

function extractRagResponse(response: any): {
  results: RagResult[]
  answer: string | null
  expandedQueries: string[]
  metadata: Record<string, unknown>
} {
  const results: RagResult[] =
    response?.results || response?.documents || response?.docs || []
  const answer =
    response?.generated_answer || response?.answer || response?.response || null
  const expandedQueries = Array.isArray(response?.expanded_queries)
    ? response.expanded_queries.filter(
        (value: unknown): value is string =>
          typeof value === "string" && value.trim().length > 0
      )
    : []
  const metadata =
    response?.metadata && typeof response.metadata === "object"
      ? (response.metadata as Record<string, unknown>)
      : {}
  if (typeof response?.feedback_id === "string" && !metadata.feedback_id) {
    metadata.feedback_id = response.feedback_id
  }
  return { results, answer, expandedQueries, metadata }
}

function mapStreamingContextsToResults(contexts: any[]): RagResult[] {
  return contexts.map((context, index) => ({
    id:
      typeof context?.id === "string" && context.id.length > 0
        ? context.id
        : `stream-source-${index + 1}`,
    metadata: {
      title:
        typeof context?.title === "string" && context.title.length > 0
          ? context.title
          : `Source ${index + 1}`,
      source:
        typeof context?.source === "string" ? context.source : undefined,
      url: typeof context?.url === "string" ? context.url : undefined,
    },
    score: typeof context?.score === "number" ? context.score : undefined,
  }))
}

function calculateAverageRelevance(results: RagResult[]): number | null {
  const numericScores = results
    .map((result) => result.score)
    .filter((score): score is number => typeof score === "number")
  if (numericScores.length === 0) return null
  const sum = numericScores.reduce((acc, value) => acc + value, 0)
  return sum / numericScores.length
}

function normalizeMetric(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null
  return value
}

function extractTokenAndCostDetails(metadata: Record<string, unknown>): {
  tokensUsed: number | null
  estimatedCostUsd: number | null
} {
  const estimatedCostRaw = metadata?.estimated_cost
  const estimatedCostUsd =
    typeof estimatedCostRaw === "number"
      ? estimatedCostRaw
      : estimatedCostRaw &&
          typeof estimatedCostRaw === "object" &&
          typeof (estimatedCostRaw as Record<string, unknown>).total === "number"
        ? ((estimatedCostRaw as Record<string, unknown>).total as number)
        : null

  const tokenCandidates: unknown[] = [
    metadata?.tokens_used,
    metadata?.total_tokens,
    metadata?.token_count,
    metadata?.usage &&
    typeof metadata.usage === "object"
      ? (metadata.usage as Record<string, unknown>).total_tokens
      : undefined,
    estimatedCostRaw &&
    typeof estimatedCostRaw === "object"
      ? (estimatedCostRaw as Record<string, unknown>).input_tokens
      : undefined,
    estimatedCostRaw &&
    typeof estimatedCostRaw === "object"
      ? (estimatedCostRaw as Record<string, unknown>).output_tokens
      : undefined,
  ]

  const directTokenValue = tokenCandidates.find(
    (value) => typeof value === "number" && Number.isFinite(value)
  ) as number | undefined
  const estimatedCostTokens =
    estimatedCostRaw && typeof estimatedCostRaw === "object"
      ? (((estimatedCostRaw as Record<string, unknown>).input_tokens as number | undefined) ?? 0) +
        (((estimatedCostRaw as Record<string, unknown>).output_tokens as number | undefined) ?? 0)
      : null

  return {
    tokensUsed:
      typeof directTokenValue === "number"
        ? directTokenValue
        : typeof estimatedCostTokens === "number" && Number.isFinite(estimatedCostTokens) && estimatedCostTokens > 0
          ? estimatedCostTokens
          : null,
    estimatedCostUsd:
      typeof estimatedCostUsd === "number" && Number.isFinite(estimatedCostUsd)
        ? estimatedCostUsd
        : null,
  }
}

function buildSearchDetailsFromResponse(
  response: {
    expandedQueries: string[]
    metadata: Record<string, unknown>
  },
  results: RagResult[],
  settings: RagSettings
): SearchRuntimeDetails {
  const webFallbackMetadata =
    response.metadata?.web_fallback &&
    typeof response.metadata.web_fallback === "object"
      ? (response.metadata.web_fallback as Record<string, unknown>)
      : null
  const whyTheseSourcesMetadata =
    response.metadata?.why_these_sources &&
    typeof response.metadata.why_these_sources === "object"
      ? (response.metadata.why_these_sources as Record<string, unknown>)
      : null
  const { tokensUsed, estimatedCostUsd } = extractTokenAndCostDetails(
    response.metadata
  )

  return {
    expandedQueries: response.expandedQueries,
    rerankingEnabled: Boolean(settings.enable_reranking),
    rerankingStrategy:
      typeof settings.reranking_strategy === "string"
        ? settings.reranking_strategy
        : "unknown",
    averageRelevance: calculateAverageRelevance(results),
    webFallbackEnabled: Boolean(settings.enable_web_fallback),
    webFallbackTriggered:
      typeof webFallbackMetadata?.triggered === "boolean"
        ? webFallbackMetadata.triggered
        : false,
    webFallbackEngine:
      typeof webFallbackMetadata?.engine_used === "string"
        ? webFallbackMetadata.engine_used
        : null,
    tokensUsed,
    estimatedCostUsd,
    feedbackId:
      typeof response.metadata?.feedback_id === "string"
        ? response.metadata.feedback_id
        : null,
    whyTheseSources: whyTheseSourcesMetadata
      ? {
          topicality: normalizeMetric(whyTheseSourcesMetadata.topicality),
          diversity: normalizeMetric(whyTheseSourcesMetadata.diversity),
          freshness: normalizeMetric(whyTheseSourcesMetadata.freshness),
        }
      : null,
  }
}

function buildSearchDetailsFromStreaming(
  results: RagResult[],
  whyPayload: unknown,
  settings: RagSettings
): SearchRuntimeDetails {
  const why =
    whyPayload && typeof whyPayload === "object"
      ? (whyPayload as Record<string, unknown>)
      : null

  return {
    expandedQueries: [],
    rerankingEnabled: Boolean(settings.enable_reranking),
    rerankingStrategy:
      typeof settings.reranking_strategy === "string"
        ? settings.reranking_strategy
        : "unknown",
    averageRelevance: calculateAverageRelevance(results),
    webFallbackEnabled: Boolean(settings.enable_web_fallback),
    webFallbackTriggered: false,
    webFallbackEngine: null,
    tokensUsed: null,
    estimatedCostUsd: null,
    feedbackId: null,
    whyTheseSources: why
      ? {
          topicality: normalizeMetric(why.topicality),
          diversity: normalizeMetric(why.diversity),
          freshness: normalizeMetric(why.freshness),
        }
      : null,
  }
}

function buildScopeSnapshot(
  preset: RagPresetName,
  settings: RagSettings
): ScopeSnapshot {
  return {
    preset,
    sources: [...settings.sources],
    webFallback: Boolean(settings.enable_web_fallback),
  }
}

// Provider component
export function KnowledgeQAProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [storedPreset] = useStorage<RagPresetName>("ragSearchPreset", "balanced")
  const [storedSettings] = useStorage<RagSettings>(
    "ragSearchSettingsV2",
    DEFAULT_RAG_SETTINGS
  )
  const [streamingFeatureFlag] = useStorage<boolean>("ff_knowledgeQaStreaming", true)
  const hydratedDefaultsRef = useRef<string | null>(null)
  const activeSearchAbortRef = useRef<AbortController | null>(null)
  const focusedSourceTimeoutRef = useRef<number | null>(null)
  const persistenceWarningShownRef = useRef(false)
  const historyQuotaWarningShownRef = useRef(false)
  const message = useAntdMessage()
  const streamingFeatureEnabled = streamingFeatureFlag !== false
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

  const createNewThread = useCallback(
    async (title?: string, options?: CreateThreadOptions): Promise<string> => {
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
          ...(typeof options?.parentConversationId === "string" &&
          options.parentConversationId.trim().length > 0
            ? { parent_conversation_id: options.parentConversationId.trim() }
            : {}),
          ...(typeof options?.forkedFromMessageId === "string" &&
          options.forkedFromMessageId.trim().length > 0
            ? { forked_from_message_id: options.forkedFromMessageId.trim() }
            : {}),
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
        dispatch({ type: "SET_LOCAL_ONLY_THREAD", payload: false })
        dispatch({ type: "SET_MESSAGES", payload: [] })

        return threadId
      } catch (error) {
        console.error("Failed to create thread:", error)
        // Return a local ID as fallback
        const localId = `${LOCAL_THREAD_PREFIX}${crypto.randomUUID()}`
        dispatch({ type: "SET_THREAD_ID", payload: localId })
        dispatch({ type: "SET_LOCAL_ONLY_THREAD", payload: true })
        dispatch({ type: "SET_MESSAGES", payload: [] })
        return localId
      }
    },
    [resolveDefaultCharacterId, tagConversationKeyword]
  )

  const notifyPersistenceFailure = useCallback(() => {
    if (persistenceWarningShownRef.current) {
      return
    }
    persistenceWarningShownRef.current = true
    message.open({
      type: "warning",
      content: "Unable to save conversation. Results are available but may not persist.",
      duration: 4,
    })
  }, [message])

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
        notifyPersistenceFailure()
        return null
      }
    },
    [notifyPersistenceFailure]
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
        // Metadata-only failure path: answers/sources remain usable even if context persistence fails.
        console.error("Failed to persist RAG context:", error)
        return false
      }
    },
    []
  )

  const buildRagContext = useCallback(
    (
      question: string,
      results: RagResult[],
      answer: string | null,
      settings: RagSettings
    ): RagContextData => ({
      search_query: question,
      search_mode: settings.search_mode,
      settings_snapshot: {
        top_k: settings.top_k,
        enable_reranking: settings.enable_reranking,
        enable_citations: settings.enable_citations,
        enable_web_fallback: settings.enable_web_fallback,
        web_fallback_threshold: settings.web_fallback_threshold,
        web_search_engine: settings.web_search_engine,
        web_fallback_result_count: settings.web_fallback_result_count,
        web_fallback_merge_strategy: settings.web_fallback_merge_strategy,
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
    []
  )

  const runKnowledgeQuery = useCallback(
    async (
      question: string,
      addToHistory: boolean,
      settingsOverrides?: Partial<RagSettings>
    ) => {
      const trimmedQuery = question.trim()
      if (!trimmedQuery) return

      const searchStartedAt = Date.now()
      const abortController = new AbortController()
      activeSearchAbortRef.current = abortController
      dispatch({ type: "SET_SEARCHING", payload: true })
      dispatch({ type: "SET_QUERY_STAGE", payload: "searching" })
      dispatch({ type: "SET_SEARCH_DETAILS", payload: null })
      const effectiveSettings: RagSettings = {
        ...state.settings,
        ...(settingsOverrides || {}),
      }

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
          ...effectiveSettings,
          query: trimmedQuery,
          enable_web_fallback: effectiveSettings.enable_web_fallback,
        })

        const streamSearch = (tldwClient as {
          ragSearchStream?: (
            query: string,
            options?: Record<string, unknown>
          ) => AsyncGenerator<any, void, unknown>
        }).ragSearchStream
        const canAttemptStreaming =
          streamingFeatureEnabled &&
          effectiveSettings.enable_generation &&
          typeof streamSearch === "function"

        let results: RagResult[] = []
        let answer: string | null = null
        let usedStreaming = false
        let resolvedSearchDetails: SearchRuntimeDetails | null = null

        if (canAttemptStreaming && streamSearch) {
          let streamResults: RagResult[] = []
          let streamAnswer = ""
          let receivedStreamEvent = false
          let streamWhyPayload: unknown = null

          try {
            for await (const event of streamSearch(trimmedQuery, {
              ...options,
              signal: abortController.signal,
            })) {
              const eventType = typeof event?.type === "string" ? event.type : ""

              if (eventType === "contexts" && Array.isArray(event?.contexts)) {
                dispatch({ type: "SET_QUERY_STAGE", payload: "ranking" })
                streamResults = mapStreamingContextsToResults(event.contexts)
                streamWhyPayload = event?.why
                resolvedSearchDetails = buildSearchDetailsFromStreaming(
                  streamResults,
                  streamWhyPayload,
                  effectiveSettings
                )
                dispatch({
                  type: "SET_SEARCH_DETAILS",
                  payload: resolvedSearchDetails,
                })
                const partialCitations =
                  streamAnswer.length > 0
                    ? parseCitations(streamAnswer, streamResults)
                    : []
                dispatch({
                  type: "SET_PARTIAL_RESULTS",
                  payload: {
                    results: streamResults,
                    answer: streamAnswer || null,
                    citations: partialCitations,
                  },
                })
                receivedStreamEvent = true
                continue
              }

              if (eventType === "delta") {
                dispatch({ type: "SET_QUERY_STAGE", payload: "generating" })
                const deltaText =
                  typeof event?.text === "string" ? event.text : ""
                if (!deltaText) continue
                streamAnswer += deltaText
                dispatch({
                  type: "SET_PARTIAL_RESULTS",
                  payload: {
                    results: streamResults,
                    answer: streamAnswer,
                    citations: parseCitations(streamAnswer, streamResults),
                  },
                })
                receivedStreamEvent = true
                continue
              }

              if (eventType === "error") {
                throw new Error(
                  typeof event?.message === "string" && event.message
                    ? event.message
                    : "Search failed"
                )
              }
            }

            if (receivedStreamEvent) {
              results = streamResults
              answer = streamAnswer || null
              usedStreaming = true
              resolvedSearchDetails = buildSearchDetailsFromStreaming(
                streamResults,
                streamWhyPayload,
                effectiveSettings
              )
            }
          } catch (streamError) {
            const streamMessage =
              streamError instanceof Error
                ? streamError.message
                : String(streamError ?? "")
            const isStreamAbort =
              abortController.signal.aborted ||
              (streamError as { name?: string } | null)?.name === "AbortError" ||
              /abort|cancel/i.test(streamMessage)
            if (isStreamAbort) {
              throw streamError
            }

            console.warn(
              "Streaming search failed, falling back to standard search:",
              streamError
            )
          }
        }

        if (!usedStreaming) {
          dispatch({ type: "SET_QUERY_STAGE", payload: "ranking" })
          const response = await tldwClient.ragSearch(trimmedQuery, {
            ...options,
            signal: abortController.signal,
          })
          const extracted = extractRagResponse(response)
          results = extracted.results
          answer = extracted.answer
          if (answer) {
            dispatch({ type: "SET_QUERY_STAGE", payload: "generating" })
          }
          resolvedSearchDetails = buildSearchDetailsFromResponse(
            extracted,
            results,
            effectiveSettings
          )
        }

        // Parse citations from answer
        dispatch({ type: "SET_QUERY_STAGE", payload: "verifying" })
        const citations = answer ? parseCitations(answer, results) : []

        dispatch({
          type: "SET_RESULTS",
          payload: { results, answer, citations },
        })
        dispatch({ type: "SET_SEARCH_DETAILS", payload: resolvedSearchDetails })
        dispatch({
          type: "SET_LAST_SEARCH_SCOPE",
          payload: buildScopeSnapshot(state.preset, effectiveSettings),
        })
        void trackKnowledgeQaSearchMetric({
          type: "search_complete",
          duration_ms: Date.now() - searchStartedAt,
          result_count: results.length,
          has_answer: Boolean(answer),
          used_streaming: usedStreaming,
        })

        let assistantMessageId: string | null = null
        const ragContext = buildRagContext(
          trimmedQuery,
          results,
          answer,
          effectiveSettings
        )

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
            answerPreview: truncateAnswerPreview(answer),
            preset: state.preset,
            conversationId: threadId && !isLocalThreadId(threadId) ? threadId : undefined,
            messageId: assistantMessageId || undefined,
            keywords: [KNOWLEDGE_QA_KEYWORD],
          }
          dispatch({ type: "ADD_HISTORY_ITEM", payload: historyItem })
        }
      } catch (error) {
        const rawErrorMessage =
          error instanceof Error
            ? error.message
            : typeof error === "string"
              ? error
              : ""
        const isAbortError =
          abortController.signal.aborted ||
          (error as { name?: string } | null)?.name === "AbortError" ||
          /abort|cancel/i.test(rawErrorMessage)

        if (isAbortError) {
          const abortReason = abortController.signal.reason
          if (abortReason === "clear") {
            dispatch({ type: "SET_ERROR", payload: null })
            return
          }
          dispatch({ type: "SET_ERROR", payload: "Search cancelled" })
          dispatch({ type: "SET_QUERY_STAGE", payload: "idle" })
          return
        }
        console.error("Search failed:", error)
        const errorMessage = mapKnowledgeQaSearchErrorMessage(error, "Search failed")
        dispatch({
          type: "SET_ERROR",
          payload: errorMessage,
        })
      } finally {
        if (activeSearchAbortRef.current === abortController) {
          activeSearchAbortRef.current = null
        }
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
      streamingFeatureEnabled,
    ]
  )

  const cancelSearch = useCallback(() => {
    if (!state.isSearching || !activeSearchAbortRef.current) return

    void trackKnowledgeQaSearchMetric({ type: "search_cancel" })
    activeSearchAbortRef.current.abort("cancel")
    message.open({
      type: "info",
      content: "Search cancelled.",
      duration: 2,
    })
  }, [message, state.isSearching])

  const search = useCallback(async () => {
    const queryLength = state.query.trim().length
    if (queryLength > 0) {
      void trackKnowledgeQaSearchMetric({
        type: "search_submit",
        query_length: queryLength,
      })
    }
    await runKnowledgeQuery(state.query, true)
  }, [state.query, runKnowledgeQuery])

  const rerunWithTokenLimit = useCallback(
    async (tokenLimit: number) => {
      const normalized = Math.max(64, Math.min(4000, Math.round(tokenLimit)))
      await runKnowledgeQuery(state.query, false, {
        max_generation_tokens: normalized,
        enable_generation: true,
      })
    },
    [runKnowledgeQuery, state.query]
  )

  const clearResults = useCallback(() => {
    const hasClearableState =
      state.results.length > 0 ||
      Boolean(state.answer) ||
      state.messages.length > 0 ||
      Boolean(state.currentThreadId)
    if (hasClearableState) {
      void trackKnowledgeQaSearchMetric({ type: "search_clear_full" })
    }

    if (activeSearchAbortRef.current) {
      activeSearchAbortRef.current.abort("clear")
      activeSearchAbortRef.current = null
    }
    dispatch({ type: "CLEAR_RESULTS" })
    dispatch({ type: "SET_THREAD_ID", payload: null })
    dispatch({ type: "SET_LOCAL_ONLY_THREAD", payload: false })
    dispatch({ type: "SET_MESSAGES", payload: [] })
  }, [state.answer, state.currentThreadId, state.messages.length, state.results.length])

  const selectThread = useCallback(async (threadId: string) => {
    dispatch({ type: "SET_THREAD_ID", payload: threadId })
    dispatch({ type: "SET_LOCAL_ONLY_THREAD", payload: isLocalThreadId(threadId) })

    if (isLocalThreadId(threadId)) {
      dispatch({ type: "SET_MESSAGES", payload: [] })
      dispatch({ type: "CLEAR_RESULTS" })
      return
    }

    try {
      // Load messages with RAG context
      const response = await tldwClient.fetchWithAuth(
        `/api/v1/chat/conversations/${threadId}/messages-with-context?include_rag_context=true`
      )
      if (!response.ok) {
        throw new Error(`Failed to load thread ${threadId} (HTTP ${response.status})`)
      }
      const rawMessages = await response.json()
      const messages = normalizeMessagesWithContext(rawMessages, threadId)
      dispatch({ type: "SET_MESSAGES", payload: messages })

      const hydration = deriveThreadHydrationState(messages)
      if (hydration?.query) {
        dispatch({ type: "SET_QUERY", payload: hydration.query })
      }
      if (hydration && (hydration.results.length > 0 || hydration.answer)) {
        dispatch({
          type: "SET_RESULTS",
          payload: {
            results: hydration.results,
            answer: hydration.answer,
            citations: hydration.citations,
          },
        })
      } else {
        dispatch({ type: "CLEAR_RESULTS" })
      }

      const matchingHistoryItem = state.searchHistory.find(
        (item) => item.conversationId === threadId
      )
      if (matchingHistoryItem && hydration) {
        dispatch({
          type: "UPDATE_HISTORY_ITEM",
          payload: {
            id: matchingHistoryItem.id,
            patch: {
              answerPreview: hydration.answerPreview,
              hasAnswer: Boolean(hydration.answer),
              sourcesCount: hydration.sourcesCount || matchingHistoryItem.sourcesCount,
            },
          },
        })
      }
    } catch (error) {
      console.error("Failed to load thread messages:", error)
      dispatch({ type: "SET_MESSAGES", payload: [] })
      dispatch({ type: "CLEAR_RESULTS" })
    }
  }, [state.searchHistory])

  const selectSharedThread = useCallback(
    async (shareToken: string) => {
      const trimmedToken = shareToken.trim()
      if (!trimmedToken) {
        dispatch({ type: "SET_ERROR", payload: "Shared link is invalid." })
        return
      }

      try {
        const payload = await tldwClient.resolveConversationShareLink(trimmedToken)
        const conversationId =
          typeof payload?.conversation_id === "string" &&
          payload.conversation_id.trim().length > 0
            ? payload.conversation_id.trim()
            : `shared-${crypto.randomUUID()}`
        const rawMessages = Array.isArray(payload?.messages) ? payload.messages : []
        const messages = normalizeMessagesWithContext(rawMessages, conversationId)

        dispatch({ type: "SET_THREAD_ID", payload: null })
        dispatch({ type: "SET_LOCAL_ONLY_THREAD", payload: false })
        dispatch({ type: "SET_MESSAGES", payload: messages })
        dispatch({ type: "SET_SEARCH_DETAILS", payload: null })

        const hydration = deriveThreadHydrationState(messages)
        if (hydration?.query) {
          dispatch({ type: "SET_QUERY", payload: hydration.query })
        }
        if (hydration && (hydration.results.length > 0 || hydration.answer)) {
          dispatch({
            type: "SET_RESULTS",
            payload: {
              results: hydration.results,
              answer: hydration.answer,
              citations: hydration.citations,
            },
          })
        } else {
          dispatch({ type: "CLEAR_RESULTS" })
        }
      } catch (error) {
        console.error("Failed to load shared thread:", error)
        dispatch({ type: "SET_THREAD_ID", payload: null })
        dispatch({ type: "SET_LOCAL_ONLY_THREAD", payload: false })
        dispatch({ type: "SET_MESSAGES", payload: [] })
        dispatch({ type: "SET_SEARCH_DETAILS", payload: null })
        dispatch({ type: "CLEAR_RESULTS" })
        dispatch({
          type: "SET_ERROR",
          payload: "Unable to open this shared conversation link.",
        })
      }
    },
    []
  )

  const branchFromTurn = useCallback(
    async (messageId: string) => {
      const branchSeedMessages = sliceMessagesForBranch(state.messages, messageId)
      if (branchSeedMessages.length === 0) {
        message.open({
          type: "warning",
          content: "Unable to branch from that turn.",
          duration: 3,
        })
        return
      }

      const branchSourceQuestion =
        branchSeedMessages.find((entry) => entry.id === messageId)?.content?.trim() || ""
      const branchTitle =
        branchSourceQuestion.length > 0
          ? `Branch: ${branchSourceQuestion.slice(0, 64)}`
          : "Knowledge QA Branch"
      const parentConversationId =
        state.currentThreadId && !isLocalThreadId(state.currentThreadId)
          ? state.currentThreadId
          : undefined
      const branchThreadId = await createNewThread(branchTitle, {
        parentConversationId,
        forkedFromMessageId: messageId,
      })

      const branchedMessages: KnowledgeQAMessage[] = []
      let parentMessageId: string | null = null

      for (const sourceMessage of branchSeedMessages) {
        const persisted = await persistChatMessage(
          branchThreadId,
          sourceMessage.role,
          sourceMessage.content,
          parentMessageId
        )
        const nextMessageId = persisted?.id || crypto.randomUUID()
        parentMessageId = persisted?.id || null

        const branchMessage: KnowledgeQAMessage = {
          ...sourceMessage,
          id: nextMessageId,
          conversationId: branchThreadId,
          timestamp: persisted?.timestamp || sourceMessage.timestamp,
        }
        branchedMessages.push(branchMessage)

        if (
          sourceMessage.role === "assistant" &&
          sourceMessage.ragContext &&
          persisted?.id
        ) {
          await persistRagContext(persisted.id, sourceMessage.ragContext)
        }
      }

      dispatch({ type: "SET_THREAD_ID", payload: branchThreadId })
      dispatch({ type: "SET_LOCAL_ONLY_THREAD", payload: isLocalThreadId(branchThreadId) })
      dispatch({ type: "SET_MESSAGES", payload: branchedMessages })
      dispatch({ type: "SET_SEARCH_DETAILS", payload: null })

      const hydration = deriveThreadHydrationState(branchedMessages)
      if (hydration?.query) {
        dispatch({ type: "SET_QUERY", payload: hydration.query })
      }
      if (hydration && (hydration.results.length > 0 || hydration.answer)) {
        dispatch({
          type: "SET_RESULTS",
          payload: {
            results: hydration.results,
            answer: hydration.answer,
            citations: hydration.citations,
          },
        })
      } else {
        dispatch({ type: "CLEAR_RESULTS" })
      }

      message.open({
        type: "success",
        content: "Branch created from selected turn.",
        duration: 3,
      })
    },
    [
      createNewThread,
      message,
      persistChatMessage,
      persistRagContext,
      state.currentThreadId,
      state.messages,
    ]
  )

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

  const toggleHistoryPin = useCallback((id: string) => {
    dispatch({ type: "TOGGLE_HISTORY_PIN", payload: id })
  }, [])

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

  const setEvidenceRailOpen = useCallback((open: boolean) => {
    dispatch({ type: "SET_EVIDENCE_RAIL_OPEN", payload: open })
  }, [])

  const setEvidenceRailTab = useCallback((tab: "sources" | "details") => {
    dispatch({ type: "SET_EVIDENCE_RAIL_TAB", payload: tab })
  }, [])

  const setQueryStage = useCallback((stage: QueryStage) => {
    dispatch({ type: "SET_QUERY_STAGE", payload: stage })
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
    if (state.searchHistory.length === 0) {
      localStorage.removeItem("knowledge_qa_history")
      return
    }

    try {
      const { storedHistory, wasTrimmed } = persistKnowledgeQaHistory(
        state.searchHistory,
        (serializedHistory) => {
          localStorage.setItem("knowledge_qa_history", serializedHistory)
        }
      )

      if (wasTrimmed && storedHistory.length !== state.searchHistory.length) {
        dispatch({ type: "SET_SEARCH_HISTORY", payload: storedHistory })
        if (!historyQuotaWarningShownRef.current) {
          historyQuotaWarningShownRef.current = true
          message.open({
            type: "warning",
            content: "History storage is full. Oldest searches were trimmed locally.",
            duration: 4,
          })
        }
      }
    } catch (error) {
      console.error("Failed to persist Knowledge QA history:", error)
    }
  }, [message, state.searchHistory])

  // Load history on mount
  useEffect(() => {
    loadSearchHistory()
  }, [loadSearchHistory])

  // Auto-clear focused source highlight to prevent stale focus rings.
  useEffect(() => {
    if (typeof window === "undefined") return

    if (focusedSourceTimeoutRef.current != null) {
      window.clearTimeout(focusedSourceTimeoutRef.current)
      focusedSourceTimeoutRef.current = null
    }

    if (state.focusedSourceIndex == null) {
      return
    }

    focusedSourceTimeoutRef.current = window.setTimeout(() => {
      dispatch({ type: "SET_FOCUSED_SOURCE", payload: null })
      focusedSourceTimeoutRef.current = null
    }, 5000)

    return () => {
      if (focusedSourceTimeoutRef.current != null) {
        window.clearTimeout(focusedSourceTimeoutRef.current)
        focusedSourceTimeoutRef.current = null
      }
    }
  }, [state.focusedSourceIndex])

  // Memoized context value
  const contextValue = useMemo<KnowledgeQAContextValue>(
    () => ({
      ...state,
      setQuery,
      search,
      cancelSearch,
      clearResults,
      rerunWithTokenLimit,
      createNewThread,
      selectThread,
      selectSharedThread,
      askFollowUp,
      branchFromTurn,
      setPreset,
      updateSetting,
      resetSettings,
      toggleExpertMode,
      loadSearchHistory,
      restoreFromHistory,
      deleteHistoryItem,
      toggleHistoryPin,
      setSettingsPanelOpen,
      setHistorySidebarOpen,
      focusSource,
      setEvidenceRailOpen,
      setEvidenceRailTab,
      setQueryStage,
      persistRagContext,
      scrollToSource,
    }),
    [
      state,
      setQuery,
      search,
      cancelSearch,
      clearResults,
      rerunWithTokenLimit,
      createNewThread,
      selectThread,
      selectSharedThread,
      askFollowUp,
      branchFromTurn,
      setPreset,
      updateSetting,
      resetSettings,
      toggleExpertMode,
      loadSearchHistory,
      restoreFromHistory,
      deleteHistoryItem,
      toggleHistoryPin,
      setSettingsPanelOpen,
      setHistorySidebarOpen,
      focusSource,
      setEvidenceRailOpen,
      setEvidenceRailTab,
      setQueryStage,
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
