import React from "react"
import { useTranslation } from "react-i18next"
import {
  AlertCircle,
  ChevronDown,
  FileText,
  Send,
  MessageSquarePlus,
  Square,
  Trash2,
  RotateCcw,
  SlidersHorizontal
} from "lucide-react"
import { Modal, Tag, Tooltip, Input, Slider, Switch, message } from "antd"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { useWorkspaceStore } from "@/store/workspace"
import { useStoreMessageOption } from "@/store/option"
import { useMessageOption } from "@/hooks/useMessageOption"
import { useSmartScroll } from "@/hooks/useSmartScroll"
import { useMobile } from "@/hooks/useMediaQuery"
import { useConnectionStore } from "@/store/connection"
import { ConnectionPhase } from "@/types/connection"
import { DEFAULT_RAG_SETTINGS } from "@/services/rag/unified-rag"
import type { WorkspaceSource, WorkspaceSourceType } from "@/types/workspace"
import { PlaygroundMessage } from "@/components/Common/Playground/Message"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import {
  WORKSPACE_SOURCE_DRAG_TYPE,
  parseWorkspaceSourceDragPayload
} from "../drag-source"
import { getWorkspaceChatNoSourcesHint } from "../source-location-copy"
import { getWorkspaceChatSearchMessageId } from "../workspace-global-search"

const { TextArea } = Input
const VISIBLE_SOURCE_TAG_COUNT = 5

type RetrievalDiagnostics = {
  chunkCount: number | null
  sourceCount: number | null
  averageRelevanceScore: number | null
}

type ChatModePreference = "normal" | "rag"
type LorebookActivityTurn = {
  turnNumber: number
  assistantPreview: string
  entryCount: number
}

const LOREBOOK_ACTIVITY_PAGE_SIZE = 8
const LOREBOOK_ACTIVITY_EXPORT_PAGE_SIZE = 200
const LOREBOOK_DEBUG_ENTRYPOINT_HREF = "/playground?focus=lorebook-debug"

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null

const toPositiveInt = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isInteger(value) && value > 0) {
    return value
  }
  if (typeof value === "string") {
    const parsed = Number.parseInt(value, 10)
    if (Number.isInteger(parsed) && parsed > 0) {
      return parsed
    }
  }
  return null
}

const toFiniteNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value
  }
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number.parseFloat(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return null
}

const normalizeText = (value: unknown): string =>
  typeof value === "string" ? value.trim().toLowerCase() : ""

const extractCitationMediaId = (citation: unknown): number | null => {
  if (!isRecord(citation)) return null
  const metadata = isRecord(citation.metadata) ? citation.metadata : null
  const includeMediaIds = Array.isArray(metadata?.include_media_ids)
    ? metadata?.include_media_ids
    : []
  const mediaCandidates: unknown[] = [
    citation.mediaId,
    citation.media_id,
    citation.mediaID,
    metadata?.mediaId,
    metadata?.media_id,
    metadata?.mediaID,
    ...includeMediaIds
  ]

  for (const candidate of mediaCandidates) {
    const mediaId = toPositiveInt(candidate)
    if (mediaId !== null) {
      return mediaId
    }
  }
  return null
}

const findSourceIdFromCitation = (
  citation: unknown,
  sources: WorkspaceSource[]
): string | null => {
  if (!isRecord(citation)) return null

  const citationMediaId = extractCitationMediaId(citation)
  if (citationMediaId !== null) {
    const byMediaId = sources.find((source) => source.mediaId === citationMediaId)
    if (byMediaId) return byMediaId.id
  }

  const metadata = isRecord(citation.metadata) ? citation.metadata : null
  const citationUrl = normalizeText(citation.url || metadata?.url)
  if (citationUrl) {
    const byUrl = sources.find(
      (source) => normalizeText(source.url) === citationUrl
    )
    if (byUrl) return byUrl.id
  }

  const candidateLabels = new Set(
    [
      citation.name,
      citation.title,
      citation.source,
      metadata?.source,
      metadata?.title
    ]
      .map(normalizeText)
      .filter(Boolean)
  )

  if (candidateLabels.size === 0) {
    return null
  }

  for (const source of sources) {
    const normalizedTitle = normalizeText(source.title)
    if (!normalizedTitle) continue
    if (candidateLabels.has(normalizedTitle)) {
      return source.id
    }
  }

  for (const source of sources) {
    const normalizedTitle = normalizeText(source.title)
    if (!normalizedTitle) continue
    for (const label of candidateLabels) {
      if (label.includes(normalizedTitle) || normalizedTitle.includes(label)) {
        return source.id
      }
    }
  }

  return null
}

const extractSourceScore = (source: unknown): number | null => {
  if (!isRecord(source)) return null
  const metadata = isRecord(source.metadata) ? source.metadata : null
  const scoreCandidates: unknown[] = [
    source.score,
    source.relevance,
    source.relevance_score,
    source.similarity,
    source.rerank_score,
    metadata?.score,
    metadata?.relevance,
    metadata?.relevance_score,
    metadata?.similarity,
    metadata?.rerank_score
  ]

  for (const candidate of scoreCandidates) {
    const parsed = toFiniteNumber(candidate)
    if (parsed !== null) {
      return parsed
    }
  }
  return null
}

const getNumericField = (
  generationInfo: unknown,
  paths: Array<string[]>
): number | null => {
  if (!isRecord(generationInfo)) return null

  for (const path of paths) {
    let current: unknown = generationInfo
    for (const key of path) {
      if (!isRecord(current)) {
        current = undefined
        break
      }
      current = current[key]
    }
    const parsed = toFiniteNumber(current)
    if (parsed !== null) {
      return parsed
    }
  }

  return null
}

const buildRetrievalDiagnostics = (
  messageSources: unknown[] | undefined,
  generationInfo: unknown
): RetrievalDiagnostics | null => {
  const sources = Array.isArray(messageSources) ? messageSources : []

  const chunkCountFromGeneration = getNumericField(generationInfo, [
    ["retrieval", "chunks_retrieved"],
    ["retrieval", "chunk_count"],
    ["retrieval", "chunks"],
    ["chunks_retrieved"],
    ["chunk_count"],
    ["retrieved_chunks"],
    ["context_chunks"]
  ])

  const sourceCountFromGeneration = getNumericField(generationInfo, [
    ["retrieval", "source_count"],
    ["retrieval", "sources_used"],
    ["source_count"],
    ["sources_used"]
  ])

  const avgScoreFromGeneration = getNumericField(generationInfo, [
    ["retrieval", "avg_relevance_score"],
    ["retrieval", "average_relevance_score"],
    ["avg_relevance_score"],
    ["average_relevance_score"],
    ["relevance_score"]
  ])

  const uniqueSourceKeys = new Set<string>()
  for (const source of sources) {
    if (!isRecord(source)) continue
    const mediaId = extractCitationMediaId(source)
    if (mediaId !== null) {
      uniqueSourceKeys.add(`media:${mediaId}`)
      continue
    }
    const metadata = isRecord(source.metadata) ? source.metadata : null
    const label =
      normalizeText(source.name || source.url || metadata?.source || metadata?.title)
    if (label) {
      uniqueSourceKeys.add(`label:${label}`)
    }
  }

  const sourceScores = sources
    .map((source) => extractSourceScore(source))
    .filter((score): score is number => score !== null)

  const averageScoreFromSources =
    sourceScores.length > 0
      ? sourceScores.reduce((sum, score) => sum + score, 0) /
        sourceScores.length
      : null

  const diagnostics: RetrievalDiagnostics = {
    chunkCount:
      chunkCountFromGeneration !== null
        ? Math.max(0, Math.round(chunkCountFromGeneration))
        : sources.length > 0
          ? sources.length
          : null,
    sourceCount:
      sourceCountFromGeneration !== null
        ? Math.max(0, Math.round(sourceCountFromGeneration))
        : uniqueSourceKeys.size > 0
          ? uniqueSourceKeys.size
          : null,
    averageRelevanceScore:
      avgScoreFromGeneration !== null
        ? avgScoreFromGeneration
        : averageScoreFromSources
  }

  if (
    diagnostics.chunkCount === null &&
    diagnostics.sourceCount === null &&
    diagnostics.averageRelevanceScore === null
  ) {
    return null
  }

  return diagnostics
}

/**
 * ChatContextIndicator - Shows sources as horizontally scrollable tags
 */
const ChatContextIndicator: React.FC = () => {
  const { t } = useTranslation(["playground"])
  const selectedSourceIds = useWorkspaceStore((s) => s.selectedSourceIds)
  const getSelectedSources = useWorkspaceStore((s) => s.getSelectedSources)
  const selectedSources = getSelectedSources()
  const [showAllSources, setShowAllSources] = React.useState(false)

  React.useEffect(() => {
    setShowAllSources(false)
  }, [selectedSourceIds])

  if (selectedSources.length === 0) return null

  const hiddenSourceCount = Math.max(
    0,
    selectedSources.length - VISIBLE_SOURCE_TAG_COUNT
  )
  const visibleSources = showAllSources
    ? selectedSources
    : selectedSources.slice(0, VISIBLE_SOURCE_TAG_COUNT)

  return (
    <div className="shrink-0 border-b border-border bg-surface px-4 py-2">
      <div className="flex items-center gap-2">
        <span className="shrink-0 text-xs font-medium text-text-muted">
          <FileText className="mr-1 inline h-3 w-3" />
          {t("playground:chat.usingSourcesLabel", "Sources:")}
        </span>
        {/* Horizontally scrollable source tags */}
        <div className="custom-scrollbar flex min-w-0 flex-1 gap-1.5 overflow-x-auto pb-0.5">
          {visibleSources.map((source) => (
            <Tooltip key={source.id} title={source.title}>
              <Tag
                color="blue"
                className="shrink-0 cursor-default !m-0 max-w-[150px] truncate"
              >
                {source.title}
              </Tag>
            </Tooltip>
          ))}
          {hiddenSourceCount > 0 && !showAllSources && (
            <button
              type="button"
              onClick={() => setShowAllSources(true)}
              className="shrink-0 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary transition hover:bg-primary/15"
              aria-label={t("playground:chat.showMoreSources", "Show more sources")}
            >
              +{hiddenSourceCount}{" "}
              {t("playground:chat.moreSources", "more")}
            </button>
          )}
          {hiddenSourceCount > 0 && showAllSources && (
            <button
              type="button"
              onClick={() => setShowAllSources(false)}
              className="shrink-0 rounded-full border border-border bg-surface2 px-2 py-0.5 text-xs font-medium text-text-muted transition hover:bg-surface"
              aria-label={t("playground:chat.showFewerSources", "Show fewer sources")}
            >
              {t("playground:chat.showLess", "Show less")}
            </button>
          )}
        </div>
      </div>
      <p className="mt-1 text-xs text-text-muted">
        {t(
          "playground:chat.ragModeHint",
          "Answers will be grounded in your selected sources"
        )}
      </p>
    </div>
  )
}

const RetrievalDiagnosticsPanel: React.FC<{
  diagnostics: RetrievalDiagnostics
}> = ({ diagnostics }) => {
  const { t } = useTranslation(["playground"])

  return (
    <details className="rounded-md border border-border bg-surface2/40 px-3 py-2 text-xs text-text-muted">
      <summary className="cursor-pointer font-medium text-text-subtle">
        {t("playground:chat.retrievalInfo", "Retrieval info")}
      </summary>
      <div className="mt-2 space-y-1">
        {diagnostics.chunkCount !== null && (
          <p>
            {t("playground:chat.retrievalChunks", "Chunks retrieved")}:{" "}
            <span className="font-medium text-text">{diagnostics.chunkCount}</span>
          </p>
        )}
        {diagnostics.sourceCount !== null && (
          <p>
            {t("playground:chat.retrievalSources", "Sources used")}:{" "}
            <span className="font-medium text-text">{diagnostics.sourceCount}</span>
          </p>
        )}
        {diagnostics.averageRelevanceScore !== null && (
          <p>
            {t("playground:chat.retrievalAverageScore", "Avg relevance score")}:{" "}
            <span className="font-medium text-text">
              {diagnostics.averageRelevanceScore.toFixed(3)}
            </span>
          </p>
        )}
      </div>
    </details>
  )
}

/**
 * WorkspaceChatEmpty - Empty state for the workspace chat
 */
const WorkspaceChatEmpty: React.FC<{
  hasSelectedSources: boolean
  sourceCount: number
  selectedSourceTypes: WorkspaceSourceType[]
  isMobile: boolean
}> = ({ hasSelectedSources, sourceCount, selectedSourceTypes, isMobile }) => {
  const { t } = useTranslation(["playground"])
  const sourceTypeSet = React.useMemo(
    () => new Set(selectedSourceTypes),
    [selectedSourceTypes]
  )

  const examples = React.useMemo(() => {
    if (!hasSelectedSources) {
      return [
        t(
          "playground:chat.exampleGeneral1",
          "Help me frame a research question on this topic"
        ),
        t(
          "playground:chat.exampleGeneral2",
          "Give me a quick overview before I add sources"
        ),
        t(
          "playground:chat.exampleGeneral3",
          "What should I look for in high-quality sources?"
        )
      ]
    }

    const adaptiveExamples: string[] = []
    if (sourceTypeSet.has("video")) {
      adaptiveExamples.push(
        t(
          "playground:chat.exampleVideo",
          "What was discussed around minute 12?"
        )
      )
    }
    if (sourceTypeSet.has("audio")) {
      adaptiveExamples.push(
        t(
          "playground:chat.exampleAudio",
          "List key takeaways and speaker viewpoints from this audio"
        )
      )
    }
    if (
      sourceTypeSet.has("pdf") ||
      sourceTypeSet.has("document") ||
      sourceTypeSet.has("text")
    ) {
      adaptiveExamples.push(
        t(
          "playground:chat.exampleDocument",
          "Summarize chapter 3 and cite the strongest supporting passages"
        )
      )
    }
    if (sourceTypeSet.has("website")) {
      adaptiveExamples.push(
        t(
          "playground:chat.exampleWebsite",
          "Extract the main claims and supporting evidence from these pages"
        )
      )
    }

    const fallbackExamples = [
      t("playground:chat.example1", "Summarize the key points from these sources"),
      t("playground:chat.example2", "What are the main arguments presented?"),
      t("playground:chat.example3", "Compare and contrast the different perspectives")
    ]

    return [...new Set([...adaptiveExamples, ...fallbackExamples])].slice(0, 3)
  }, [hasSelectedSources, sourceTypeSet, t])

  return (
    <div className="mx-auto mt-10 max-w-xl px-4">
      <FeatureEmptyState
        icon={MessageSquarePlus}
        title={t("playground:chat.emptyTitle", "Start your research")}
        description={
          hasSelectedSources
            ? t(
                "playground:chat.emptyWithSources",
                "Ask questions about your {{count}} selected source(s)",
                { count: sourceCount }
              )
            : t(
                "playground:chat.emptyNoSources",
                getWorkspaceChatNoSourcesHint(isMobile)
              )
        }
        examples={examples}
      />
    </div>
  )
}

/**
 * SimpleChatInput - A simple chat input component
 */
const SimpleChatInput: React.FC<{
  onSubmit: (message: string) => void
  onStop: () => void
  isLoading: boolean
  placeholder?: string
  seededValue?: string | null
  onSeedConsumed?: () => void
}> = ({
  onSubmit,
  onStop,
  isLoading,
  placeholder,
  seededValue,
  onSeedConsumed
}) => {
  const { t } = useTranslation(["playground", "common"])
  const [value, setValue] = React.useState("")

  React.useEffect(() => {
    if (typeof seededValue !== "string") return
    setValue(seededValue)
    onSeedConsumed?.()
  }, [onSeedConsumed, seededValue])

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || isLoading) return
    onSubmit(trimmed)
    setValue("")
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div>
      <form onSubmit={handleSubmit} className="flex items-end gap-2">
        <div className="relative flex-1">
          <TextArea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              placeholder || t("playground:chat.inputPlaceholder", "Type a message...")
            }
            autoSize={{ minRows: 1, maxRows: 6 }}
            disabled={isLoading}
            className="pr-10 text-sm"
          />
        </div>
        {isLoading ? (
          <button
            type="button"
            onClick={onStop}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-error text-white transition hover:bg-error/90"
            aria-label={t("common:stop", "Stop")}
            title={t("common:stop", "Stop") as string}
          >
            <Square className="h-4 w-4 fill-current" />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!value.trim()}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-white transition hover:bg-primaryStrong disabled:cursor-not-allowed disabled:opacity-50"
            aria-label={t("common:send", "Send")}
          >
            <Send className="h-5 w-5" />
          </button>
        )}
      </form>
      <p className="mt-1 text-xs text-text-muted">
        {t(
          "playground:chat.inputKeyboardHint",
          "Enter to send, Shift+Enter for new line"
        )}
      </p>
    </div>
  )
}

// Generate a stable conversation instance ID for the workspace
const WORKSPACE_CONVERSATION_ID = "workspace-playground-conversation"
const WORKSPACE_DISCUSS_EVENT = "workspace-playground:discuss-artifact"
const WORKSPACE_SOURCE_CONTEXT_WARNING_KEY =
  "workspace-playground:source-context-warning"

type WorkspaceDiscussArtifactDetail = {
  artifactId: string
  artifactType: string
  title: string
  content: string
}

const buildCapturedMessageTitle = (
  isBot: boolean,
  text: string,
  assistantPrefix: string,
  userPrefix: string
): string => {
  const prefix = isBot ? assistantPrefix : userPrefix
  const collapsed = text.replace(/\s+/g, " ").trim()
  if (!collapsed) return prefix
  const excerpt = collapsed.length > 56 ? `${collapsed.slice(0, 56)}...` : collapsed
  return `${prefix}: ${excerpt}`
}

/**
 * ChatPane - Middle pane for RAG-powered conversation
 */
export const ChatPane: React.FC = () => {
  const { t } = useTranslation(["playground", "common"])
  const isMobile = useMobile()
  const [messageApi, messageContextHolder] = message.useMessage()

  // Workspace store
  const selectedSourceIds = useWorkspaceStore((s) => s.selectedSourceIds)
  const sources = useWorkspaceStore((s) => s.sources)
  const getSelectedSources = useWorkspaceStore((s) => s.getSelectedSources)
  const getSelectedMediaIds = useWorkspaceStore((s) => s.getSelectedMediaIds)
  const setSelectedSourceIds = useWorkspaceStore((s) => s.setSelectedSourceIds)
  const focusSourceById = useWorkspaceStore((s) => s.focusSourceById)
  const focusSourceByMediaId = useWorkspaceStore((s) => s.focusSourceByMediaId)
  const captureToCurrentNote = useWorkspaceStore((s) => s.captureToCurrentNote)
  const workspaceId = useWorkspaceStore((s) => s.workspaceId)
  const workspaceChatReferenceId = useWorkspaceStore(
    (s) => s.workspaceChatReferenceId
  )
  const chatFocusTarget = useWorkspaceStore((s) => s.chatFocusTarget)
  const clearChatFocusTarget = useWorkspaceStore((s) => s.clearChatFocusTarget)

  // Message option hook
  const {
    messages,
    setMessages,
    history,
    setHistory,
    streaming,
    setStreaming,
    isProcessing,
    setIsProcessing,
    onSubmit,
    stopStreamingRequest,
    regenerateLastMessage,
    deleteMessage,
    editMessage,
    historyId,
    setHistoryId,
    serverChatId,
    setServerChatId
  } = useMessageOption({})

  // RAG state from store
  const setRagMediaIds = useStoreMessageOption((s) => s.setRagMediaIds)
  const setChatMode = useStoreMessageOption((s) => s.setChatMode)
  const setFileRetrievalEnabled = useStoreMessageOption(
    (s) => s.setFileRetrievalEnabled
  )
  const ragTopK = useStoreMessageOption((s) => s.ragTopK)
  const setRagTopK = useStoreMessageOption((s) => s.setRagTopK)
  const ragAdvancedOptions = useStoreMessageOption((s) => s.ragAdvancedOptions)
  const setRagAdvancedOptions = useStoreMessageOption(
    (s) => s.setRagAdvancedOptions
  )
  const saveWorkspaceChatSession = useWorkspaceStore(
    (s) => s.saveWorkspaceChatSession
  )
  const getWorkspaceChatSession = useWorkspaceStore(
    (s) => s.getWorkspaceChatSession
  )
  const checkConnectionOnce = useConnectionStore((s) => s.checkOnce)
  const connectionState = useConnectionStore((s) => s.state)
  const [preferredChatMode, setPreferredChatMode] = React.useState<
    ChatModePreference | null
  >(null)
  const [dropZoneActive, setDropZoneActive] = React.useState(false)
  const [seededPrompt, setSeededPrompt] = React.useState<string | null>(null)
  const [highlightedChatMessageId, setHighlightedChatMessageId] = React.useState<
    string | null
  >(null)
  const [showAdvancedRagSettings, setShowAdvancedRagSettings] = React.useState(
    false
  )
  const [submitError, setSubmitError] = React.useState<string | null>(null)
  const [lorebookActivityTurns, setLorebookActivityTurns] = React.useState<
    LorebookActivityTurn[]
  >([])
  const [lorebookActivityTotal, setLorebookActivityTotal] = React.useState(0)
  const [lorebookActivityLoading, setLorebookActivityLoading] =
    React.useState(false)
  const [lorebookActivityError, setLorebookActivityError] = React.useState<
    string | null
  >(null)
  const [lorebookActivityForbidden, setLorebookActivityForbidden] =
    React.useState(false)
  const [exportingLorebookActivity, setExportingLorebookActivity] =
    React.useState(false)
  const workspaceSessionRef = React.useRef<string | null>(null)
  const chatMessageItemRefs = React.useRef<Record<string, HTMLDivElement | null>>(
    {}
  )
  const previousSelectedSourcesRef = React.useRef<string[]>(selectedSourceIds)
  const selectedSourcesInitializedRef = React.useRef(false)
  const workspaceSessionId = workspaceId || WORKSPACE_CONVERSATION_ID

  // Smart scroll for chat messages
  const { containerRef, isAutoScrollToBottom, autoScrollToBottom } =
    useSmartScroll(messages, streaming, 120)

  const selectedSources = getSelectedSources()
  const hasMessages = messages.length > 0
  const hasSelectedSources = selectedSources.length > 0
  const normalizedRagAdvancedOptions = React.useMemo(() => {
    return isRecord(ragAdvancedOptions) ? ragAdvancedOptions : {}
  }, [ragAdvancedOptions])
  const resolvedTopK = React.useMemo(() => {
    const value =
      typeof ragTopK === "number" && Number.isFinite(ragTopK)
        ? ragTopK
        : DEFAULT_RAG_SETTINGS.top_k
    return Math.max(1, Math.min(50, Math.round(value)))
  }, [ragTopK])
  const similarityThreshold = React.useMemo(() => {
    const raw = normalizedRagAdvancedOptions.min_score
    const value =
      typeof raw === "number" && Number.isFinite(raw)
        ? raw
        : DEFAULT_RAG_SETTINGS.min_score
    return Math.max(0, Math.min(1, value))
  }, [normalizedRagAdvancedOptions.min_score])
  const rerankingEnabled = React.useMemo(() => {
    const raw = normalizedRagAdvancedOptions.enable_reranking
    return typeof raw === "boolean"
      ? raw
      : DEFAULT_RAG_SETTINGS.enable_reranking
  }, [normalizedRagAdvancedOptions.enable_reranking])
  const requestedChatMode: ChatModePreference =
    preferredChatMode ?? (hasSelectedSources ? "rag" : "normal")
  const effectiveChatMode: ChatModePreference =
    hasSelectedSources && requestedChatMode === "rag" ? "rag" : "normal"

  const updateRagAdvancedOptions = React.useCallback(
    (patch: Record<string, unknown>) => {
      setRagAdvancedOptions({
        ...normalizedRagAdvancedOptions,
        ...patch
      })
    },
    [normalizedRagAdvancedOptions, setRagAdvancedOptions]
  )

  const handleTopKChange = (value: number | number[]) => {
    const raw = Array.isArray(value) ? value[0] : value
    if (typeof raw !== "number" || !Number.isFinite(raw)) return
    const nextTopK = Math.max(1, Math.min(50, Math.round(raw)))
    setRagTopK(nextTopK)
    updateRagAdvancedOptions({ top_k: nextTopK })
  }

  const handleSimilarityThresholdChange = (value: number | number[]) => {
    const raw = Array.isArray(value) ? value[0] : value
    if (typeof raw !== "number" || !Number.isFinite(raw)) return
    const nextThreshold = Math.max(0, Math.min(1, raw))
    updateRagAdvancedOptions({ min_score: Number(nextThreshold.toFixed(2)) })
  }

  const handleRerankingToggle = (checked: boolean) => {
    updateRagAdvancedOptions({ enable_reranking: checked })
  }

  React.useEffect(() => {
    if (!hasSelectedSources && showAdvancedRagSettings) {
      setShowAdvancedRagSettings(false)
    }
  }, [hasSelectedSources, showAdvancedRagSettings])

  React.useEffect(() => {
    if (!selectedSourcesInitializedRef.current) {
      previousSelectedSourcesRef.current = selectedSourceIds
      selectedSourcesInitializedRef.current = true
      return
    }

    const previous = previousSelectedSourcesRef.current
    const removedSourceCount = previous.filter(
      (sourceId) => !selectedSourceIds.includes(sourceId)
    ).length

    if (removedSourceCount > 0 && hasMessages) {
      messageApi.info({
        key: WORKSPACE_SOURCE_CONTEXT_WARNING_KEY,
        duration: 4,
        content: t(
          "playground:chat.sourceContextChangedWarning",
          "Source context changed. Previous answers may reference sources no longer selected."
        )
      })
    }

    previousSelectedSourcesRef.current = selectedSourceIds
  }, [hasMessages, messageApi, selectedSourceIds, t])

  // Sync selected sources + user mode preference with RAG context
  React.useEffect(() => {
    const mediaIds = getSelectedMediaIds()
    const hasScopedMediaIds = mediaIds.length > 0
    const autoMode: ChatModePreference = hasScopedMediaIds ? "rag" : "normal"
    const resolvedMode = preferredChatMode ?? autoMode
    const nextMode: ChatModePreference =
      hasScopedMediaIds && resolvedMode === "rag" ? "rag" : "normal"

    if (nextMode === "rag") {
      setRagMediaIds(mediaIds)
      setChatMode("rag")
      setFileRetrievalEnabled(true)
    } else {
      setRagMediaIds(null)
      setChatMode("normal")
      setFileRetrievalEnabled(false)
    }
  }, [
    selectedSourceIds,
    preferredChatMode,
    getSelectedMediaIds,
    setChatMode,
    setFileRetrievalEnabled,
    setRagMediaIds
  ])

  React.useEffect(() => {
    if (!workspaceSessionId) return

    saveWorkspaceChatSession(workspaceSessionId, {
      messages,
      history,
      historyId,
      serverChatId
    })
  }, [
    workspaceSessionId,
    messages,
    history,
    historyId,
    serverChatId,
    saveWorkspaceChatSession
  ])

  React.useEffect(() => {
    if (!workspaceSessionId) return

    const previousWorkspaceSessionId = workspaceSessionRef.current
    if (previousWorkspaceSessionId === workspaceSessionId) return

    if (previousWorkspaceSessionId) {
      saveWorkspaceChatSession(previousWorkspaceSessionId, {
        messages,
        history,
        historyId,
        serverChatId
      })
    }

    const nextSession = getWorkspaceChatSession(workspaceSessionId)
    if (nextSession) {
      setMessages(nextSession.messages)
      setHistory(nextSession.history)
      setHistoryId(nextSession.historyId, { preserveServerChatId: true })
      setServerChatId(nextSession.serverChatId)
    } else {
      setMessages([])
      setHistory([])
      setHistoryId(null, { preserveServerChatId: true })
      setServerChatId(null)
    }

    setStreaming(false)
    setIsProcessing(false)
    setSubmitError(null)
    workspaceSessionRef.current = workspaceSessionId
  }, [
    workspaceSessionId,
    getWorkspaceChatSession,
    history,
    historyId,
    messages,
    saveWorkspaceChatSession,
    serverChatId,
    setHistory,
    setHistoryId,
    setIsProcessing,
    setMessages,
    setServerChatId,
    setStreaming
  ])

  React.useEffect(() => {
    const targetMessageId = chatFocusTarget?.messageId
    if (!targetMessageId) return

    const targetElement = chatMessageItemRefs.current[targetMessageId]
    if (!targetElement) {
      clearChatFocusTarget()
      return
    }

    const revealTimer = window.setTimeout(() => {
      targetElement.scrollIntoView({ behavior: "smooth", block: "nearest" })
      setHighlightedChatMessageId(targetMessageId)
    }, 0)
    const highlightTimer = window.setTimeout(() => {
      setHighlightedChatMessageId((current) =>
        current === targetMessageId ? null : current
      )
    }, 1800)

    clearChatFocusTarget()

    return () => {
      window.clearTimeout(revealTimer)
      window.clearTimeout(highlightTimer)
    }
  }, [chatFocusTarget, clearChatFocusTarget])

  const handleSubmit = async (message: string) => {
    setSubmitError(null)
    try {
      await onSubmit({ message, image: "" })
    } catch {
      setSubmitError(
        t(
          "playground:chat.connectionError",
          "Unable to reach server. Please check your connection and retry."
        )
      )
    }
  }

  React.useEffect(() => {
    if (typeof window === "undefined") return

    const onDiscussArtifact = (event: Event) => {
      const customEvent = event as CustomEvent<WorkspaceDiscussArtifactDetail>
      const detail = customEvent.detail
      if (!detail || typeof detail.content !== "string") return

      const trimmedContent = detail.content.trim()
      if (!trimmedContent) return
      const excerpt =
        trimmedContent.length > 6000
          ? `${trimmedContent.slice(0, 6000)}\n\n[truncated]`
          : trimmedContent

      const prompt = [
        `I generated this ${detail.artifactType.replaceAll("_", " ")} in Studio:`,
        `Title: ${detail.title}`,
        "",
        excerpt,
        "",
        "Please review it, identify gaps, and suggest concrete improvements."
      ].join("\n")

      void handleSubmit(prompt)
    }

    window.addEventListener(WORKSPACE_DISCUSS_EVENT, onDiscussArtifact)
    return () => {
      window.removeEventListener(WORKSPACE_DISCUSS_EVENT, onDiscussArtifact)
    }
  }, [handleSubmit])

  const handleDropZoneDragOver = React.useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      const hasWorkspaceSource =
        event.dataTransfer.types.includes(WORKSPACE_SOURCE_DRAG_TYPE) ||
        Boolean(event.dataTransfer.getData(WORKSPACE_SOURCE_DRAG_TYPE))
      if (!hasWorkspaceSource) return
      event.preventDefault()
      event.dataTransfer.dropEffect = "copy"
      if (!dropZoneActive) {
        setDropZoneActive(true)
      }
    },
    [dropZoneActive]
  )

  const handleDropZoneDragLeave = React.useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      const nextTarget = event.relatedTarget as Node | null
      if (nextTarget && event.currentTarget.contains(nextTarget)) {
        return
      }
      setDropZoneActive(false)
    },
    []
  )

  const handleDropZoneDrop = React.useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      setDropZoneActive(false)

      const payload = parseWorkspaceSourceDragPayload(
        event.dataTransfer.getData(WORKSPACE_SOURCE_DRAG_TYPE)
      )
      if (!payload) return

      setSelectedSourceIds([payload.sourceId])
      setPreferredChatMode("rag")

      const promptTemplate = t(
        "playground:chat.dragPromptTemplate",
        'Focus on "{{title}}" only. Summarize key findings and cite supporting evidence.',
        { title: payload.title }
      ).replace("{{title}}", payload.title)
      setSeededPrompt(promptTemplate)
      messageApi.info({
        duration: 3,
        content: t(
          "playground:chat.dragScopedInfo",
          'Scoped chat context to "{{title}}".',
          { title: payload.title }
        ).replace("{{title}}", payload.title)
      })
    },
    [messageApi, setSelectedSourceIds, t]
  )

  const handleClearChat = () => {
    if (!hasMessages) return

    Modal.confirm({
      title: t("playground:chat.clearTitle", "Clear chat?"),
      content: t(
        "playground:chat.clearMessage",
        "This will remove all messages in this workspace chat."
      ),
      okText: t("common:clear", "Clear"),
      cancelText: t("common:cancel", "Cancel"),
      onOk: () => {
        setMessages([])
        setHistory([])
        setHistoryId(null, { preserveServerChatId: true })
        setServerChatId(null)
        setStreaming(false)
        setIsProcessing(false)
        setSubmitError(null)
        saveWorkspaceChatSession(workspaceSessionId, {
          messages: [],
          history: [],
          historyId: null,
          serverChatId: null
        })
      }
    })
  }

  const handleRetryConnection = async () => {
    setSubmitError(null)
    await checkConnectionOnce()
  }

  const handleCitationSourceClick = React.useCallback(
    (citation: unknown) => {
      const citationMediaId = extractCitationMediaId(citation)
      if (citationMediaId !== null && focusSourceByMediaId(citationMediaId)) {
        return
      }

      const matchedSourceId = findSourceIdFromCitation(citation, sources)
      if (matchedSourceId) {
        focusSourceById(matchedSourceId)
      }
    },
    [focusSourceById, focusSourceByMediaId, sources]
  )

  const loadLorebookActivity = React.useCallback(async () => {
    if (!serverChatId) {
      setLorebookActivityTurns([])
      setLorebookActivityTotal(0)
      setLorebookActivityLoading(false)
      setLorebookActivityError(null)
      setLorebookActivityForbidden(false)
      return
    }

    setLorebookActivityLoading(true)
    setLorebookActivityError(null)
    setLorebookActivityForbidden(false)
    try {
      const response = await tldwClient.getChatLorebookDiagnostics(serverChatId, {
        page: 1,
        size: LOREBOOK_ACTIVITY_PAGE_SIZE,
        order: "desc"
      })
      const turns = Array.isArray(response?.turns) ? response.turns : []
      const normalizedTurns: LorebookActivityTurn[] = turns
        .slice(0, LOREBOOK_ACTIVITY_PAGE_SIZE)
        .map((turn: any) => ({
        turnNumber:
          typeof turn?.turn_number === "number"
            ? turn.turn_number
            : Number(turn?.turn_number || 0),
        assistantPreview: String(turn?.message_preview || ""),
        entryCount: Array.isArray(turn?.diagnostics) ? turn.diagnostics.length : 0
      }))
      setLorebookActivityTurns(normalizedTurns)
      setLorebookActivityTotal(
        typeof response?.total_turns_with_diagnostics === "number"
          ? response.total_turns_with_diagnostics
          : normalizedTurns.length
      )
    } catch (error: any) {
      const messageText = String(error?.message || "Failed to load lorebook activity.")
      const forbidden = /(403|forbidden|not authorized|permission)/i.test(messageText)
      setLorebookActivityForbidden(forbidden)
      setLorebookActivityError(messageText)
      setLorebookActivityTurns([])
      setLorebookActivityTotal(0)
    } finally {
      setLorebookActivityLoading(false)
    }
  }, [serverChatId])

  const handleExportLorebookActivity = React.useCallback(async () => {
    if (!serverChatId || exportingLorebookActivity) return
    setExportingLorebookActivity(true)
    try {
      const response = await tldwClient.getChatLorebookDiagnostics(serverChatId, {
        page: 1,
        size: LOREBOOK_ACTIVITY_EXPORT_PAGE_SIZE,
        order: "asc"
      })
      const payload = {
        exported_at: new Date().toISOString(),
        chat_id: String(serverChatId),
        total_turns_with_diagnostics: response?.total_turns_with_diagnostics || 0,
        turns: Array.isArray(response?.turns) ? response.turns : []
      }
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json;charset=utf-8"
      })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `lorebook-activity-${String(serverChatId)}.json`
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (error: any) {
      messageApi.error(
        error?.message || "Failed to export lorebook activity diagnostics."
      )
    } finally {
      setExportingLorebookActivity(false)
    }
  }, [exportingLorebookActivity, messageApi, serverChatId])

  React.useEffect(() => {
    if (!hasMessages || !serverChatId) {
      setLorebookActivityTurns([])
      setLorebookActivityTotal(0)
      setLorebookActivityLoading(false)
      setLorebookActivityError(null)
      setLorebookActivityForbidden(false)
      return
    }
    void loadLorebookActivity()
  }, [hasMessages, loadLorebookActivity, serverChatId])

  const handleSaveMessageToNotes = React.useCallback(
    (msg: {
      isBot: boolean
      message: string
      name?: string
    }) => {
      const snippet = String(msg.message || "").trim()
      if (!snippet) return
      captureToCurrentNote({
        title: buildCapturedMessageTitle(
          msg.isBot,
          snippet,
          t("playground:chat.savedAssistantPrefix", "Assistant"),
          t("playground:chat.savedUserPrefix", "User")
        ),
        content: snippet,
        mode: "append"
      })
    },
    [captureToCurrentNote, t]
  )

  // Conversation instance ID (use workspace ID or fallback)
  const conversationInstanceId =
    workspaceChatReferenceId || workspaceId || WORKSPACE_CONVERSATION_ID
  const showConnectionBanner =
    submitError !== null ||
    (connectionState.phase === ConnectionPhase.ERROR &&
      !connectionState.isChecking)
  const connectionDescription =
    submitError ||
    connectionState.lastError ||
    t(
      "playground:chat.connectionErrorGeneric",
      "Unable to reach server. Please retry."
    )

  return (
    <div className="flex h-full flex-col">
      {messageContextHolder}

      {/* Context indicator */}
      <ChatContextIndicator />

      {/* Connection banner */}
      {showConnectionBanner && (
        <div className="border-b border-error/30 bg-error/5 px-4 py-2">
          <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2 text-sm text-error">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span className="truncate">
                {t("playground:chat.connectionBanner", "Unable to reach server")}
                : {connectionDescription}
              </span>
            </div>
            <button
              type="button"
              onClick={() => {
                void handleRetryConnection()
              }}
              className="shrink-0 rounded border border-error/40 bg-surface px-2 py-1 text-xs font-medium text-error transition hover:bg-error/10"
            >
              <RotateCcw className="mr-1 inline h-3.5 w-3.5" />
              {t("common:retry", "Retry")}
            </button>
          </div>
        </div>
      )}

      {/* Chat controls */}
      <div className="border-b border-border bg-surface px-4 py-2">
        <div className="mx-auto flex max-w-3xl items-center justify-end">
          <button
            type="button"
            onClick={handleClearChat}
            disabled={!hasMessages}
            className="rounded p-1.5 text-text-muted transition hover:bg-surface2 hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
            aria-label={t("playground:chat.clearChat", "Clear chat")}
            title={t("playground:chat.clearChat", "Clear chat") as string}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {hasMessages && (
        <div className="border-b border-border bg-surface px-4 py-2">
          <div className="mx-auto max-w-3xl space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-medium text-text">Lorebook Activity</p>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => void loadLorebookActivity()}
                  className="rounded border border-border px-2 py-1 text-xs text-text-muted transition hover:border-primary/40 hover:text-text"
                >
                  Refresh
                </button>
                <button
                  type="button"
                  onClick={() => void handleExportLorebookActivity()}
                  disabled={!serverChatId || exportingLorebookActivity}
                  className="rounded border border-border px-2 py-1 text-xs text-text-muted transition hover:border-primary/40 hover:text-text disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {exportingLorebookActivity ? "Exporting…" : "Export"}
                </button>
                <a
                  href={LOREBOOK_DEBUG_ENTRYPOINT_HREF}
                  className="text-xs text-primary hover:underline"
                  aria-label="Open full lorebook diagnostics"
                >
                  View Full Diagnostics
                </a>
              </div>
            </div>

            {!serverChatId && (
              <p className="text-xs text-text-muted">
                Lorebook activity appears once this chat is saved to server.
              </p>
            )}

            {serverChatId && lorebookActivityLoading && (
              <p className="text-xs text-text-muted">Loading lorebook activity…</p>
            )}

            {serverChatId && lorebookActivityError && (
              <p className="text-xs text-danger">
                {lorebookActivityForbidden
                  ? "Lorebook activity is unavailable for this account."
                  : lorebookActivityError}
              </p>
            )}

            {serverChatId &&
              !lorebookActivityLoading &&
              !lorebookActivityError &&
              lorebookActivityTurns.length === 0 && (
                <p className="text-xs text-text-muted">
                  No lorebook entries have fired yet for this chat.
                </p>
              )}

            {serverChatId &&
              !lorebookActivityLoading &&
              !lorebookActivityError &&
              lorebookActivityTurns.length > 0 && (
                <div className="space-y-1">
                  {lorebookActivityTurns.map((turn) => (
                    <div
                      key={`lorebook-turn-${turn.turnNumber}`}
                      className="rounded border border-border px-2 py-1"
                    >
                      <p className="text-xs font-medium text-text">
                        Turn {turn.turnNumber}: {turn.entryCount} entries fired
                      </p>
                      {turn.assistantPreview && (
                        <p className="line-clamp-2 text-xs text-text-muted">
                          {turn.assistantPreview}
                        </p>
                      )}
                    </div>
                  ))}
                  {lorebookActivityTotal > lorebookActivityTurns.length && (
                    <p className="text-[11px] text-text-muted">
                      Showing {lorebookActivityTurns.length} of {lorebookActivityTotal} turns with diagnostics.
                    </p>
                  )}
                </div>
              )}
          </div>
        </div>
      )}

      {/* Chat messages area */}
      <div className="relative flex min-h-0 flex-1 flex-col">
        <div
          ref={containerRef}
          role="log"
          aria-live="polite"
          aria-relevant="additions"
          aria-label={t("playground:aria.chatTranscript", "Chat messages")}
          className="custom-scrollbar min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-4"
        >
          <div className="mx-auto w-full max-w-3xl pb-6">
            {hasMessages ? (
              <div className="space-y-4 py-4">
                {messages.map((msg, idx) => {
                  const diagnostics = msg.isBot
                    ? buildRetrievalDiagnostics(msg.sources, msg.generationInfo)
                    : null
                  const chatSearchMessageId = getWorkspaceChatSearchMessageId(
                    msg,
                    idx
                  )
                  const isHighlighted =
                    highlightedChatMessageId === chatSearchMessageId

                  return (
                    <div
                      key={msg.id || `msg-${idx}`}
                      data-chat-message-id={chatSearchMessageId}
                      ref={(element) => {
                        chatMessageItemRefs.current[chatSearchMessageId] = element
                      }}
                      className={`space-y-2 rounded-md transition ${
                        isHighlighted ? "ring-2 ring-primary/40 bg-primary/5 p-1.5" : ""
                      }`}
                    >
                      <PlaygroundMessage
                        isBot={msg.isBot}
                        message={msg.message}
                        name={msg.name}
                        images={msg.images}
                        generationInfo={msg.generationInfo}
                        sources={msg.sources}
                        toolCalls={msg.toolCalls}
                        toolResults={msg.toolResults}
                        reasoningTimeTaken={msg.reasoning_time_taken}
                        currentMessageIndex={idx}
                        totalMessages={messages.length}
                        isProcessing={isProcessing}
                        isStreaming={streaming && idx === messages.length - 1}
                        conversationInstanceId={conversationInstanceId}
                        historyId={historyId || undefined}
                        serverChatId={serverChatId}
                        serverMessageId={msg.serverMessageId}
                        messageId={msg.id}
                        discoSkillComment={msg.discoSkillComment}
                        createdAt={msg.createdAt}
                        variants={msg.variants}
                        activeVariantIndex={msg.activeVariantIndex}
                        modelName={msg.modelName}
                        modelImage={msg.modelImage}
                        onSourceClick={handleCitationSourceClick}
                        onSaveToWorkspaceNotes={() =>
                          handleSaveMessageToNotes({
                            isBot: msg.isBot,
                            message: msg.message,
                            name: msg.name
                          })
                        }
                        onRegenerate={
                          msg.isBot && idx === messages.length - 1
                            ? () => regenerateLastMessage()
                            : () => {}
                        }
                        onDeleteMessage={() => deleteMessage(idx)}
                        onEditFormSubmit={(value, isSend) => {
                          editMessage(idx, value, !msg.isBot, isSend)
                        }}
                        hideEditAndRegenerate={!msg.isBot && idx !== messages.length - 1}
                        hideContinue={true}
                        temporaryChat={false}
                      />
                      {msg.isBot && diagnostics && (
                        <div className="px-2">
                          <RetrievalDiagnosticsPanel diagnostics={diagnostics} />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              <WorkspaceChatEmpty
                hasSelectedSources={hasSelectedSources}
                sourceCount={selectedSources.length}
                selectedSourceTypes={selectedSources.map((source) => source.type)}
                isMobile={isMobile}
              />
            )}
          </div>
        </div>

        {/* Scroll to bottom button */}
        {!isAutoScrollToBottom && hasMessages && (
          <div className="pointer-events-none absolute bottom-24 left-0 right-0 flex justify-center">
            <button
              onClick={() => autoScrollToBottom()}
              aria-label={t(
                "playground:composer.scrollToLatest",
                "Scroll to latest messages"
              )}
              title={
                t(
                  "playground:composer.scrollToLatest",
                  "Scroll to latest messages"
                ) as string
              }
              className="pointer-events-auto rounded-full border border-border bg-surface p-2 text-text-subtle shadow-card transition-colors hover:bg-surface2 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              <ChevronDown className="size-4 text-text-subtle" aria-hidden="true" />
            </button>
          </div>
        )}
      </div>

      {/* Chat input */}
      <div
        data-testid="chat-drop-zone"
        data-drop-active={dropZoneActive ? "true" : "false"}
        onDragOver={handleDropZoneDragOver}
        onDrop={handleDropZoneDrop}
        onDragLeave={handleDropZoneDragLeave}
        className={`sticky bottom-0 border-t border-border bg-surface transition-colors ${
          dropZoneActive ? "bg-primary/5" : ""
        }`}
      >
        <div className="mx-auto max-w-3xl px-4 py-3">
          {dropZoneActive && (
            <div className="mb-2 rounded-md border border-primary/40 bg-primary/10 px-3 py-2 text-xs text-primary">
              {t(
                "playground:chat.dropZoneHint",
                "Drop source to scope chat and start a source-specific question."
              )}
            </div>
          )}
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <div className="inline-flex rounded-md border border-border bg-surface2 p-0.5">
              <button
                type="button"
                onClick={() => setPreferredChatMode("normal")}
                className={`rounded px-2.5 py-1 text-xs font-medium transition ${
                  effectiveChatMode === "normal"
                    ? "bg-primary text-white"
                    : "text-text-muted hover:text-text"
                }`}
                aria-pressed={effectiveChatMode === "normal"}
              >
                {t("playground:chat.generalMode", "General chat")}
              </button>
              <Tooltip
                title={
                  hasSelectedSources
                    ? undefined
                    : t(
                        "playground:chat.ragModeRequiresSources",
                        "Select sources to enable RAG mode"
                      )
                }
              >
                <button
                  type="button"
                  disabled={!hasSelectedSources}
                  onClick={() => setPreferredChatMode("rag")}
                  className={`rounded px-2.5 py-1 text-xs font-medium transition ${
                    effectiveChatMode === "rag"
                      ? "bg-primary text-white"
                      : "text-text-muted hover:text-text"
                  } disabled:cursor-not-allowed disabled:opacity-50`}
                  aria-pressed={effectiveChatMode === "rag"}
                >
                  {t("playground:chat.ragMode", "RAG mode")}
                </button>
              </Tooltip>
            </div>
            <div className="flex items-center gap-2">
              {preferredChatMode !== null && (
                <button
                  type="button"
                  onClick={() => setPreferredChatMode(null)}
                  className="text-xs text-text-muted transition hover:text-text hover:underline"
                >
                  {t("playground:chat.modeAuto", "Auto")}
                </button>
              )}
              {hasSelectedSources && (
                <button
                  type="button"
                  onClick={() =>
                    setShowAdvancedRagSettings((current) => !current)
                  }
                  className="inline-flex items-center gap-1 rounded border border-border bg-surface2 px-2 py-1 text-xs text-text-muted transition hover:bg-surface hover:text-text"
                  aria-expanded={showAdvancedRagSettings}
                >
                  <SlidersHorizontal className="h-3.5 w-3.5" />
                  {t(
                    "playground:chat.advancedRagSettings",
                    "Advanced RAG settings"
                  )}
                </button>
              )}
            </div>
          </div>
          {hasSelectedSources && effectiveChatMode === "normal" && (
            <p className="mb-2 text-xs text-warn">
              {t(
                "playground:chat.generalModeWithSourcesHint",
                "General chat mode is active. Selected sources will not be used unless RAG mode is enabled."
              )}
            </p>
          )}
          {hasSelectedSources && showAdvancedRagSettings && (
            <div className="mb-3 rounded-md border border-border bg-surface2/40 p-3">
              <div className="space-y-3">
                <div>
                  <div className="mb-1 flex items-center justify-between text-xs text-text-muted">
                    <span>{t("playground:chat.ragTopK", "Top K")}</span>
                    <span className="font-medium text-text">{resolvedTopK}</span>
                  </div>
                  <Slider
                    min={1}
                    max={50}
                    step={1}
                    value={resolvedTopK}
                    onChange={handleTopKChange}
                  />
                </div>
                <div>
                  <div className="mb-1 flex items-center justify-between text-xs text-text-muted">
                    <span>
                      {t(
                        "playground:chat.ragSimilarityThreshold",
                        "Similarity threshold"
                      )}
                    </span>
                    <span className="font-medium text-text">
                      {similarityThreshold.toFixed(2)}
                    </span>
                  </div>
                  <Slider
                    min={0}
                    max={1}
                    step={0.01}
                    value={similarityThreshold}
                    onChange={handleSimilarityThresholdChange}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">
                    {t("playground:chat.ragReranking", "Enable reranking")}
                  </span>
                  <Switch
                    size="small"
                    checked={rerankingEnabled}
                    onChange={handleRerankingToggle}
                  />
                </div>
              </div>
            </div>
          )}
          <SimpleChatInput
            onSubmit={handleSubmit}
            onStop={stopStreamingRequest}
            isLoading={streaming}
            seededValue={seededPrompt}
            onSeedConsumed={() => setSeededPrompt(null)}
            placeholder={
              hasSelectedSources
                ? t(
                    "playground:chat.inputPlaceholderWithSources",
                    "Ask about your sources..."
                  )
                : t(
                    "playground:chat.inputPlaceholder",
                    "Type a message..."
                  )
            }
          />
        </div>
      </div>
    </div>
  )
}

export default ChatPane
