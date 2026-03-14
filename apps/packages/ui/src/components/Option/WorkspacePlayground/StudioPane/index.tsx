import React, { useState, useEffect, useRef } from "react"
import { useTranslation } from "react-i18next"
import {
  Headphones,
  FileText,
  GitBranch,
  FileSpreadsheet,
  Layers,
  HelpCircle,
  Scale,
  Calendar,
  Presentation,
  Table as TableIconLucide,
  Loader2,
  CheckCircle,
  XCircle,
  Eye,
  Download,
  RefreshCw,
  Square,
  MessageCircle,
  StickyNote,
  Pencil,
  Plus,
  Save,
  Search,
  ZoomIn,
  ZoomOut,
  Trash2,
  ChevronDown,
  ChevronUp,
  Settings2,
  PanelRightClose
} from "lucide-react"
import {
  Button,
  Empty,
  Tooltip,
  Input,
  Modal,
  message,
  Slider,
  Select,
  Dropdown,
  Switch,
  Table as AntTable
} from "antd"
import { useMobile } from "@/hooks/useMediaQuery"
import { useWorkspaceStore } from "@/store/workspace"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { tldwModels, type ModelInfo } from "@/services/tldw"
import { trackWorkspacePlaygroundTelemetry } from "@/utils/workspace-playground-telemetry"
import { generateQuiz } from "@/services/quizzes"
import { createFlashcard, createDeck, listDecks } from "@/services/flashcards"
import { fetchTldwVoiceCatalog, type TldwVoice } from "@/services/tldw/audio-voices"
import { inferTldwProviderFromModel } from "@/services/tts-provider"
import { OUTPUT_TYPES } from "@/types/workspace"
import type { ArtifactType, GeneratedArtifact, AudioTtsProvider } from "@/types/workspace"
import { useStoreMessageOption } from "@/store/option"
import { useStoreChatModelSettings } from "@/store/model"
import Mermaid from "@/components/Common/Mermaid"
import { QuickNotesSection } from "./QuickNotesSection"
import { getWorkspaceStudioNoSourcesHint } from "../source-location-copy"
import {
  WORKSPACE_UNDO_WINDOW_MS,
  scheduleWorkspaceUndoAction,
  undoWorkspaceAction
} from "../undo-manager"

// Icon mapping for artifact types
const ARTIFACT_TYPE_ICONS: Record<ArtifactType, React.ElementType> = {
  audio_overview: Headphones,
  summary: FileText,
  mindmap: GitBranch,
  report: FileSpreadsheet,
  compare_sources: Scale,
  flashcards: Layers,
  quiz: HelpCircle,
  timeline: Calendar,
  slides: Presentation,
  data_table: TableIconLucide
}

// Output type button configuration
const OUTPUT_BUTTONS: {
  type: ArtifactType
  label: string
  description: string
  icon: React.ElementType
}[] = [
  {
    type: "audio_overview",
    label: "Audio Summary",
    description:
      OUTPUT_TYPES.find((config) => config.type === "audio_overview")
        ?.description || "Generate a spoken summary of your sources",
    icon: Headphones
  },
  {
    type: "summary",
    label: "Summary",
    description:
      OUTPUT_TYPES.find((config) => config.type === "summary")?.description ||
      "Create a concise summary of key points",
    icon: FileText
  },
  {
    type: "mindmap",
    label: "Mind Map",
    description:
      OUTPUT_TYPES.find((config) => config.type === "mindmap")?.description ||
      "Visualize concepts and relationships",
    icon: GitBranch
  },
  {
    type: "report",
    label: "Report",
    description:
      OUTPUT_TYPES.find((config) => config.type === "report")?.description ||
      "Generate a detailed report document",
    icon: FileSpreadsheet
  },
  {
    type: "compare_sources",
    label: "Compare Sources",
    description:
      OUTPUT_TYPES.find((config) => config.type === "compare_sources")
        ?.description ||
      "Compare claims, evidence, and disagreements across selected sources",
    icon: Scale
  },
  {
    type: "flashcards",
    label: "Flashcards",
    description:
      OUTPUT_TYPES.find((config) => config.type === "flashcards")?.description ||
      "Create study flashcards for review",
    icon: Layers
  },
  {
    type: "quiz",
    label: "Quiz",
    description:
      OUTPUT_TYPES.find((config) => config.type === "quiz")?.description ||
      "Generate a quiz to test understanding",
    icon: HelpCircle
  },
  {
    type: "timeline",
    label: "Timeline",
    description:
      OUTPUT_TYPES.find((config) => config.type === "timeline")?.description ||
      "Create a chronological timeline",
    icon: Calendar
  },
  {
    type: "slides",
    label: "Slides",
    description:
      OUTPUT_TYPES.find((config) => config.type === "slides")?.description ||
      "Generate presentation slides",
    icon: Presentation
  },
  {
    type: "data_table",
    label: "Data Table",
    description:
      OUTPUT_TYPES.find((config) => config.type === "data_table")
        ?.description || "Extract structured data into a table",
    icon: TableIconLucide
  }
]

const OUTPUT_GROUPS: Array<{
  id: string
  label: string
  types: ArtifactType[]
}> = [
  {
    id: "study-aids",
    label: "Study Aids",
    types: ["quiz", "flashcards"]
  },
  {
    id: "analysis",
    label: "Analysis",
    types: ["summary", "report", "compare_sources", "timeline", "data_table"]
  },
  {
    id: "creative",
    label: "Creative",
    types: ["mindmap", "slides", "audio_overview"]
  }
]

// Status icons for artifacts
const STATUS_ICONS: Record<
  GeneratedArtifact["status"],
  { icon: React.ElementType; className: string }
> = {
  pending: { icon: Loader2, className: "text-text-muted animate-spin" },
  generating: { icon: Loader2, className: "text-primary animate-spin" },
  completed: { icon: CheckCircle, className: "text-success" },
  failed: { icon: XCircle, className: "text-error" }
}

// TTS Provider configurations
const TTS_PROVIDERS: { value: AudioTtsProvider; label: string }[] = [
  { value: "tldw", label: "tldw Server" },
  { value: "openai", label: "OpenAI" },
  { value: "browser", label: "Browser" }
]

const TLDW_TTS_MODELS = [
  { value: "kokoro", label: "Kokoro" }
]

const OPENAI_TTS_MODELS = [
  { value: "tts-1", label: "tts-1" },
  { value: "tts-1-hd", label: "tts-1-hd" }
]

const OPENAI_TTS_VOICES = [
  { value: "alloy", label: "Alloy" },
  { value: "echo", label: "Echo" },
  { value: "fable", label: "Fable" },
  { value: "onyx", label: "Onyx" },
  { value: "nova", label: "Nova" },
  { value: "shimmer", label: "Shimmer" }
]

const AUDIO_FORMATS: { value: string; label: string }[] = [
  { value: "mp3", label: "MP3" },
  { value: "wav", label: "WAV" },
  { value: "opus", label: "Opus" },
  { value: "aac", label: "AAC" },
  { value: "flac", label: "FLAC" }
]

// Slides export formats
const SLIDES_EXPORT_FORMATS: { value: string; label: string; ext: string }[] = [
  { value: "revealjs", label: "Reveal.js (ZIP)", ext: "zip" },
  { value: "markdown", label: "Markdown", ext: "md" },
  { value: "pdf", label: "PDF", ext: "pdf" },
  { value: "json", label: "JSON", ext: "json" }
]

interface StudioPaneProps {
  /** Callback to hide/collapse the pane */
  onHide?: () => void
}

type RegenerateMode = "replace" | "new_version"

type ArtifactGenerationOptions = {
  mode?: RegenerateMode
  targetArtifactId?: string
}

type FlashcardDraft = {
  front: string
  back: string
}

type QuizQuestionDraft = {
  question: string
  options: string[]
  answer: string
  explanation?: string
}

type ParsedQuizQuestion = {
  question: string
  options: string[]
  answer: string
  explanation: string
}

type MarkdownTableData = {
  headers: string[]
  rows: string[][]
}

type ArtifactDiscussDetail = {
  artifactId: string
  artifactType: ArtifactType
  title: string
  content: string
}

const RECENT_OUTPUT_TYPES_STORAGE_KEY = "tldw:workspace-playground:recent-output-types:v1"
const RECENT_OUTPUT_TYPES_COUNT = 3
const WORKSPACE_DISCUSS_EVENT = "workspace-playground:discuss-artifact"
const VOICE_PREVIEW_TEXT =
  "This is a quick voice preview from your current audio settings."
const OUTPUT_VIRTUALIZATION_THRESHOLD = 50
const OUTPUT_VIRTUAL_ROW_HEIGHT = 150
const OUTPUT_VIRTUAL_OVERSCAN = 4
const STUDIO_GENERATION_RAG_TIMEOUT_MS = 120000
const STUDIO_DEFAULT_RAG_TOP_K = 8
const STUDIO_DEFAULT_RAG_MIN_SCORE = 0.2
const STUDIO_DEFAULT_ENABLE_RERANKING = true
const STUDIO_DEFAULT_MAX_TOKENS = 800

const loadRecentOutputTypes = (): ArtifactType[] => {
  try {
    const raw = localStorage.getItem(RECENT_OUTPUT_TYPES_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    const validTypes = new Set(OUTPUT_BUTTONS.map((b) => b.type))
    return parsed.filter(
      (item): item is ArtifactType =>
        typeof item === "string" && validTypes.has(item as ArtifactType)
    )
  } catch {
    return []
  }
}

const recordRecentOutputType = (type: ArtifactType): ArtifactType[] => {
  const current = loadRecentOutputTypes()
  const updated = [type, ...current.filter((t) => t !== type)].slice(0, 10)
  try {
    localStorage.setItem(RECENT_OUTPUT_TYPES_STORAGE_KEY, JSON.stringify(updated))
  } catch {
    // Quota exceeded — silent
  }
  return updated
}

const isAbortLikeError = (error: unknown): boolean => {
  const candidate = (error as {
    name?: string
    message?: string
    code?: string
  } | null) ?? { message: String(error ?? "") }

  if (candidate.name === "AbortError") {
    return true
  }

  if (
    typeof candidate.code === "string" &&
    /^(REQUEST_ABORTED|ERR_CANCELED|ERR_CANCELLED)$/i.test(candidate.code)
  ) {
    return true
  }

  const message = candidate.message ?? String(error ?? "")
  return /\babort(ed|error)?\b/i.test(message)
}

const TEXT_FAILURE_SENTINELS: Partial<Record<ArtifactType, string[]>> = {
  summary: ["Summary generation failed"],
  report: ["Report generation failed"],
  compare_sources: ["Compare sources generation failed"],
  timeline: ["Timeline generation failed"],
  mindmap: ["Mind map generation failed"],
  slides: ["Slides generation failed"],
  data_table: ["Data table generation failed"]
}

const KNOWN_ERROR_RESPONSE_TEXTS = new Set([
  "sorry, i encountered an error. please try again.",
  "i'm sorry, i encountered an error processing your request.",
  "i encountered an error generating a response.",
  "the workflow encountered an error."
])

export const estimateGenerationSeconds = (
  type: ArtifactType,
  sourceCount: number
): number => {
  const normalizedSourceCount = Math.max(1, sourceCount)
  const baseSeconds: Record<ArtifactType, number> = {
    summary: 8,
    report: 16,
    compare_sources: 18,
    timeline: 12,
    quiz: 10,
    flashcards: 10,
    mindmap: 12,
    audio_overview: 24,
    slides: 20,
    data_table: 14
  }
  const perSourceSeconds: Record<ArtifactType, number> = {
    summary: 2,
    report: 4,
    compare_sources: 5,
    timeline: 3,
    quiz: 2,
    flashcards: 2,
    mindmap: 3,
    audio_overview: 5,
    slides: 4,
    data_table: 3
  }
  return Math.round(
    baseSeconds[type] + perSourceSeconds[type] * (normalizedSourceCount - 1)
  )
}

const ESTIMATED_COST_PER_1K_TOKENS_USD = 0.003

export const estimateGenerationTokens = (
  type: ArtifactType,
  sourceCount: number
): number => {
  const normalizedSourceCount = Math.max(1, sourceCount)
  const baseTokens: Record<ArtifactType, number> = {
    summary: 1200,
    report: 2200,
    compare_sources: 2400,
    timeline: 1500,
    quiz: 1400,
    flashcards: 1300,
    mindmap: 1500,
    audio_overview: 2600,
    slides: 2400,
    data_table: 1800
  }
  const perSourceTokens: Record<ArtifactType, number> = {
    summary: 350,
    report: 700,
    compare_sources: 800,
    timeline: 450,
    quiz: 400,
    flashcards: 350,
    mindmap: 450,
    audio_overview: 900,
    slides: 800,
    data_table: 550
  }

  return Math.max(
    200,
    Math.round(
      baseTokens[type] + perSourceTokens[type] * (normalizedSourceCount - 1)
    )
  )
}

export const estimateGenerationCostUsd = (tokens: number): number => {
  const safeTokens = Math.max(0, Number(tokens) || 0)
  return Number(((safeTokens / 1000) * ESTIMATED_COST_PER_1K_TOKENS_USD).toFixed(4))
}

type UsageMetrics = {
  totalTokens?: number
  totalCostUsd?: number
}

type GenerationResult = {
  serverId?: number | string
  content?: string
  audioUrl?: string
  audioFormat?: string
  presentationId?: string
  presentationVersion?: number
  totalTokens?: number
  totalCostUsd?: number
  data?: Record<string, unknown>
}

const extractUsageMetrics = (payload: unknown): UsageMetrics => {
  if (!payload || typeof payload !== "object") {
    return {}
  }
  const candidate = payload as Record<string, unknown>
  const usage = (candidate.usage || candidate.generation_info || candidate.generationInfo) as
    | Record<string, unknown>
    | undefined
  const usagePayload = (usage?.usage as Record<string, unknown> | undefined) || usage

  const totalTokensValue =
    usagePayload?.total_tokens ||
    usagePayload?.totalTokens ||
    usagePayload?.tokens ||
    usagePayload?.token_count
  const totalCostValue =
    usagePayload?.total_cost_usd ||
    usagePayload?.totalCostUsd ||
    usagePayload?.estimated_cost_usd ||
    usagePayload?.cost_usd

  const totalTokens =
    typeof totalTokensValue === "number"
      ? Math.max(0, Math.round(totalTokensValue))
      : typeof totalTokensValue === "string"
        ? Math.max(0, Math.round(Number(totalTokensValue) || 0))
        : undefined
  const totalCostUsd =
    typeof totalCostValue === "number"
      ? Math.max(0, totalCostValue)
      : typeof totalCostValue === "string"
        ? Math.max(0, Number(totalCostValue) || 0)
        : undefined

  return {
    totalTokens:
      typeof totalTokens === "number" && Number.isFinite(totalTokens)
        ? totalTokens
        : undefined,
    totalCostUsd:
      typeof totalCostUsd === "number" && Number.isFinite(totalCostUsd)
        ? Number(totalCostUsd.toFixed(4))
        : undefined
  }
}

const buildMissingContentError = (label: string): Error =>
  new Error(`No usable ${label} content was returned.`)

const extractRequiredRagText = (response: unknown, label: string): string => {
  const candidate = isRecord(response) ? response : {}
  const generation =
    typeof candidate.generation === "string" ? candidate.generation.trim() : ""
  const generatedAnswer =
    typeof candidate.generated_answer === "string"
      ? candidate.generated_answer.trim()
      : ""
  const answer = typeof candidate.answer === "string" ? candidate.answer.trim() : ""
  const responseText =
    typeof candidate.response === "string" ? candidate.response.trim() : ""
  const text = generation || generatedAnswer || answer || responseText

  if (!text) {
    throw buildMissingContentError(label)
  }

  return text
}

const requireUsableTextResult = (
  type: ArtifactType,
  result: GenerationResult,
  label: string
): GenerationResult => {
  const content = typeof result.content === "string" ? result.content.trim() : ""
  const sentinels = TEXT_FAILURE_SENTINELS[type] ?? []
  const normalizedContent = content.toLowerCase()

  if (
    !content ||
    sentinels.includes(content) ||
    KNOWN_ERROR_RESPONSE_TEXTS.has(normalizedContent)
  ) {
    throw buildMissingContentError(label)
  }

  return {
    ...result,
    content
  }
}

const finalizeGenerationResult = (
  type: ArtifactType,
  result: GenerationResult,
  options?: {
    audioProvider?: AudioTtsProvider
  }
): GenerationResult => {
  switch (type) {
    case "summary":
      return requireUsableTextResult(type, result, "summary")
    case "report":
      return requireUsableTextResult(type, result, "report")
    case "compare_sources":
      return requireUsableTextResult(type, result, "comparison")
    case "timeline":
      return requireUsableTextResult(type, result, "timeline")
    case "mindmap": {
      const normalized = requireUsableTextResult(type, result, "mind map")
      const mermaid =
        isRecord(normalized.data) && typeof normalized.data.mermaid === "string"
          ? normalized.data.mermaid.trim()
          : ""
      if (!mermaid || !isLikelyMermaidDiagram(mermaid)) {
        throw buildMissingContentError("mind map")
      }
      return normalized
    }
    case "data_table": {
      const normalized = requireUsableTextResult(type, result, "data table")
      const table =
        isRecord(normalized.data) && normalized.data.table ? normalized.data.table : null
      if (!table) {
        throw buildMissingContentError("data table")
      }
      return normalized
    }
    case "slides":
      if (result.presentationId) {
        return result
      }
      return requireUsableTextResult(type, result, "slide")
    case "audio_overview": {
      const normalized = requireUsableTextResult(type, result, "audio")
      if (options?.audioProvider === "browser") {
        return normalized
      }
      if (!result.audioUrl) {
        throw new Error("No usable audio output was returned.")
      }
      return normalized
    }
    default:
      return result
  }
}

/**
 * StudioPane - Right pane for generating outputs
 */
export const StudioPane: React.FC<StudioPaneProps> = ({ onHide }) => {
  const { t } = useTranslation(["playground", "common"])
  const isMobile = useMobile()
  const [messageApi, contextHolder] = message.useMessage()

  // Store state
  const selectedSourceIds = useWorkspaceStore((s) => s.selectedSourceIds)
  const selectedSourceFolderIds = useWorkspaceStore(
    (s) => s.selectedSourceFolderIds
  ) || []
  const getSelectedMediaIds = useWorkspaceStore((s) => s.getSelectedMediaIds)
  const getEffectiveSelectedMediaIds = useWorkspaceStore(
    (s) => s.getEffectiveSelectedMediaIds
  )
  const generatedArtifacts = useWorkspaceStore((s) => s.generatedArtifacts)
  const isGeneratingOutput = useWorkspaceStore((s) => s.isGeneratingOutput)
  const generatingOutputType = useWorkspaceStore((s) => s.generatingOutputType)
  const workspaceTag = useWorkspaceStore((s) => s.workspaceTag)
  const audioSettings = useWorkspaceStore((s) => s.audioSettings)
  const noteFocusTarget = useWorkspaceStore((s) => s.noteFocusTarget)

  // Store actions
  const addArtifact = useWorkspaceStore((s) => s.addArtifact)
  const updateArtifactStatus = useWorkspaceStore((s) => s.updateArtifactStatus)
  const removeArtifact = useWorkspaceStore((s) => s.removeArtifact)
  const restoreArtifact = useWorkspaceStore((s) => s.restoreArtifact)
  const setIsGeneratingOutput = useWorkspaceStore((s) => s.setIsGeneratingOutput)
  const setAudioSettings = useWorkspaceStore((s) => s.setAudioSettings)
  const captureToCurrentNote = useWorkspaceStore((s) => s.captureToCurrentNote)

  // Workspace chat/store options
  const selectedModel = useStoreMessageOption((s) => s.selectedModel)
  const setSelectedModel = useStoreMessageOption((s) => s.setSelectedModel)
  const ragSearchMode = useStoreMessageOption((s) => s.ragSearchMode)
  const setRagSearchMode = useStoreMessageOption((s) => s.setRagSearchMode)
  const ragTopK = useStoreMessageOption((s) => s.ragTopK)
  const setRagTopK = useStoreMessageOption((s) => s.setRagTopK)
  const ragEnableGeneration = useStoreMessageOption((s) => s.ragEnableGeneration)
  const setRagEnableGeneration = useStoreMessageOption((s) => s.setRagEnableGeneration)
  const ragEnableCitations = useStoreMessageOption((s) => s.ragEnableCitations)
  const setRagEnableCitations = useStoreMessageOption((s) => s.setRagEnableCitations)
  const ragAdvancedOptions = useStoreMessageOption((s) => s.ragAdvancedOptions)
  const setRagAdvancedOptions = useStoreMessageOption((s) => s.setRagAdvancedOptions)

  const apiProvider = useStoreChatModelSettings((s) => s.apiProvider)
  const temperature = useStoreChatModelSettings((s) => s.temperature)
  const topP = useStoreChatModelSettings((s) => s.topP)
  const numPredict = useStoreChatModelSettings((s) => s.numPredict)
  const setApiProvider = useStoreChatModelSettings((s) => s.setApiProvider)
  const setTemperature = useStoreChatModelSettings((s) => s.setTemperature)
  const setTopP = useStoreChatModelSettings((s) => s.setTopP)
  const setNumPredict = useStoreChatModelSettings((s) => s.setNumPredict)
  const updateModelSetting = useStoreChatModelSettings((s) => s.updateSetting)

  // Local state for TTS settings panel
  const [showTtsSettings, setShowTtsSettings] = useState(false)
  const [tldwVoices, setTldwVoices] = useState<TldwVoice[]>([])
  const [loadingVoices, setLoadingVoices] = useState(false)
  const [previewingVoice, setPreviewingVoice] = useState(false)
  const [availableDecks, setAvailableDecks] = useState<Array<{ id: number; name: string }>>([])
  const [loadingDecks, setLoadingDecks] = useState(false)
  const [selectedFlashcardDeck, setSelectedFlashcardDeck] = useState<"auto" | number>("auto")
  const [activeOutputType, setActiveOutputType] = useState<ArtifactType | null>(
    null
  )
  const [recentOutputTypes, setRecentOutputTypes] = useState<ArtifactType[]>(
    () => loadRecentOutputTypes()
  )
  const [moreOutputsExpanded, setMoreOutputsExpanded] = useState(
    () => loadRecentOutputTypes().length === 0
  )
  const previewAudioRef = useRef<HTMLAudioElement | null>(null)

  // Local state for collapsible sections
  const [studioOptionsExpanded, setStudioOptionsExpanded] = useState(false)
  const [studioExpanded, setStudioExpanded] = useState(true)
  const [outputsExpanded, setOutputsExpanded] = useState(true)
  const [notesExpanded, setNotesExpanded] = useState(false)
  const [chatModels, setChatModels] = useState<ModelInfo[]>([])
  const [loadingChatModels, setLoadingChatModels] = useState(false)
  const generationAbortRef = useRef<AbortController | null>(null)
  const [generationPhase, setGenerationPhase] = useState<
    "preparing" | "retrieving" | "generating" | "finalizing" | null
  >(null)
  const outputListContainerRef = useRef<HTMLDivElement | null>(null)
  const [outputListScrollTop, setOutputListScrollTop] = useState(0)
  const [outputListViewportHeight, setOutputListViewportHeight] = useState(320)

  const inferredTldwProviderKey = inferTldwProviderFromModel(audioSettings.model)

  // Fetch voices when provider changes to tldw
  useEffect(() => {
    if (audioSettings.provider !== "tldw") {
      setTldwVoices([])
      setLoadingVoices(false)
      return
    }
    if (!inferredTldwProviderKey) {
      setTldwVoices([])
      setLoadingVoices(false)
      return
    }
    setLoadingVoices(true)
    fetchTldwVoiceCatalog(inferredTldwProviderKey)
      .then((voices) => setTldwVoices(voices))
      .catch(() => setTldwVoices([]))
      .finally(() => setLoadingVoices(false))
  }, [audioSettings.provider, inferredTldwProviderKey])

  useEffect(() => {
    let cancelled = false
    setLoadingChatModels(true)
    tldwModels
      .getChatModels()
      .then((models) => {
        if (cancelled) return
        setChatModels(Array.isArray(models) ? models : [])
      })
      .catch(() => {
        if (cancelled) return
        setChatModels([])
      })
      .finally(() => {
        if (cancelled) return
        setLoadingChatModels(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const loadFlashcardDecks = async (signal?: AbortSignal) => {
    setLoadingDecks(true)
    try {
      const decks = await listDecks({ signal })
      const normalizedDecks = decks.map((deck) => ({
        id: deck.id,
        name: deck.name || `Deck ${deck.id}`
      }))
      setAvailableDecks(normalizedDecks)
      if (
        selectedFlashcardDeck !== "auto" &&
        !normalizedDecks.some((deck) => deck.id === selectedFlashcardDeck)
      ) {
        setSelectedFlashcardDeck("auto")
      }
    } catch (error) {
      if (!isAbortLikeError(error)) {
        setAvailableDecks([])
      }
    } finally {
      setLoadingDecks(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    void loadFlashcardDecks(controller.signal)
    return () => {
      controller.abort()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const selectedMediaIds = React.useMemo(
    () =>
      typeof getEffectiveSelectedMediaIds === "function"
        ? getEffectiveSelectedMediaIds()
        : getSelectedMediaIds(),
    [
      getEffectiveSelectedMediaIds,
      getSelectedMediaIds,
      selectedSourceFolderIds,
      selectedSourceIds
    ]
  )
  const hasSelectedSources = selectedMediaIds.length > 0
  const selectedMediaCount = selectedMediaIds.length
  const contextualAudioSettingsVisible =
    activeOutputType === "audio_overview" ||
    generatingOutputType === "audio_overview"
  const showAudioSettingsPanel = showTtsSettings || contextualAudioSettingsVisible
  const studioControlSize = isMobile ? "large" : "small"
  const mobileSliderClassName = isMobile
    ? "[&_.ant-slider-rail]:!h-2 [&_.ant-slider-track]:!h-2 [&_.ant-slider-handle]:!h-5 [&_.ant-slider-handle]:!w-5"
    : undefined
  const normalizedRagAdvancedOptions = React.useMemo(() => {
    return isRecord(ragAdvancedOptions) ? ragAdvancedOptions : {}
  }, [ragAdvancedOptions])
  const resolvedStudioTopK = React.useMemo(() => {
    const value =
      typeof ragTopK === "number" && Number.isFinite(ragTopK)
        ? ragTopK
        : STUDIO_DEFAULT_RAG_TOP_K
    return Math.max(1, Math.min(50, Math.round(value)))
  }, [ragTopK])
  const studioSimilarityThreshold = React.useMemo(() => {
    const raw = normalizedRagAdvancedOptions.min_score
    const value =
      typeof raw === "number" && Number.isFinite(raw)
        ? raw
        : STUDIO_DEFAULT_RAG_MIN_SCORE
    return Math.max(0, Math.min(1, value))
  }, [normalizedRagAdvancedOptions.min_score])
  const studioRerankingEnabled = React.useMemo(() => {
    const raw = normalizedRagAdvancedOptions.enable_reranking
    return typeof raw === "boolean"
      ? raw
      : STUDIO_DEFAULT_ENABLE_RERANKING
  }, [normalizedRagAdvancedOptions.enable_reranking])
  const resolvedTemperature = React.useMemo(() => {
    const value =
      typeof temperature === "number" && Number.isFinite(temperature)
        ? temperature
        : 0.7
    return Math.max(0, Math.min(2, Number(value.toFixed(2))))
  }, [temperature])
  const resolvedTopP = React.useMemo(() => {
    const value = typeof topP === "number" && Number.isFinite(topP) ? topP : 1
    return Math.max(0, Math.min(1, Number(value.toFixed(2))))
  }, [topP])
  const resolvedNumPredict = React.useMemo(() => {
    const value =
      typeof numPredict === "number" && Number.isFinite(numPredict)
        ? numPredict
        : STUDIO_DEFAULT_MAX_TOKENS
    return Math.max(1, Math.min(32768, Math.round(value)))
  }, [numPredict])
  const normalizedApiProvider =
    typeof apiProvider === "string" && apiProvider.trim().length > 0
      ? apiProvider.trim().toLowerCase()
      : "__auto__"
  const providerOptions = React.useMemo(() => {
    const providerKeys = Array.from(
      new Set(
        chatModels
          .map((model) => String(model.provider || "").trim().toLowerCase())
          .filter(Boolean)
      )
    )
    providerKeys.sort((a, b) => a.localeCompare(b))
    return providerKeys.map((provider) => ({
      value: provider,
      label: tldwModels.getProviderDisplayName(provider)
    }))
  }, [chatModels])
  const filteredChatModels = React.useMemo(() => {
    if (normalizedApiProvider === "__auto__") {
      return chatModels
    }
    return chatModels.filter(
      (model) =>
        String(model.provider || "").trim().toLowerCase() ===
        normalizedApiProvider
    )
  }, [chatModels, normalizedApiProvider])
  const modelOptions = React.useMemo(() => {
    const options = filteredChatModels.map((model) => ({
      value: model.id,
      label: model.name || model.id
    }))
    if (
      selectedModel &&
      !options.some((option) => option.value === selectedModel)
    ) {
      options.push({
        value: selectedModel,
        label: `${selectedModel} (${t("playground:studio.currentModel", "current")})`
      })
    }
    return options
  }, [filteredChatModels, selectedModel, t])
  const patchRagAdvancedOptions = React.useCallback(
    (patch: Record<string, unknown>) => {
      setRagAdvancedOptions({
        ...normalizedRagAdvancedOptions,
        ...patch
      })
    },
    [normalizedRagAdvancedOptions, setRagAdvancedOptions]
  )
  const handleStudioTopKChange = (value: number | number[]) => {
    const raw = Array.isArray(value) ? value[0] : value
    if (typeof raw !== "number" || !Number.isFinite(raw)) return
    const nextTopK = Math.max(1, Math.min(50, Math.round(raw)))
    setRagTopK(nextTopK)
    patchRagAdvancedOptions({ top_k: nextTopK })
  }
  const handleStudioSimilarityThresholdChange = (value: number | number[]) => {
    const raw = Array.isArray(value) ? value[0] : value
    if (typeof raw !== "number" || !Number.isFinite(raw)) return
    const nextThreshold = Math.max(0, Math.min(1, raw))
    patchRagAdvancedOptions({ min_score: Number(nextThreshold.toFixed(2)) })
  }
  const handleStudioTemperatureChange = (value: number | number[]) => {
    const raw = Array.isArray(value) ? value[0] : value
    if (typeof raw !== "number" || !Number.isFinite(raw)) return
    setTemperature(Math.max(0, Math.min(2, Number(raw.toFixed(2)))))
  }
  const handleStudioTopPChange = (value: number | number[]) => {
    const raw = Array.isArray(value) ? value[0] : value
    if (typeof raw !== "number" || !Number.isFinite(raw)) return
    setTopP(Math.max(0, Math.min(1, Number(raw.toFixed(2)))))
  }
  const etaSeconds =
    isGeneratingOutput && generatingOutputType
      ? estimateGenerationSeconds(
          generatingOutputType,
          Math.max(1, selectedMediaCount)
        )
      : null
  const cumulativeUsage = React.useMemo(() => {
    return generatedArtifacts.reduce(
      (acc, artifact) => {
        const tokens = artifact.totalTokens || artifact.estimatedTokens || 0
        const cost = artifact.totalCostUsd || artifact.estimatedCostUsd || 0
        return {
          tokens: acc.tokens + tokens,
          costUsd: acc.costUsd + cost
        }
      },
      { tokens: 0, costUsd: 0 }
    )
  }, [generatedArtifacts])
  const useVirtualizedOutputs =
    generatedArtifacts.length > OUTPUT_VIRTUALIZATION_THRESHOLD
  const virtualOutputStartIndex = useVirtualizedOutputs
    ? Math.max(
        0,
        Math.floor(outputListScrollTop / OUTPUT_VIRTUAL_ROW_HEIGHT) -
          OUTPUT_VIRTUAL_OVERSCAN
      )
    : 0
  const virtualOutputEndIndex = useVirtualizedOutputs
    ? Math.min(
        generatedArtifacts.length,
        Math.ceil(
          (outputListScrollTop + outputListViewportHeight) /
            OUTPUT_VIRTUAL_ROW_HEIGHT
        ) + OUTPUT_VIRTUAL_OVERSCAN
      )
    : generatedArtifacts.length
  const visibleArtifacts = useVirtualizedOutputs
    ? generatedArtifacts.slice(virtualOutputStartIndex, virtualOutputEndIndex)
    : generatedArtifacts
  const virtualOutputTopPadding = useVirtualizedOutputs
    ? virtualOutputStartIndex * OUTPUT_VIRTUAL_ROW_HEIGHT
    : 0
  const virtualOutputBottomPadding = useVirtualizedOutputs
    ? Math.max(
        0,
        (generatedArtifacts.length - virtualOutputEndIndex) *
          OUTPUT_VIRTUAL_ROW_HEIGHT
      )
    : 0

  useEffect(() => {
    return () => {
      generationAbortRef.current?.abort()
      generationAbortRef.current = null
      if (previewAudioRef.current) {
        previewAudioRef.current.pause()
        previewAudioRef.current.src = ""
        previewAudioRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    if (!noteFocusTarget) return
    if (!notesExpanded) {
      setNotesExpanded(true)
    }
  }, [noteFocusTarget, notesExpanded])

  useEffect(() => {
    const container = outputListContainerRef.current
    if (!container) return

    const syncViewportHeight = () => {
      setOutputListViewportHeight(container.clientHeight || 320)
    }

    syncViewportHeight()

    if (typeof ResizeObserver === "undefined") {
      return
    }

    const observer = new ResizeObserver(() => {
      syncViewportHeight()
    })
    observer.observe(container)

    return () => {
      observer.disconnect()
    }
  }, [outputsExpanded])

  useEffect(() => {
    if (!useVirtualizedOutputs) {
      setOutputListScrollTop(0)
      return
    }

    const container = outputListContainerRef.current
    if (!container) return

    const maxScrollTop = Math.max(
      0,
      generatedArtifacts.length * OUTPUT_VIRTUAL_ROW_HEIGHT - outputListViewportHeight
    )

    if (container.scrollTop > maxScrollTop) {
      container.scrollTop = maxScrollTop
      setOutputListScrollTop(maxScrollTop)
    }
  }, [generatedArtifacts.length, outputListViewportHeight, useVirtualizedOutputs])

  // Get voice options based on provider
  const getVoiceOptions = () => {
    if (audioSettings.provider === "tldw") {
      if (tldwVoices.length > 0) {
        return tldwVoices.map((v) => ({
          value: v.voice_id || v.id || v.name || "",
          label: v.name || v.voice_id || v.id || "Unknown"
        }))
      }
      // Default tldw voices
      return [
        { value: "af_heart", label: "Heart (Female)" },
        { value: "af_bella", label: "Bella (Female)" },
        { value: "am_adam", label: "Adam (Male)" },
        { value: "am_michael", label: "Michael (Male)" }
      ]
    }
    if (audioSettings.provider === "openai") {
      return OPENAI_TTS_VOICES
    }
    return []
  }

  // Get model options based on provider
  const getModelOptions = () => {
    if (audioSettings.provider === "tldw") {
      return TLDW_TTS_MODELS
    }
    if (audioSettings.provider === "openai") {
      return OPENAI_TTS_MODELS
    }
    return []
  }

  const handleCancelGeneration = () => {
    const activeAbort = generationAbortRef.current
    if (!activeAbort) return
    void trackWorkspacePlaygroundTelemetry({
      type: "operation_cancelled",
      workspace_id: workspaceTag || null,
      operation: "artifact_generation",
      artifact_type: generatingOutputType || null
    })
    activeAbort.abort()
  }

  const handleDeleteArtifact = (artifact: GeneratedArtifact) => {
    const artifactIndex = generatedArtifacts.findIndex(
      (entry) => entry.id === artifact.id
    )
    Modal.confirm({
      title: t("playground:studio.deleteOutputTitle", "Delete output?"),
      content: t(
        "playground:studio.deleteOutputDescription",
        "This generated output will be permanently removed."
      ),
      okText: t("common:delete", "Delete"),
      cancelText: t("common:cancel", "Cancel"),
      okButtonProps: { danger: true },
      onOk: () => {
        const undoHandle = scheduleWorkspaceUndoAction({
          apply: () => {
            removeArtifact(artifact.id)
          },
          undo: () => {
            restoreArtifact(artifact, { index: artifactIndex })
          }
        })

        const undoMessageKey = `workspace-artifact-undo-${undoHandle.id}`
        const maybeOpen = (messageApi as { open?: (config: unknown) => void })
          .open
        const messageConfig = {
          key: undoMessageKey,
          type: "warning",
          duration: WORKSPACE_UNDO_WINDOW_MS / 1000,
          content: t(
            "playground:studio.undoDeleteOutput",
            "Output deleted."
          ),
          btn: (
            <Button
              size="small"
              type="link"
              onClick={() => {
                if (undoWorkspaceAction(undoHandle.id)) {
                  messageApi.success(
                    t("playground:studio.outputRestored", "Output restored")
                  )
                }
                messageApi.destroy(undoMessageKey)
              }}
            >
              {t("common:undo", "Undo")}
            </Button>
          )
        }
        if (typeof maybeOpen === "function") {
          maybeOpen(messageConfig)
        } else {
          const maybeWarning = (
            messageApi as { warning?: (content: string) => void }
          ).warning
          if (typeof maybeWarning === "function") {
            maybeWarning(
              t("playground:studio.undoDeleteOutput", "Output deleted.")
            )
          }
        }
      }
    })
  }

  const handlePreviewVoice = async () => {
    if (audioSettings.provider === "browser") {
      if (typeof window === "undefined" || !("speechSynthesis" in window)) {
        messageApi.error(
          t(
            "playground:studio.voicePreviewUnavailable",
            "Voice preview is unavailable in this browser."
          )
        )
        return
      }
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(VOICE_PREVIEW_TEXT)
      utterance.rate = audioSettings.speed
      window.speechSynthesis.speak(utterance)
      return
    }

    setPreviewingVoice(true)
    try {
      const audioBuffer = await tldwClient.synthesizeSpeech(VOICE_PREVIEW_TEXT, {
        model: audioSettings.model,
        voice: audioSettings.voice,
        responseFormat: "mp3",
        speed: audioSettings.speed
      })
      const audioBlob = new Blob([audioBuffer], { type: "audio/mpeg" })
      const audioUrl = URL.createObjectURL(audioBlob)

      if (previewAudioRef.current) {
        previewAudioRef.current.pause()
      }
      const previewAudio = new Audio(audioUrl)
      previewAudioRef.current = previewAudio
      previewAudio.onended = () => {
        URL.revokeObjectURL(audioUrl)
        if (previewAudioRef.current === previewAudio) {
          previewAudioRef.current = null
        }
      }
      void previewAudio.play()
    } catch (error) {
      if (!isAbortLikeError(error)) {
        messageApi.error(
          t(
            "playground:studio.voicePreviewFailed",
            "Unable to preview this voice right now."
          )
        )
      }
    } finally {
      setPreviewingVoice(false)
    }
  }

  const handleDiscussArtifact = (artifact: GeneratedArtifact) => {
    if (typeof window === "undefined") return
    const content = (artifact.content || "").trim()
    if (!content) {
      messageApi.warning(
        t(
          "playground:studio.discussNoContent",
          "This output has no text content to discuss yet."
        )
      )
      return
    }
    const detail: ArtifactDiscussDetail = {
      artifactId: artifact.id,
      artifactType: artifact.type,
      title: artifact.title,
      content
    }
    window.dispatchEvent(
      new CustomEvent<ArtifactDiscussDetail>(WORKSPACE_DISCUSS_EVENT, { detail })
    )
    messageApi.success(
      t(
        "playground:studio.discussSent",
        "Sent to chat. Ask a follow-up in the chat pane."
      )
    )
  }

  const handleSaveArtifactToNotes = (
    artifact: GeneratedArtifact,
    mode: "append" | "replace" = "append"
  ) => {
    const content = (artifact.content || "").trim()
    if (!content) {
      messageApi.warning(
        t(
          "playground:studio.notesCaptureNoContent",
          "This output has no text content to save."
        )
      )
      return
    }
    captureToCurrentNote({
      title: artifact.title,
      content,
      mode
    })
    messageApi.success(
      mode === "replace"
        ? t(
            "playground:studio.notesCaptureReplaced",
            "Output replaced the current note draft."
          )
        : t(
            "playground:studio.notesCaptureAppended",
            "Output added to your current note draft."
          )
    )
  }

  const handleGenerateOutput = async (
    type: ArtifactType,
    options: ArtifactGenerationOptions = {}
  ) => {
    setRecentOutputTypes(recordRecentOutputType(type))
    if (!hasSelectedSources) return

    const mediaIds = selectedMediaIds
    if (mediaIds.length === 0) return
    if (type === "compare_sources" && mediaIds.length < 2) {
      messageApi.warning(
        t(
          "playground:studio.compareRequiresMultipleSources",
          "Select at least two sources to compare."
        )
      )
      return
    }

    const activeAbort = new AbortController()
    generationAbortRef.current = activeAbort

    // Start generation with phased progress (UX-031)
    setIsGeneratingOutput(true, type)
    setGenerationPhase("preparing")
    const estimatedTokens = estimateGenerationTokens(type, mediaIds.length)
    const estimatedCostUsd = estimateGenerationCostUsd(estimatedTokens)

    let artifact: GeneratedArtifact | null = null

    try {
      const artifactLabel = OUTPUT_BUTTONS.find((b) => b.type === type)?.label || type
      const shouldReplaceExisting =
        options.mode === "replace" && Boolean(options.targetArtifactId)

      if (shouldReplaceExisting) {
        const existingArtifact = generatedArtifacts.find(
          (entry) => entry.id === options.targetArtifactId
        )
        if (existingArtifact) {
          updateArtifactStatus(existingArtifact.id, "generating", {
            createdAt: new Date(),
            completedAt: undefined,
            estimatedTokens,
            estimatedCostUsd,
            totalTokens: undefined,
            totalCostUsd: undefined,
            serverId: undefined,
            content: undefined,
            audioUrl: undefined,
            audioFormat: undefined,
            presentationId: undefined,
            presentationVersion: undefined,
            data: undefined,
            errorMessage: undefined
          })
          artifact = existingArtifact
        } else {
          artifact = addArtifact({
            type,
            title: `${artifactLabel}`,
            status: "generating",
            estimatedTokens,
            estimatedCostUsd
          })
        }
      } else {
        artifact = addArtifact({
          type,
          title: `${artifactLabel}`,
          status: "generating",
          estimatedTokens,
          estimatedCostUsd,
          previousVersionId:
            options.mode === "new_version" ? options.targetArtifactId : undefined
        })
      }

      let result: GenerationResult = {}

      // Phase: retrieving relevant content
      setGenerationPhase("retrieving")

      // Small delay to ensure UI updates before heavy work
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Phase: generating output
      setGenerationPhase("generating")

      switch (type) {
        case "summary":
          result = await generateSummary(
            mediaIds,
            workspaceTag,
            activeAbort.signal
          )
          break
        case "report":
          result = await generateReport(mediaIds, workspaceTag, activeAbort.signal)
          break
        case "compare_sources":
          result = await generateCompareSources(
            mediaIds,
            workspaceTag,
            activeAbort.signal
          )
          break
        case "timeline":
          result = await generateTimeline(
            mediaIds,
            workspaceTag,
            activeAbort.signal
          )
          break
        case "quiz":
          result = await generateQuizFromMedia(
            mediaIds,
            workspaceTag,
            activeAbort.signal
          )
          break
        case "flashcards":
          result = await generateFlashcards(
            mediaIds,
            selectedFlashcardDeck === "auto" ? undefined : selectedFlashcardDeck,
            workspaceTag,
            activeAbort.signal
          )
          break
        case "mindmap":
          result = await generateMindMap(mediaIds, activeAbort.signal)
          break
        case "audio_overview":
          result = await generateAudioOverview(
            mediaIds,
            audioSettings,
            activeAbort.signal
          )
          break
        case "slides":
          result = await generateSlidesFromApi(mediaIds[0], activeAbort.signal)
          break
        case "data_table":
          result = await generateDataTable(
            mediaIds,
            workspaceTag,
            activeAbort.signal
          )
          break
        default:
          throw new Error(`Unsupported output type: ${type}`)
      }

      // Phase: finalizing
      setGenerationPhase("finalizing")

      // Update artifact with success
      if (!artifact) {
        throw new Error("Artifact placeholder was not created")
      }

      result = finalizeGenerationResult(type, result, {
        audioProvider: audioSettings.provider
      })

      updateArtifactStatus(artifact.id, "completed", {
        serverId: result.serverId,
        content: result.content,
        audioUrl: result.audioUrl,
        audioFormat: result.audioFormat,
        presentationId: result.presentationId,
        presentationVersion: result.presentationVersion,
        totalTokens:
          result.totalTokens ||
          (result.content
            ? Math.max(1, Math.round(result.content.length / 4))
            : estimatedTokens),
        totalCostUsd:
          result.totalCostUsd ||
          estimateGenerationCostUsd(
            result.totalTokens ||
              (result.content
                ? Math.max(1, Math.round(result.content.length / 4))
                : estimatedTokens)
          ),
        data: result.data
      })

      messageApi.success(
        t("playground:studio.generateSuccess", "{{type}} generated successfully", {
          type: OUTPUT_BUTTONS.find((b) => b.type === type)?.label || type
        })
      )
    } catch (error) {
      const generationWasAborted = isAbortLikeError(error)
      if (artifact) {
        updateArtifactStatus(artifact.id, "failed", {
          errorMessage: generationWasAborted
            ? t(
                "playground:studio.generateCancelled",
                "Generation canceled before completion."
              )
            : error instanceof Error
              ? error.message
              : "Generation failed"
        })
      }

      if (generationWasAborted) {
        messageApi.info(
          t("playground:studio.generateCancelledToast", "Generation canceled")
        )
      } else {
        messageApi.error(
          t("playground:studio.generateError", "Failed to generate {{type}}", {
            type: OUTPUT_BUTTONS.find((b) => b.type === type)?.label || type
          })
        )
      }
    } finally {
      if (generationAbortRef.current === activeAbort) {
        generationAbortRef.current = null
      }
      setIsGeneratingOutput(false)
      setGenerationPhase(null)
    }
  }

  const getResponsiveArtifactModalProps = (
    desktopWidth: number
  ): {
    width: number | string
    style?: React.CSSProperties
    styles?: {
      body?: React.CSSProperties
    }
  } => {
    if (!isMobile) {
      return { width: desktopWidth }
    }

    return {
      width: "100%",
      style: { top: 0, paddingBottom: 0 },
      styles: {
        body: {
          maxHeight: "calc(100dvh - 96px)",
          overflowY: "auto"
        }
      }
    }
  }

  const handleViewArtifact = (artifact: GeneratedArtifact) => {
    if (artifact.type === "audio_overview" && artifact.audioUrl) {
      // Show audio player modal for audio artifacts
      Modal.info({
        title: artifact.title,
        content: (
          <div className="flex flex-col gap-4">
            <audio
              controls
              className="w-full"
              src={artifact.audioUrl}
            >
              Your browser does not support the audio element.
            </audio>
            {artifact.content && (
              <details className="mt-2">
                <summary className="cursor-pointer text-sm text-text-muted">
                  View Script
                </summary>
                <div className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap rounded bg-surface2 p-2 text-sm">
                  {artifact.content}
                </div>
              </details>
            )}
          </div>
        ),
        ...getResponsiveArtifactModalProps(500)
      })
      return
    }

    if (artifact.type === "mindmap" && artifact.content) {
      Modal.info({
        title: artifact.title,
        content: (
          <MindMapArtifactViewer title={artifact.title} content={artifact.content} />
        ),
        ...getResponsiveArtifactModalProps(960),
        footer: null,
        icon: null
      })
      return
    }

    if (artifact.type === "data_table" && artifact.content) {
      Modal.info({
        title: artifact.title,
        content: (
          <DataTableArtifactViewer title={artifact.title} content={artifact.content} />
        ),
        ...getResponsiveArtifactModalProps(980),
        footer: null,
        icon: null
      })
      return
    }

    if (artifact.type === "flashcards") {
      const initialCards = getArtifactFlashcards(artifact)
      const modal = Modal.info({
        title: artifact.title,
        content: (
          <FlashcardArtifactEditor
            cards={initialCards}
            onSave={(cards) => {
              const nextContent = formatFlashcardsContent(cards)
              updateArtifactStatus(artifact.id, artifact.status, {
                content: nextContent,
                data: {
                  ...(artifact.data || {}),
                  flashcards: cards
                }
              })
              messageApi.success(
                t(
                  "playground:studio.flashcardsSaved",
                  "Flashcards updated"
                )
              )
              modal.destroy()
            }}
          />
        ),
        ...getResponsiveArtifactModalProps(820),
        footer: null,
        icon: null
      })
      return
    }

    if (artifact.type === "quiz") {
      const initialQuestions = getArtifactQuizQuestions(artifact)
      const modal = Modal.info({
        title: artifact.title,
        content: (
          <QuizArtifactEditor
            questions={initialQuestions}
            onSave={(questions) => {
              const nextContent = formatQuizQuestionsContent(
                questions,
                artifact.title
              )
              updateArtifactStatus(artifact.id, artifact.status, {
                content: nextContent,
                data: {
                  ...(artifact.data || {}),
                  questions
                }
              })
              messageApi.success(
                t("playground:studio.quizSaved", "Quiz updated")
              )
              modal.destroy()
            }}
          />
        ),
        ...getResponsiveArtifactModalProps(860),
        footer: null,
        icon: null
      })
      return
    }

    if (artifact.content) {
      Modal.info({
        title: artifact.title,
        content: (
          <div className="max-h-96 overflow-y-auto whitespace-pre-wrap">
            {artifact.content}
          </div>
        ),
        ...getResponsiveArtifactModalProps(600)
      })
    }
  }

  const handleDownloadArtifact = async (artifact: GeneratedArtifact, format?: string) => {
    // Handle audio download - use the audioUrl blob directly
    if (artifact.type === "audio_overview" && artifact.audioUrl) {
      const a = document.createElement("a")
      a.href = artifact.audioUrl
      a.download = `${artifact.title}.${artifact.audioFormat || "mp3"}`
      a.click()
      return
    }

    // Handle slides download with format selection
    if (artifact.type === "slides" && artifact.presentationId) {
      const exportFormat = (format || "markdown") as "revealjs" | "markdown" | "json" | "pdf"
      const formatConfig = SLIDES_EXPORT_FORMATS.find((f) => f.value === exportFormat)
      try {
        const blob = await tldwClient.exportPresentation(artifact.presentationId, exportFormat)
        const url = URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url
        a.download = `${artifact.title}.${formatConfig?.ext || "md"}`
        a.click()
        URL.revokeObjectURL(url)
        messageApi.success(t("common:downloadSuccess", "Downloaded successfully"))
      } catch (error) {
        messageApi.error(t("common:downloadError", "Download failed"))
      }
      return
    }

    if (artifact.type === "quiz") {
      const questions =
        isRecord(artifact.data) && Array.isArray(artifact.data.questions)
          ? artifact.data.questions
          : null

      if (questions) {
        const quizBlob = new Blob(
          [
            JSON.stringify(
              {
                title: artifact.title,
                questions
              },
              null,
              2
            )
          ],
          { type: "application/json" }
        )
        downloadBlobFile(quizBlob, `${artifact.title}.json`)
        return
      }

      if (artifact.content) {
        const quizTextBlob = new Blob([artifact.content], { type: "text/plain" })
        downloadBlobFile(quizTextBlob, `${artifact.title}.txt`)
      }
      return
    }

    if (artifact.serverId && artifact.type !== "mindmap") {
      try {
        const blob = await tldwClient.downloadOutput(String(artifact.serverId))
        const url = URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url
        a.download = `${artifact.title}.${getFileExtension(artifact.type)}`
        a.click()
        URL.revokeObjectURL(url)
      } catch {
        messageApi.error(t("common:downloadError", "Download failed"))
      }
    } else if (artifact.content) {
      // Download text content
      const blob = new Blob([artifact.content], { type: "text/plain" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `${artifact.title}.${artifact.type === "mindmap" ? "mmd" : "txt"}`
      a.click()
      URL.revokeObjectURL(url)
    }
  }

  // Show slides export format selection modal
  const handleSlidesDownload = (artifact: GeneratedArtifact) => {
    if (!artifact.presentationId) {
      // Fallback to content download
      handleDownloadArtifact(artifact)
      return
    }

    const modal = Modal.info({
      title: t("playground:studio.selectExportFormat", "Select Export Format"),
      content: (
        <div className="mt-4 space-y-2">
          {SLIDES_EXPORT_FORMATS.map((format) => (
            <button
              key={format.value}
              type="button"
              onClick={() => {
                modal.destroy()
                handleDownloadArtifact(artifact, format.value)
              }}
              className="w-full rounded border border-border p-3 text-left hover:bg-surface2"
            >
              <div className="font-medium">{format.label}</div>
              <div className="text-xs text-text-muted">.{format.ext}</div>
            </button>
          ))}
        </div>
      ),
      footer: null,
      icon: null,
      width: 300
    })
  }

  const handleIconButtonKeyDown = (
    event: React.KeyboardEvent<HTMLButtonElement>
  ) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      event.currentTarget.click()
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto">
      {contextHolder}

      {/* Header */}
      <div className="flex items-start justify-between border-b border-border px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-text">
            {t("playground:studio.title", "Studio")}
          </h2>
          <p className="mt-0.5 text-xs text-text-muted">
            {t("playground:studio.subtitle", "Generate outputs from your sources")}
          </p>
        </div>
        {onHide && (
          <Tooltip title={t("playground:workspace.hideStudio", "Hide studio")}>
            <button
              type="button"
              onClick={onHide}
              className="hidden h-9 w-9 items-center justify-center rounded text-text-muted transition hover:bg-surface2 hover:text-text lg:flex"
              aria-label={t("playground:workspace.hideStudio", "Hide studio")}
            >
              <PanelRightClose className="h-4 w-4" />
            </button>
          </Tooltip>
        )}
      </div>

      {/* Studio Options Section - Collapsible */}
      <div className="border-b border-border">
        <button
          type="button"
          onClick={() => setStudioOptionsExpanded(!studioOptionsExpanded)}
          aria-expanded={studioOptionsExpanded}
          aria-controls="studio-options-section"
          className="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-surface2/50"
        >
          <h3 className="text-xs font-semibold uppercase text-text-muted">
            {t("playground:studio.studioOptions", "Studio Options")}
          </h3>
          {studioOptionsExpanded ? (
            <ChevronUp className="h-4 w-4 text-text-muted" />
          ) : (
            <ChevronDown className="h-4 w-4 text-text-muted" />
          )}
        </button>
        <div
          id="studio-options-section"
          hidden={!studioOptionsExpanded}
          className="px-4 pb-4"
        >
          <div
            data-testid="studio-options-accordion"
            className="space-y-4 rounded border border-border bg-surface2/30 p-3"
          >
            <section aria-label={t("playground:studio.modelRuntime", "Model Runtime")}>
              <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                {t("playground:studio.modelRuntime", "Model Runtime")}
              </h4>
              <div className="space-y-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-text-muted">
                    {t("playground:studio.apiProvider", "API Provider")}
                  </label>
                  <Select
                    size={studioControlSize}
                    className="w-full"
                    value={normalizedApiProvider}
                    onChange={(value) => {
                      if (value === "__auto__") {
                        updateModelSetting("apiProvider", undefined)
                        return
                      }
                      setApiProvider(String(value))
                    }}
                    options={[
                      {
                        value: "__auto__",
                        label: t(
                          "playground:studio.apiProviderAuto",
                          "Auto (from selected model)"
                        )
                      },
                      ...providerOptions
                    ]}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-text-muted">
                    {t("playground:studio.modelSelection", "Model")}
                  </label>
                  <Select
                    size={studioControlSize}
                    className="w-full"
                    value={selectedModel ?? undefined}
                    onChange={(value) => setSelectedModel(String(value))}
                    options={modelOptions}
                    loading={loadingChatModels}
                    placeholder={t(
                      "playground:studio.modelSelectionPlaceholder",
                      "Select a model"
                    )}
                  />
                </div>
                <div>
                  <div className="mb-1 flex items-center justify-between text-xs text-text-muted">
                    <label className="font-medium">
                      {t("playground:studio.temperature", "Temperature")}
                    </label>
                    <span className="font-medium text-text">
                      {resolvedTemperature.toFixed(2)}
                    </span>
                  </div>
                  <Slider
                    min={0}
                    max={2}
                    step={0.01}
                    value={resolvedTemperature}
                    onChange={handleStudioTemperatureChange}
                  />
                </div>
                <div>
                  <div className="mb-1 flex items-center justify-between text-xs text-text-muted">
                    <label className="font-medium">
                      {t("playground:studio.topP", "Top P")}
                    </label>
                    <span className="font-medium text-text">
                      {resolvedTopP.toFixed(2)}
                    </span>
                  </div>
                  <Slider
                    min={0}
                    max={1}
                    step={0.01}
                    value={resolvedTopP}
                    onChange={handleStudioTopPChange}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-text-muted">
                    {t("playground:studio.maxTokens", "Max Tokens")}
                  </label>
                  <Input
                    size={studioControlSize}
                    type="number"
                    min={1}
                    max={32768}
                    value={resolvedNumPredict}
                    onChange={(event) => {
                      const raw = event.target.value.trim()
                      if (!raw) {
                        setNumPredict(undefined)
                        return
                      }
                      const parsed = Number(raw)
                      if (!Number.isFinite(parsed)) return
                      setNumPredict(Math.max(1, Math.min(32768, Math.round(parsed))))
                    }}
                  />
                </div>
              </div>
            </section>

            <section aria-label={t("playground:studio.ragSettings", "RAG Settings")}>
              <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                {t("playground:studio.ragSettings", "RAG Settings")}
              </h4>
              <div className="space-y-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-text-muted">
                    {t("playground:studio.ragSearchMode", "Search Mode")}
                  </label>
                  <Select
                    size={studioControlSize}
                    className="w-full"
                    value={ragSearchMode}
                    onChange={(value) =>
                      setRagSearchMode(value as "hybrid" | "vector" | "fts")
                    }
                    options={[
                      { value: "hybrid", label: t("playground:studio.ragHybrid", "Hybrid") },
                      { value: "vector", label: t("playground:studio.ragVector", "Vector") },
                      { value: "fts", label: t("playground:studio.ragFts", "FTS") }
                    ]}
                  />
                </div>
                <div>
                  <div className="mb-1 flex items-center justify-between text-xs text-text-muted">
                    <span>{t("playground:studio.ragTopK", "Top K")}</span>
                    <span className="font-medium text-text">{resolvedStudioTopK}</span>
                  </div>
                  <Slider
                    min={1}
                    max={50}
                    step={1}
                    value={resolvedStudioTopK}
                    onChange={handleStudioTopKChange}
                  />
                </div>
                <div>
                  <div className="mb-1 flex items-center justify-between text-xs text-text-muted">
                    <span>
                      {t(
                        "playground:studio.ragSimilarityThreshold",
                        "Similarity threshold"
                      )}
                    </span>
                    <span className="font-medium text-text">
                      {studioSimilarityThreshold.toFixed(2)}
                    </span>
                  </div>
                  <Slider
                    min={0}
                    max={1}
                    step={0.01}
                    value={studioSimilarityThreshold}
                    onChange={handleStudioSimilarityThresholdChange}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">
                    {t("playground:studio.ragEnableGeneration", "Enable generation")}
                  </span>
                  <Switch
                    size="small"
                    checked={ragEnableGeneration}
                    onChange={(checked) => setRagEnableGeneration(checked)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">
                    {t("playground:studio.ragEnableCitations", "Enable citations")}
                  </span>
                  <Switch
                    size="small"
                    checked={ragEnableCitations}
                    onChange={(checked) => setRagEnableCitations(checked)}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">
                    {t("playground:studio.ragEnableReranking", "Enable reranking")}
                  </span>
                  <Switch
                    size="small"
                    checked={studioRerankingEnabled}
                    onChange={(checked) =>
                      patchRagAdvancedOptions({ enable_reranking: checked })
                    }
                  />
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>

      {/* Studio Section - Collapsible */}
      <div className="border-b border-border">
        <button
          type="button"
          onClick={() => setStudioExpanded(!studioExpanded)}
          aria-expanded={studioExpanded}
          aria-controls="studio-output-types-section"
          className="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-surface2/50"
        >
          <h3 className="text-xs font-semibold uppercase text-text-muted">
            {t("playground:studio.outputTypes", "Output Types")}
          </h3>
          {studioExpanded ? (
            <ChevronUp className="h-4 w-4 text-text-muted" />
          ) : (
            <ChevronDown className="h-4 w-4 text-text-muted" />
          )}
        </button>
        <div
          id="studio-output-types-section"
          hidden={!studioExpanded}
          className="px-4 pb-4"
        >
        {isGeneratingOutput && (
          <div className="mb-3 space-y-2">
            {/* Multi-phase progress indicator (UX-031) */}
            <div className="flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
              <p className="text-xs font-medium text-text">
                {generationPhase === "preparing"
                  ? t("playground:studio.phasePreparing", "Preparing...")
                  : generationPhase === "retrieving"
                    ? t("playground:studio.phaseRetrieving", "Retrieving relevant content...")
                    : generationPhase === "finalizing"
                      ? t("playground:studio.phaseFinalizing", "Finalizing...")
                      : t(
                          "playground:studio.phaseGenerating",
                          "Generating {{type}}...",
                          {
                            type:
                              OUTPUT_BUTTONS.find(
                                (button) => button.type === generatingOutputType
                              )?.label || generatingOutputType || "output"
                          }
                        )}
              </p>
            </div>
            {/* Phase progress bar */}
            <div className="flex gap-1">
              {(["preparing", "retrieving", "generating", "finalizing"] as const).map((phase) => {
                const phaseOrder = ["preparing", "retrieving", "generating", "finalizing"]
                const currentIdx = generationPhase ? phaseOrder.indexOf(generationPhase) : -1
                const thisIdx = phaseOrder.indexOf(phase)
                const isComplete = thisIdx < currentIdx
                const isActive = thisIdx === currentIdx
                return (
                  <div
                    key={phase}
                    className={`h-1 flex-1 rounded-full transition-colors ${
                      isComplete
                        ? "bg-primary"
                        : isActive
                          ? "bg-primary/60 animate-pulse"
                          : "bg-border"
                    }`}
                  />
                )
              })}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[11px] text-text-muted">
              {t(
                "playground:studio.generatingWithEta",
                "~{{seconds}}s for {{count}} source{{suffix}}",
                {
                  seconds: etaSeconds ?? 15,
                  count: Math.max(1, selectedMediaCount),
                  suffix: Math.max(1, selectedMediaCount) === 1 ? "" : "s"
                }
              )}
            </p>
            <Button
              size="small"
              danger
              icon={<Square className="h-3.5 w-3.5 fill-current" />}
              onClick={handleCancelGeneration}
            >
              {t("common:cancel", "Cancel")}
            </Button>
            </div>
          </div>
        )}
        {(() => {
          const recentTypes = recentOutputTypes.slice(0, RECENT_OUTPUT_TYPES_COUNT)
          const allTypes = OUTPUT_BUTTONS.map((b) => b.type)
          const remainingTypes = allTypes.filter((t) => !recentTypes.includes(t))
          const hasRecent = recentTypes.length > 0

          const artifactStatusForType = (type: ArtifactType): "completed" | "failed" | null => {
            const match = generatedArtifacts.find((a) => a.type === type)
            if (!match) return null
            if (match.status === "completed") return "completed"
            if (match.status === "failed") return "failed"
            return null
          }

          const renderOutputButton = (type: ArtifactType) => {
            const button = OUTPUT_BUTTONS.find((entry) => entry.type === type)
            if (!button) return null
            const { label, icon: Icon, description } = button
            const isGenerating =
              isGeneratingOutput && generatingOutputType === type
            const requiresMultipleSources =
              type === "compare_sources" && selectedMediaCount < 2
            const isDisabled =
              !hasSelectedSources || isGeneratingOutput || requiresMultipleSources
            const artifactStatus = artifactStatusForType(type)

            return (
              <Tooltip
                key={type}
                title={
                  requiresMultipleSources
                    ? t(
                        "playground:studio.compareRequiresMultipleSourcesHint",
                        "Compare Sources requires at least two selected sources."
                      )
                    : !hasSelectedSources
                    ? t(
                        "playground:studio.selectSourcesFirst",
                        "Select sources first"
                      )
                    : description
                }
              >
                <button
                  type="button"
                  disabled={isDisabled}
                  onFocus={() => setActiveOutputType(type)}
                  onMouseEnter={() => setActiveOutputType(type)}
                  onClick={() => {
                    setActiveOutputType(type)
                    if (type === "audio_overview") {
                      setShowTtsSettings(true)
                    }
                    void handleGenerateOutput(type)
                  }}
                  className={`relative flex flex-col items-center justify-center rounded-lg border p-3 transition-colors ${
                    isDisabled
                      ? "cursor-not-allowed border-border bg-surface2/50 text-text-muted"
                      : "border-border bg-surface hover:border-primary/50 hover:bg-primary/5"
                  }`}
                >
                  {isGenerating ? (
                    <Loader2 className="h-5 w-5 animate-spin text-primary" />
                  ) : (
                    <Icon className="h-5 w-5" />
                  )}
                  <span className="mt-1.5 text-xs font-medium">{label}</span>
                  {artifactStatus === "completed" && (
                    <CheckCircle className="absolute right-1.5 top-1.5 h-3.5 w-3.5 text-success" />
                  )}
                  {artifactStatus === "failed" && (
                    <XCircle className="absolute right-1.5 top-1.5 h-3.5 w-3.5 text-error" />
                  )}
                </button>
              </Tooltip>
            )
          }

          return (
            <div className="space-y-4">
              {hasRecent && (
                <section aria-label={t("playground:studio.recentOutputs", "Recent")}>
                  <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                    {t("playground:studio.recentOutputs", "Recent")}
                  </h4>
                  <div className="grid grid-cols-3 gap-3">
                    {recentTypes.map(renderOutputButton)}
                  </div>
                </section>
              )}
              {hasRecent && !moreOutputsExpanded && (
                <button
                  type="button"
                  onClick={() => setMoreOutputsExpanded(true)}
                  className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-border py-2 text-xs font-medium text-text-muted transition hover:border-primary/40 hover:text-text"
                >
                  <ChevronDown className="h-3.5 w-3.5" />
                  {t("playground:studio.moreOutputs", "More outputs...")}
                </button>
              )}
              {(moreOutputsExpanded || !hasRecent) &&
                OUTPUT_GROUPS.map((group) => {
                  const groupTypes = hasRecent
                    ? group.types.filter((t) => remainingTypes.includes(t))
                    : group.types
                  if (groupTypes.length === 0) return null
                  return (
                    <section key={group.id} aria-label={group.label}>
                      <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                        {group.label}
                      </h4>
                      <div className="grid grid-cols-2 gap-3">
                        {groupTypes.map(renderOutputButton)}
                      </div>
                    </section>
                  )
                })}
              {hasRecent && moreOutputsExpanded && (
                <button
                  type="button"
                  onClick={() => setMoreOutputsExpanded(false)}
                  className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-border py-2 text-xs font-medium text-text-muted transition hover:border-primary/40 hover:text-text"
                >
                  <ChevronUp className="h-3.5 w-3.5" />
                  {t("playground:studio.lessOutputs", "Show less")}
                </button>
              )}
            </div>
          )
        })()}
        {!hasSelectedSources && (
          <p className="mt-2 text-center text-xs text-text-muted">
            {t(
              "playground:studio.selectSourcesHint",
              getWorkspaceStudioNoSourcesHint(isMobile)
            )}
          </p>
        )}

        {/* TTS Settings Panel */}
        <div className="mt-4">
          {!contextualAudioSettingsVisible && !showTtsSettings && (
            <p className="mb-2 rounded border border-border bg-surface2/30 px-3 py-2 text-xs text-text-muted">
              {t(
                "playground:studio.audioSettingsHint",
                "Select Audio Summary to configure TTS voice and speed."
              )}
            </p>
          )}
          <div
            data-testid="studio-audio-settings-accordion"
            className="overflow-hidden rounded border border-border bg-surface2/30"
          >
            <button
              type="button"
              onClick={() => setShowTtsSettings(!showTtsSettings)}
              aria-expanded={showAudioSettingsPanel}
              aria-controls="studio-audio-settings-panel"
              className={`flex w-full items-center justify-between px-3 py-2 text-xs text-text-muted transition-colors ${
                showAudioSettingsPanel
                  ? "border-b border-border bg-surface2/60"
                  : "bg-surface2/50 hover:bg-surface2"
              }`}
            >
              <span className="flex items-center gap-2">
                <Settings2 className="h-3.5 w-3.5" />
                {t("playground:studio.audioSettings", "Audio Settings")}
              </span>
              {showAudioSettingsPanel ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
            </button>

            {showAudioSettingsPanel && (
              <div
                id="studio-audio-settings-panel"
                className={`p-3 ${
                  isMobile ? "space-y-4" : "space-y-3"
                }`}
              >
              {/* Provider */}
              <div>
                <label className="mb-1 block text-xs font-medium text-text-muted">
                  {t("playground:studio.ttsProvider", "TTS Provider")}
                </label>
                <Select
                  size={studioControlSize}
                  className="w-full"
                  value={audioSettings.provider}
                  onChange={(value) => setAudioSettings({ provider: value as AudioTtsProvider })}
                  options={TTS_PROVIDERS}
                />
              </div>

              {/* Model (for tldw and openai) */}
              {audioSettings.provider !== "browser" && (
                <div>
                  <label className="mb-1 block text-xs font-medium text-text-muted">
                    {t("playground:studio.ttsModel", "Model")}
                  </label>
                  <Select
                    size={studioControlSize}
                    className="w-full"
                    value={audioSettings.model}
                    onChange={(value) => setAudioSettings({ model: value })}
                    options={getModelOptions()}
                  />
                </div>
              )}

              {/* Voice */}
              {audioSettings.provider !== "browser" && (
                <div>
                  <label className="mb-1 block text-xs font-medium text-text-muted">
                    {t("playground:studio.ttsVoice", "Voice")}
                  </label>
                  <Select
                    size={studioControlSize}
                    className="w-full"
                    value={audioSettings.voice}
                    onChange={(value) => setAudioSettings({ voice: value })}
                    options={getVoiceOptions()}
                    loading={loadingVoices}
                    showSearch
                    optionFilterProp="label"
                  />
                  <div className="mt-2 flex justify-end">
                    <Button
                      size={studioControlSize}
                      onClick={() => void handlePreviewVoice()}
                      loading={previewingVoice}
                    >
                      {t("playground:studio.previewVoice", "Preview")}
                    </Button>
                  </div>
                </div>
              )}

              {/* Speed */}
              <div>
                <label className="mb-1 block text-xs font-medium text-text-muted">
                  {t("playground:studio.ttsSpeed", "Speed")}: {audioSettings.speed.toFixed(1)}x
                </label>
                <Slider
                  data-testid="studio-tts-speed-slider"
                  className={mobileSliderClassName}
                  min={0.5}
                  max={2.0}
                  step={0.1}
                  value={audioSettings.speed}
                  onChange={(value) => setAudioSettings({ speed: value })}
                  tooltip={{ formatter: (v) => `${v}x` }}
                />
              </div>

              {/* Format */}
              <div>
                <label className="mb-1 block text-xs font-medium text-text-muted">
                  {t("playground:studio.ttsFormat", "Output Format")}
                </label>
                <Select
                  size={studioControlSize}
                  className="w-full"
                  value={audioSettings.format}
                  onChange={(value) => setAudioSettings({ format: value as any })}
                  options={AUDIO_FORMATS}
                />
              </div>

              <div className="rounded border border-border bg-surface/40 p-2">
                <div className="mb-1 flex items-center justify-between">
                  <label className="block text-xs font-medium text-text-muted">
                    {t("playground:studio.flashcardDeck", "Flashcard Deck")}
                  </label>
                  <Button
                    size={studioControlSize}
                    onClick={() => void loadFlashcardDecks()}
                    loading={loadingDecks}
                  >
                    {t("common:refresh", "Refresh")}
                  </Button>
                </div>
                <Select
                  size={studioControlSize}
                  className="w-full"
                  value={selectedFlashcardDeck}
                  onChange={(value) =>
                    setSelectedFlashcardDeck(
                      value === "auto" ? "auto" : Number(value)
                    )
                  }
                  options={[
                    {
                      value: "auto",
                      label: t(
                        "playground:studio.flashcardDeckAuto",
                        "Auto (first deck or create new)"
                      )
                    },
                    ...availableDecks.map((deck) => ({
                      value: deck.id,
                      label: deck.name
                    }))
                  ]}
                />
              </div>
              </div>
            )}
          </div>
        </div>
        </div>
      </div>

      {/* Generated Outputs Section - Collapsible */}
      <div className="border-b border-border">
        <button
          type="button"
          onClick={() => setOutputsExpanded(!outputsExpanded)}
          aria-expanded={outputsExpanded}
          aria-controls="studio-generated-outputs-section"
          className="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-surface2/50"
        >
          <h3 className="text-xs font-semibold uppercase text-text-muted">
            {t("playground:studio.generatedOutputs", "Generated Outputs")}
            {generatedArtifacts.length > 0 && (
              <span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                {generatedArtifacts.length}
              </span>
            )}
          </h3>
          {outputsExpanded ? (
            <ChevronUp className="h-4 w-4 text-text-muted" />
          ) : (
            <ChevronDown className="h-4 w-4 text-text-muted" />
          )}
        </button>
        <div
          id="studio-generated-outputs-section"
          ref={outputListContainerRef}
          hidden={!outputsExpanded}
          className="custom-scrollbar min-h-[10rem] overflow-y-auto px-4 pb-4"
          style={{ maxHeight: "40vh" }}
          onScroll={(event) => {
            if (!useVirtualizedOutputs) return
            setOutputListScrollTop(event.currentTarget.scrollTop)
          }}
          data-virtualized={useVirtualizedOutputs ? "true" : "false"}
          data-testid={
            useVirtualizedOutputs
              ? "generated-outputs-virtualized"
              : "generated-outputs-standard"
          }
        >
          {generatedArtifacts.length > 0 && (
            <div className="mb-2 rounded border border-border bg-surface/60 px-2.5 py-2 text-[11px] text-text-muted">
              {t(
                "playground:studio.usageSummary",
                "Estimated workspace usage: {{tokens}} tokens • ${{cost}}",
                {
                  tokens: Math.round(cumulativeUsage.tokens).toLocaleString(),
                  cost: cumulativeUsage.costUsd.toFixed(3)
                }
              )}
            </div>
          )}
          {generatedArtifacts.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <span className="text-xs text-text-muted">
                  {t("playground:studio.noOutputs", "No outputs generated yet")}
                </span>
              }
            />
          ) : (
            <div
              className="space-y-2"
              style={
                useVirtualizedOutputs
                  ? {
                      paddingTop: virtualOutputTopPadding,
                      paddingBottom: virtualOutputBottomPadding
                    }
                  : undefined
              }
            >
              {visibleArtifacts.map((artifact) => {
                const Icon = ARTIFACT_TYPE_ICONS[artifact.type] || FileText
                const StatusConfig = STATUS_ICONS[artifact.status]
                const StatusIcon = StatusConfig.icon
                const failedStatusDeleteLabel = t(
                  "playground:studio.deleteFailedOutput",
                  "Delete failed output"
                )

                return (
                  <div
                    key={artifact.id}
                    data-testid={`studio-artifact-card-${artifact.id}`}
                    className="group rounded-lg border border-border bg-surface2/50 p-3"
                  >
                    <div className="flex items-start gap-2">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-surface text-text-muted">
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="truncate text-sm font-medium text-text">
                            {artifact.title}
                          </p>
                          {artifact.status === "failed" ? (
                            <Tooltip title={failedStatusDeleteLabel}>
                              <button
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation()
                                  handleDeleteArtifact(artifact)
                                }}
                                onKeyDown={handleIconButtonKeyDown}
                                className="rounded p-0.5 hover:bg-error/10"
                                aria-label={failedStatusDeleteLabel}
                              >
                                <StatusIcon
                                  className={`h-4 w-4 shrink-0 ${StatusConfig.className}`}
                                />
                              </button>
                            </Tooltip>
                          ) : (
                            <StatusIcon
                              className={`h-4 w-4 shrink-0 ${StatusConfig.className}`}
                            />
                          )}
                        </div>
                        <p className="text-xs text-text-muted">
                          {artifact.createdAt.toLocaleString()}
                        </p>
                        {(artifact.totalTokens ||
                          artifact.estimatedTokens ||
                          artifact.totalCostUsd ||
                          artifact.estimatedCostUsd) && (
                          <p className="text-[11px] text-text-muted">
                            {t(
                              "playground:studio.usagePerArtifact",
                              "Tokens: {{tokens}} • Cost: ${{cost}}",
                              {
                                tokens: Math.round(
                                  artifact.totalTokens || artifact.estimatedTokens || 0
                                ).toLocaleString(),
                                cost: (
                                  artifact.totalCostUsd || artifact.estimatedCostUsd || 0
                                ).toFixed(3)
                              }
                            )}
                          </p>
                        )}
                        {artifact.status === "failed" && artifact.errorMessage && (
                          <p className="mt-1 text-xs text-error">
                            {artifact.errorMessage}
                          </p>
                        )}
                      </div>
                    </div>
                    {artifact.status === "completed" && (
                      <div className="mt-2 space-y-1.5">
                        <div
                          data-testid={`studio-artifact-primary-actions-${artifact.id}`}
                          role="group"
                          aria-label={t(
                            "playground:studio.primaryActions",
                            "Primary output actions"
                          )}
                          className="flex flex-wrap items-center gap-1 rounded border border-border/70 bg-surface/70 px-1.5 py-1"
                        >
                          {(artifact.content || artifact.audioUrl) && (
                            <Tooltip title={t("common:view", "View")}>
                              <button
                                type="button"
                                onClick={() => handleViewArtifact(artifact)}
                                onKeyDown={handleIconButtonKeyDown}
                                className="rounded p-1 text-text-muted hover:bg-surface2 hover:text-text"
                                aria-label={t("common:view", "View")}
                              >
                                <Eye className="h-4 w-4" />
                              </button>
                            </Tooltip>
                          )}
                          {(artifact.type === "flashcards" || artifact.type === "quiz") && (
                            <Tooltip title={t("common:edit", "Edit")}>
                              <button
                                type="button"
                                onClick={() => handleViewArtifact(artifact)}
                                onKeyDown={handleIconButtonKeyDown}
                                className="rounded p-1 text-text-muted hover:bg-surface2 hover:text-text"
                                aria-label={t("common:edit", "Edit")}
                                data-testid={`studio-artifact-edit-${artifact.id}`}
                              >
                                <Pencil className="h-4 w-4" />
                              </button>
                            </Tooltip>
                          )}
                          <Tooltip title={t("common:download", "Download")}>
                            <button
                              type="button"
                              onClick={() =>
                                artifact.type === "slides" && artifact.presentationId
                                  ? handleSlidesDownload(artifact)
                                  : handleDownloadArtifact(artifact)
                              }
                              onKeyDown={handleIconButtonKeyDown}
                              className="rounded p-1 text-text-muted hover:bg-surface2 hover:text-text"
                              aria-label={t("common:download", "Download")}
                            >
                              <Download className="h-4 w-4" />
                            </button>
                          </Tooltip>
                        </div>
                        <div
                          data-testid={`studio-artifact-secondary-actions-${artifact.id}`}
                          role="group"
                          aria-label={t(
                            "playground:studio.secondaryActions",
                            "Secondary output actions"
                          )}
                          className="flex flex-wrap items-center gap-1 rounded border border-border/60 bg-surface2/50 px-1.5 py-1"
                        >
                          <Dropdown
                            trigger={["click"]}
                            menu={{
                              items: [
                                {
                                  key: "replace",
                                  label: t(
                                    "playground:studio.regenerateReplace",
                                    "Replace existing"
                                  )
                                },
                                {
                                  key: "new_version",
                                  label: t(
                                    "playground:studio.regenerateNewVersion",
                                    "Create new version"
                                  )
                                }
                              ],
                              onClick: ({ key }) => {
                                const mode =
                                  key === "replace" ? "replace" : "new_version"
                                handleGenerateOutput(artifact.type, {
                                  mode,
                                  targetArtifactId: artifact.id
                                })
                              }
                            }}
                          >
                            <Tooltip
                              title={t(
                                "playground:studio.regenerateOptions",
                                "Regenerate options"
                              )}
                            >
                              <button
                                type="button"
                                onKeyDown={handleIconButtonKeyDown}
                                className="rounded p-1 text-text-muted hover:bg-surface hover:text-text"
                                aria-label={t(
                                  "playground:studio.regenerateOptions",
                                  "Regenerate options"
                                )}
                              >
                                <RefreshCw className="h-4 w-4" />
                              </button>
                            </Tooltip>
                          </Dropdown>
                          <Tooltip
                            title={t(
                              "playground:studio.discussAction",
                              "Discuss in chat"
                            )}
                          >
                            <button
                              type="button"
                              onClick={() => handleDiscussArtifact(artifact)}
                              onKeyDown={handleIconButtonKeyDown}
                              className="rounded p-1 text-text-muted hover:bg-surface hover:text-text"
                              aria-label={t(
                                "playground:studio.discussAction",
                                "Discuss in chat"
                              )}
                            >
                              <MessageCircle className="h-4 w-4" />
                            </button>
                          </Tooltip>
                          {artifact.content && (
                            <Dropdown
                              trigger={["click"]}
                              menu={{
                                items: [
                                  {
                                    key: "append",
                                    label: t(
                                      "playground:studio.saveToNotesAppend",
                                      "Append to notes"
                                    )
                                  },
                                  {
                                    key: "replace",
                                    label: t(
                                      "playground:studio.saveToNotesReplace",
                                      "Replace note draft"
                                    )
                                  }
                                ],
                                onClick: ({ key }) => {
                                  handleSaveArtifactToNotes(
                                    artifact,
                                    key === "replace" ? "replace" : "append"
                                  )
                                }
                              }}
                            >
                              <Tooltip
                                title={t(
                                  "playground:studio.saveToNotesAction",
                                  "Save to notes"
                                )}
                              >
                                <button
                                  type="button"
                                  onKeyDown={handleIconButtonKeyDown}
                                  className="rounded p-1 text-text-muted hover:bg-surface hover:text-text"
                                  aria-label={t(
                                    "playground:studio.saveToNotesAction",
                                    "Save to notes"
                                  )}
                                >
                                  <StickyNote className="h-4 w-4" />
                                </button>
                              </Tooltip>
                            </Dropdown>
                          )}
                          <Tooltip title={t("common:delete", "Delete")}>
                            <button
                              type="button"
                              onClick={() => handleDeleteArtifact(artifact)}
                              onKeyDown={handleIconButtonKeyDown}
                              className="rounded p-1 text-text-muted hover:bg-error/10 hover:text-error"
                              aria-label={t("common:delete", "Delete")}
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </Tooltip>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
          </div>
      </div>

      {/* Quick Notes Section - Collapsible, fills remaining height */}
      <div className="flex min-h-[220px] flex-1 flex-col">
        {notesExpanded ? (
          <QuickNotesSection onCollapse={() => setNotesExpanded(false)} />
        ) : (
          <button
            type="button"
            onClick={() => setNotesExpanded(true)}
            className="flex w-full items-center justify-between border-t border-border px-4 py-3 text-left transition hover:bg-surface2/50"
          >
            <h3 className="text-xs font-semibold uppercase text-text-muted">
              {t("playground:studio.quickNotes", "Quick Notes")}
            </h3>
            <ChevronDown className="h-4 w-4 text-text-muted" />
          </button>
        )}
      </div>
    </div>
  )
}

const downloadBlobFile = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

const MindMapArtifactViewer: React.FC<{
  title: string
  content: string
}> = ({ title, content }) => {
  const [zoom, setZoom] = useState(1)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mermaidCode = React.useMemo(() => extractMermaidCode(content), [content])
  const canRenderMermaid = React.useMemo(
    () => isLikelyMermaidDiagram(mermaidCode),
    [mermaidCode]
  )

  const handleExportSvg = () => {
    const svg = containerRef.current?.querySelector("svg")
    if (!svg) return
    const svgBlob = new Blob([svg.outerHTML], {
      type: "image/svg+xml;charset=utf-8"
    })
    downloadBlobFile(svgBlob, `${title || "mind-map"}.svg`)
  }

  const handleExportPng = async () => {
    if (!containerRef.current) return
    const html2canvas = (await import("html2canvas")).default
    const canvas = await html2canvas(containerRef.current, {
      backgroundColor: "#ffffff",
      scale: 2
    })
    canvas.toBlob((blob) => {
      if (!blob) return
      downloadBlobFile(blob, `${title || "mind-map"}.png`)
    }, "image/png")
  }

  if (!canRenderMermaid) {
    return (
      <div className="flex max-h-[70vh] flex-col gap-3">
        <div className="rounded border border-warning/40 bg-warning/10 p-3 text-sm text-text">
          Unable to render this mind map as a diagram. Showing raw output instead.
        </div>
        <div className="max-h-[56vh] overflow-auto whitespace-pre-wrap rounded border border-border bg-surface p-4 text-sm">
          {content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex max-h-[70vh] flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="small"
          icon={<ZoomOut className="h-3.5 w-3.5" />}
          onClick={() => setZoom((prev) => Math.max(0.5, Number((prev - 0.1).toFixed(2))))}
        >
          Zoom out
        </Button>
        <span className="text-xs text-text-muted">{Math.round(zoom * 100)}%</span>
        <Button
          size="small"
          icon={<ZoomIn className="h-3.5 w-3.5" />}
          onClick={() => setZoom((prev) => Math.min(2.5, Number((prev + 0.1).toFixed(2))))}
        >
          Zoom in
        </Button>
        <Button size="small" onClick={() => setZoom(1)}>
          Reset
        </Button>
        <Button size="small" onClick={handleExportSvg}>
          Export SVG
        </Button>
        <Button size="small" onClick={() => void handleExportPng()}>
          Export PNG
        </Button>
      </div>

      <div className="rounded border border-border bg-surface2/40 p-2 text-xs text-text-muted">
        Scroll to pan the diagram when zoomed in.
      </div>

      <div className="max-h-[56vh] overflow-auto rounded border border-border bg-surface p-4">
        <div
          ref={containerRef}
          style={{ transform: `scale(${zoom})`, transformOrigin: "top left" }}
          className="inline-block min-w-full"
        >
          <Mermaid code={mermaidCode} />
        </div>
      </div>
    </div>
  )
}

const DataTableArtifactViewer: React.FC<{
  title: string
  content: string
}> = ({ title, content }) => {
  const [query, setQuery] = useState("")
  const tableData = React.useMemo(() => parseMarkdownTable(content), [content])

  const filteredRows = React.useMemo(() => {
    if (!tableData) return []
    const normalized = query.trim().toLowerCase()
    if (!normalized) return tableData.rows
    return tableData.rows.filter((row) =>
      row.some((cell) => cell.toLowerCase().includes(normalized))
    )
  }, [query, tableData])

  const columns = React.useMemo(() => {
    if (!tableData) return []
    return tableData.headers.map((header, index) => ({
      title: header || `Column ${index + 1}`,
      dataIndex: `col_${index}`,
      key: `col_${index}`,
      sorter: (a: Record<string, string>, b: Record<string, string>) =>
        String(a[`col_${index}`] || "").localeCompare(
          String(b[`col_${index}`] || ""),
          undefined,
          { sensitivity: "base", numeric: true }
        )
    }))
  }, [tableData])

  const dataSource = React.useMemo(() => {
    return filteredRows.map((row, rowIndex) => {
      const record: Record<string, string> = { key: String(rowIndex) }
      row.forEach((cell, cellIndex) => {
        record[`col_${cellIndex}`] = cell
      })
      return record
    })
  }, [filteredRows])

  const handleDownloadCsv = () => {
    if (!tableData) return
    const csv = markdownTableToCsv(tableData)
    const csvBlob = new Blob([csv], { type: "text/csv;charset=utf-8" })
    downloadBlobFile(csvBlob, `${title || "data-table"}.csv`)
  }

  if (!tableData) {
    return (
      <div className="max-h-[70vh] overflow-y-auto whitespace-pre-wrap rounded border border-border bg-surface p-3 text-sm">
        {content}
      </div>
    )
  }

  return (
    <div className="flex max-h-[70vh] flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Filter table rows"
          prefix={<Search className="h-4 w-4 text-text-muted" />}
          className="w-72"
        />
        <Button size="small" onClick={handleDownloadCsv}>
          Export CSV
        </Button>
      </div>
      <AntTable
        columns={columns}
        dataSource={dataSource}
        pagination={{ pageSize: 10, size: "small" }}
        size="small"
        scroll={{ x: true, y: 420 }}
      />
    </div>
  )
}

const FlashcardArtifactEditor: React.FC<{
  cards: FlashcardDraft[]
  onSave: (cards: FlashcardDraft[]) => void
}> = ({ cards, onSave }) => {
  const { t } = useTranslation(["playground", "common"])
  const [messageApi, messageContextHolder] = message.useMessage()
  const [draftCards, setDraftCards] = useState<FlashcardDraft[]>(cards)

  const updateCard = (
    index: number,
    patch: Partial<FlashcardDraft>
  ) => {
    setDraftCards((previous) =>
      previous.map((card, cardIndex) =>
        cardIndex === index ? { ...card, ...patch } : card
      )
    )
  }

  const removeCard = React.useCallback(
    (index: number) => {
      const removedCard = draftCards[index]
      if (!removedCard) return
      const nextCards = draftCards.filter(
        (_card, cardIndex) => cardIndex !== index
      )
      const undoHandle = scheduleWorkspaceUndoAction({
        apply: () => {
          setDraftCards(nextCards)
        },
        undo: () => {
          setDraftCards((previous) => {
            const restored = [...previous]
            const insertionIndex = Math.max(0, Math.min(index, restored.length))
            restored.splice(insertionIndex, 0, removedCard)
            return restored
          })
        }
      })

      const undoMessageKey = `workspace-flashcard-remove-undo-${undoHandle.id}`
      const maybeOpen = (
        messageApi as { open?: (config: unknown) => void }
      ).open
      const messageConfig = {
        key: undoMessageKey,
        type: "warning",
        duration: WORKSPACE_UNDO_WINDOW_MS / 1000,
        content: t(
          "playground:studio.flashcardRemoved",
          "Flashcard removed."
        ),
        btn: (
          <Button
            size="small"
            type="link"
            onClick={() => {
              if (undoWorkspaceAction(undoHandle.id)) {
                messageApi.success(
                  t(
                    "playground:studio.flashcardRestored",
                    "Flashcard restored"
                  )
                )
              }
              messageApi.destroy(undoMessageKey)
            }}
          >
            {t("common:undo", "Undo")}
          </Button>
        )
      }

      if (typeof maybeOpen === "function") {
        maybeOpen(messageConfig)
      } else {
        const maybeWarning = (
          messageApi as { warning?: (content: string) => void }
        ).warning
        if (typeof maybeWarning === "function") {
          maybeWarning(t("playground:studio.flashcardRemoved", "Flashcard removed."))
        }
      }
    },
    [draftCards, messageApi, t]
  )

  return (
    <div className="flex max-h-[70vh] flex-col gap-3">
      {messageContextHolder}
      <div className="flex items-center justify-between">
        <p className="text-xs text-text-muted">
          Edit generated flashcards before reusing them.
        </p>
        <Button
          size="small"
          icon={<Plus className="h-3.5 w-3.5" />}
          onClick={() =>
            setDraftCards((previous) => [...previous, { front: "", back: "" }])
          }
        >
          Add card
        </Button>
      </div>

      <div className="max-h-[54vh] space-y-3 overflow-y-auto pr-1">
        {draftCards.map((card, index) => (
          <div key={`flashcard-${index}`} className="rounded border border-border bg-surface2/30 p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-medium text-text-muted">Card {index + 1}</span>
              <Button danger size="small" onClick={() => removeCard(index)}>
                Remove
              </Button>
            </div>
            <Input.TextArea
              value={card.front}
              onChange={(event) => updateCard(index, { front: event.target.value })}
              rows={2}
              placeholder="Front (question or term)"
              className="mb-2"
            />
            <Input.TextArea
              value={card.back}
              onChange={(event) => updateCard(index, { back: event.target.value })}
              rows={3}
              placeholder="Back (answer or definition)"
            />
          </div>
        ))}
      </div>

      <div className="flex justify-end">
        <Button
          type="primary"
          icon={<Save className="h-3.5 w-3.5" />}
          onClick={() =>
            onSave(
              draftCards.filter(
                (card) => card.front.trim().length > 0 && card.back.trim().length > 0
              )
            )
          }
        >
          Save changes
        </Button>
      </div>
    </div>
  )
}

const QuizArtifactEditor: React.FC<{
  questions: QuizQuestionDraft[]
  onSave: (questions: QuizQuestionDraft[]) => void
}> = ({ questions, onSave }) => {
  const { t } = useTranslation(["playground", "common"])
  const [messageApi, messageContextHolder] = message.useMessage()
  const [draftQuestions, setDraftQuestions] = useState<QuizQuestionDraft[]>(questions)

  const updateQuestion = (
    index: number,
    patch: Partial<QuizQuestionDraft>
  ) => {
    setDraftQuestions((previous) =>
      previous.map((question, questionIndex) =>
        questionIndex === index ? { ...question, ...patch } : question
      )
    )
  }

  const removeQuestion = React.useCallback(
    (index: number) => {
      const removedQuestion = draftQuestions[index]
      if (!removedQuestion) return
      const nextQuestions = draftQuestions.filter(
        (_question, questionIndex) => questionIndex !== index
      )
      const undoHandle = scheduleWorkspaceUndoAction({
        apply: () => {
          setDraftQuestions(nextQuestions)
        },
        undo: () => {
          setDraftQuestions((previous) => {
            const restored = [...previous]
            const insertionIndex = Math.max(0, Math.min(index, restored.length))
            restored.splice(insertionIndex, 0, removedQuestion)
            return restored
          })
        }
      })

      const undoMessageKey = `workspace-quiz-remove-undo-${undoHandle.id}`
      const maybeOpen = (
        messageApi as { open?: (config: unknown) => void }
      ).open
      const messageConfig = {
        key: undoMessageKey,
        type: "warning",
        duration: WORKSPACE_UNDO_WINDOW_MS / 1000,
        content: t(
          "playground:studio.quizQuestionRemoved",
          "Question removed."
        ),
        btn: (
          <Button
            size="small"
            type="link"
            onClick={() => {
              if (undoWorkspaceAction(undoHandle.id)) {
                messageApi.success(
                  t(
                    "playground:studio.quizQuestionRestored",
                    "Question restored"
                  )
                )
              }
              messageApi.destroy(undoMessageKey)
            }}
          >
            {t("common:undo", "Undo")}
          </Button>
        )
      }

      if (typeof maybeOpen === "function") {
        maybeOpen(messageConfig)
      } else {
        const maybeWarning = (
          messageApi as { warning?: (content: string) => void }
        ).warning
        if (typeof maybeWarning === "function") {
          maybeWarning(
            t("playground:studio.quizQuestionRemoved", "Question removed.")
          )
        }
      }
    },
    [draftQuestions, messageApi, t]
  )

  return (
    <div className="flex max-h-[70vh] flex-col gap-3">
      {messageContextHolder}
      <div className="flex items-center justify-between">
        <p className="text-xs text-text-muted">
          Edit generated quiz questions and answers.
        </p>
        <Button
          size="small"
          icon={<Plus className="h-3.5 w-3.5" />}
          onClick={() =>
            setDraftQuestions((previous) => [
              ...previous,
              { question: "", options: [], answer: "", explanation: "" }
            ])
          }
        >
          Add question
        </Button>
      </div>

      <div className="max-h-[54vh] space-y-3 overflow-y-auto pr-1">
        {draftQuestions.map((question, index) => (
          <div key={`quiz-${index}`} className="rounded border border-border bg-surface2/30 p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-medium text-text-muted">
                Question {index + 1}
              </span>
              <Button danger size="small" onClick={() => removeQuestion(index)}>
                Remove
              </Button>
            </div>
            <Input.TextArea
              value={question.question}
              onChange={(event) =>
                updateQuestion(index, { question: event.target.value })
              }
              rows={2}
              placeholder="Question prompt"
              className="mb-2"
            />
            <Input.TextArea
              value={question.options.join("\n")}
              onChange={(event) =>
                updateQuestion(index, {
                  options: event.target.value
                    .split("\n")
                    .map((option) => option.trim())
                    .filter(Boolean)
                })
              }
              rows={3}
              placeholder="Options (one per line)"
              className="mb-2"
            />
            <Input
              value={question.answer}
              onChange={(event) =>
                updateQuestion(index, { answer: event.target.value })
              }
              placeholder="Correct answer"
              className="mb-2"
            />
            <Input.TextArea
              value={question.explanation || ""}
              onChange={(event) =>
                updateQuestion(index, { explanation: event.target.value })
              }
              rows={2}
              placeholder="Explanation (optional)"
            />
          </div>
        ))}
      </div>

      <div className="flex justify-end">
        <Button
          type="primary"
          icon={<Save className="h-3.5 w-3.5" />}
          onClick={() =>
            onSave(
              draftQuestions.filter(
                (question) =>
                  question.question.trim().length > 0 &&
                  question.answer.trim().length > 0
              )
            )
          }
        >
          Save changes
        </Button>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Output Generation Functions
// ─────────────────────────────────────────────────────────────────────────────

async function generateSummary(
  mediaIds: number[],
  workspaceTag?: string,
  abortSignal?: AbortSignal
): Promise<GenerationResult> {
  // Use RAG to get content and generate summary via chat
  const ragResponse = await tldwClient.ragSearch(
    "Provide a comprehensive summary of the key points and main ideas.",
    {
      media_ids: mediaIds,
      top_k: 20,
      enable_generation: true,
      enable_citations: true,
      timeoutMs: STUDIO_GENERATION_RAG_TIMEOUT_MS,
      signal: abortSignal
    }
  )
  const usage = extractUsageMetrics(ragResponse)

  return {
    content: extractRequiredRagText(ragResponse, "summary"),
    ...usage
  }
}

async function generateReport(
  mediaIds: number[],
  workspaceTag?: string,
  abortSignal?: AbortSignal
): Promise<GenerationResult> {
  const ragResponse = await tldwClient.ragSearch(
    `Generate a detailed report with the following sections:
1. Executive Summary
2. Key Findings
3. Detailed Analysis
4. Conclusions
5. Recommendations

Use the provided sources to create a comprehensive report.`,
    {
      media_ids: mediaIds,
      top_k: 30,
      enable_generation: true,
      enable_citations: true,
      timeoutMs: STUDIO_GENERATION_RAG_TIMEOUT_MS,
      signal: abortSignal
    }
  )
  const usage = extractUsageMetrics(ragResponse)

  return {
    content: extractRequiredRagText(ragResponse, "report"),
    ...usage
  }
}

async function generateTimeline(
  mediaIds: number[],
  workspaceTag?: string,
  abortSignal?: AbortSignal
): Promise<GenerationResult> {
  const ragResponse = await tldwClient.ragSearch(
    `Extract and organize all events, dates, and chronological information into a timeline format.
Present the timeline as:
- [Date/Period] - Event description

List events in chronological order.`,
    {
      media_ids: mediaIds,
      top_k: 30,
      enable_generation: true,
      enable_citations: true,
      timeoutMs: STUDIO_GENERATION_RAG_TIMEOUT_MS,
      signal: abortSignal
    }
  )
  const usage = extractUsageMetrics(ragResponse)

  return {
    content: extractRequiredRagText(ragResponse, "timeline"),
    ...usage
  }
}

async function generateCompareSources(
  mediaIds: number[],
  workspaceTag?: string,
  abortSignal?: AbortSignal
): Promise<GenerationResult> {
  const ragResponse = await tldwClient.ragSearch(
    `Compare the selected sources and produce:
1. A short synthesis of where they agree.
2. A list of key disagreements or conflicting claims.
3. Evidence strength notes for each disagreement.
4. Open questions that need additional verification.

Use markdown headings and bullet lists. Cite source-specific evidence when possible.`,
    {
      media_ids: mediaIds,
      top_k: 30,
      enable_generation: true,
      enable_citations: true,
      timeoutMs: STUDIO_GENERATION_RAG_TIMEOUT_MS,
      signal: abortSignal
    }
  )
  const usage = extractUsageMetrics(ragResponse)
  const content = extractRequiredRagText(ragResponse, "comparison")

  return {
    content,
    ...usage,
    data: {
      sourceCount: mediaIds.length,
      workspaceTag: workspaceTag || null
    }
  }
}

async function generateQuizFromMedia(
  mediaIds: number[],
  workspaceTag?: string,
  abortSignal?: AbortSignal
): Promise<GenerationResult> {
  const uniqueMediaIds = Array.from(new Set(mediaIds))
  if (uniqueMediaIds.length === 0) {
    throw new Error("No media selected for quiz generation")
  }

  const generationResponses: Array<{
    mediaId: number
    response: any
    usage: UsageMetrics
  }> = []
  for (const mediaId of uniqueMediaIds) {
    const response = await generateQuiz(
      {
        media_id: mediaId,
        num_questions: Math.max(3, Math.ceil(10 / uniqueMediaIds.length)),
        question_types: ["multiple_choice", "true_false"],
        difficulty: "mixed",
        workspace_tag: workspaceTag || undefined
      },
      { signal: abortSignal }
    )
    generationResponses.push({
      mediaId,
      response,
      usage: extractUsageMetrics(response)
    })
  }

  const mergedQuestions = generationResponses.flatMap(({ mediaId, response }) =>
    (response.questions || []).map((question: any) => ({
      question: String(question.question_text || "").trim(),
      options: Array.isArray(question.options)
        ? question.options.map((option: unknown) => String(option))
        : [],
      answer: String(question.correct_answer || "").trim(),
      explanation: question.explanation
        ? String(question.explanation)
        : undefined,
      sourceMediaId: mediaId
    }))
  )

  const limitedQuestions = mergedQuestions.slice(0, 20)
  const content = formatQuizQuestionsContent(
    limitedQuestions.map((question) => ({
      question: question.question,
      options: question.options,
      answer: question.answer,
      explanation: question.explanation
    })),
    generationResponses[0]?.response?.quiz?.name || "Workspace Quiz"
  )

  const totalTokens = generationResponses.reduce(
    (acc, item) => acc + (item.usage.totalTokens || 0),
    0
  )
  const totalCostUsd = generationResponses.reduce(
    (acc, item) => acc + (item.usage.totalCostUsd || 0),
    0
  )

  return {
    serverId: generationResponses[0]?.response?.quiz?.id,
    content,
    totalTokens: totalTokens > 0 ? totalTokens : undefined,
    totalCostUsd:
      totalCostUsd > 0 ? Number(totalCostUsd.toFixed(4)) : undefined,
    data: {
      questions: limitedQuestions,
      sourceMediaIds: uniqueMediaIds
    }
  }
}

async function generateFlashcards(
  mediaIds: number[],
  preferredDeckId: number | undefined,
  workspaceTag?: string,
  abortSignal?: AbortSignal
): Promise<GenerationResult> {
  // First, get content via RAG
  const ragResponse = await tldwClient.ragSearch(
    `Extract key concepts, definitions, and important facts that would make good flashcards.
Format each as:
Front: [Question or term]
Back: [Answer or definition]

Generate 10-15 flashcards.`,
    {
      media_ids: mediaIds,
      top_k: 20,
      enable_generation: true,
      timeoutMs: STUDIO_GENERATION_RAG_TIMEOUT_MS,
      signal: abortSignal
    }
  )
  const usage = extractUsageMetrics(ragResponse)

  const content = ragResponse?.generation || ragResponse?.answer || ""

  // Parse and create flashcards
  const flashcards = parseFlashcards(content)
  if (!flashcards.length) {
    throw new Error("Failed to parse generated flashcards from model output")
  }

  // Ensure we have a deck
  const decks = await listDecks({ signal: abortSignal })
  let deckId: number | undefined

  if (preferredDeckId && decks.some((deck) => deck.id === preferredDeckId)) {
    deckId = preferredDeckId
  } else if (decks.length === 0) {
    const newDeck = await createDeck(
      { name: "Workspace Flashcards" },
      { signal: abortSignal }
    )
    deckId = newDeck.id
  } else {
    deckId = decks[0].id
  }

  // Create flashcards
  let createdCount = 0
  let firstCreateError: unknown = null
  for (const card of flashcards) {
    try {
      await createFlashcard({
        deck_id: deckId,
        front: card.front,
        back: card.back,
        source_ref_type: "media",
        source_ref_id: mediaIds.join(",")
      }, { signal: abortSignal })
      createdCount += 1
    } catch (error) {
      if (firstCreateError == null) {
        firstCreateError = error
      }
    }
  }

  if (createdCount === 0) {
    if (firstCreateError instanceof Error && firstCreateError.message) {
      throw new Error(`Failed to save generated flashcards: ${firstCreateError.message}`)
    }
    throw new Error("Failed to save generated flashcards")
  }

  const failedCount = flashcards.length - createdCount
  const summaryLine =
    failedCount > 0
      ? `Created ${createdCount} of ${flashcards.length} flashcards (${failedCount} failed)`
      : `Created ${createdCount} flashcards`

  return {
    content: `${summaryLine}\n\n${content}`,
    ...usage,
    data: {
      flashcards,
      deckId,
      sourceMediaIds: mediaIds
    }
  }
}

async function generateMindMap(
  mediaIds: number[],
  abortSignal?: AbortSignal
): Promise<GenerationResult> {
  const ragResponse = await tldwClient.ragSearch(
    `Analyze the content and create a mind map in Mermaid format.
Use the following structure:
\`\`\`mermaid
mindmap
  root((Main Topic))
    Branch 1
      Sub-topic 1.1
      Sub-topic 1.2
    Branch 2
      Sub-topic 2.1
      Sub-topic 2.2
\`\`\`

Identify the central theme and 3-5 main branches with their sub-topics.`,
    {
      media_ids: mediaIds,
      top_k: 20,
      enable_generation: true,
      timeoutMs: STUDIO_GENERATION_RAG_TIMEOUT_MS,
      signal: abortSignal
    }
  )
  const usage = extractUsageMetrics(ragResponse)

  const content = extractRequiredRagText(ragResponse, "mind map")
  return {
    content,
    ...usage,
    data: {
      mermaid: extractMermaidCode(content)
    }
  }
}

async function generateAudioOverview(
  mediaIds: number[],
  audioSettings: import("@/types/workspace").AudioGenerationSettings,
  abortSignal?: AbortSignal
): Promise<GenerationResult> {
  // First generate a spoken overview script
  const ragResponse = await tldwClient.ragSearch(
    `Create a spoken overview script (2-3 minutes when read aloud) that:
1. Introduces the topic
2. Covers the main points
3. Concludes with key takeaways

Write in a conversational, easy-to-listen style. Do not include any stage directions, speaker labels, or formatting - just the spoken text.`,
    {
      media_ids: mediaIds,
      top_k: 15,
      enable_generation: true,
      timeoutMs: STUDIO_GENERATION_RAG_TIMEOUT_MS,
      signal: abortSignal
    }
  )
  const usage = extractUsageMetrics(ragResponse)

  const script = ragResponse?.generation || ragResponse?.answer || ""

  if (!script.trim()) {
    throw new Error("Failed to generate audio script")
  }

  // Use browser TTS if selected
  if (audioSettings.provider === "browser") {
    return {
      content: script,
      audioFormat: "browser",
      ...usage
    }
  }

  // Generate audio using TTS API with user settings
  try {
    const audioBuffer = await tldwClient.synthesizeSpeech(script, {
      model: audioSettings.model,
      voice: audioSettings.voice,
      responseFormat: audioSettings.format,
      speed: audioSettings.speed,
      signal: abortSignal
    })

    // Determine MIME type based on format
    const mimeTypes: Record<string, string> = {
      mp3: "audio/mpeg",
      wav: "audio/wav",
      opus: "audio/opus",
      aac: "audio/aac",
      flac: "audio/flac"
    }

    // Create a blob URL for playback
    const audioBlob = new Blob([audioBuffer], {
      type: mimeTypes[audioSettings.format] || "audio/mpeg"
    })
    const audioUrl = URL.createObjectURL(audioBlob)

    return {
      content: script,
      audioUrl,
      audioFormat: audioSettings.format,
      ...usage
    }
  } catch (ttsError) {
    if (isAbortLikeError(ttsError)) {
      throw ttsError
    }
    console.error("TTS generation failed:", ttsError)
    throw new Error("Audio generation failed because speech synthesis did not return audio.")
  }
}

async function generateSlidesFromApi(
  mediaId: number,
  abortSignal?: AbortSignal
): Promise<GenerationResult> {
  try {
    // Use the Slides API to generate a real presentation
    const presentation = await tldwClient.generateSlidesFromMedia(mediaId, {
      signal: abortSignal
    })
    const usage = extractUsageMetrics(presentation)

    // Format slides as readable content
    let content = `# ${presentation.title}\n\n`
    if (presentation.description) {
      content += `${presentation.description}\n\n`
    }
    content += `**Theme:** ${presentation.theme}\n`
    content += `**Slides:** ${presentation.slides.length}\n\n---\n\n`

    for (const slide of presentation.slides) {
      content += `## Slide ${slide.order + 1}: ${slide.title || "(Untitled)"}\n`
      content += `*Layout: ${slide.layout}*\n\n`
      content += `${slide.content}\n`
      if (slide.speaker_notes) {
        content += `\n> **Speaker Notes:** ${slide.speaker_notes}\n`
      }
      content += "\n---\n\n"
    }

    return {
      content,
      presentationId: presentation.id,
      presentationVersion: presentation.version,
      ...usage
    }
  } catch (error) {
    if (isAbortLikeError(error)) {
      throw error
    }
    // Fallback to RAG-based generation if API fails
    console.error("Slides API failed, falling back to RAG:", error)
    return generateSlidesFallback([mediaId], abortSignal)
  }
}

async function generateSlidesFallback(
  mediaIds: number[],
  abortSignal?: AbortSignal
): Promise<GenerationResult> {
  const ragResponse = await tldwClient.ragSearch(
    `Create a presentation outline with 8-12 slides:

For each slide provide:
# Slide [Number]: [Title]
- Bullet point 1
- Bullet point 2
- Bullet point 3

Include:
1. Title slide
2. Introduction/Overview
3-10. Main content slides
11. Summary/Key Takeaways
12. Conclusion/Q&A`,
    {
      media_ids: mediaIds,
      top_k: 25,
      enable_generation: true,
      timeoutMs: STUDIO_GENERATION_RAG_TIMEOUT_MS,
      signal: abortSignal
    }
  )
  const usage = extractUsageMetrics(ragResponse)

  return {
    content: extractRequiredRagText(ragResponse, "slide"),
    ...usage
  }
}

async function generateDataTable(
  mediaIds: number[],
  workspaceTag?: string,
  abortSignal?: AbortSignal
): Promise<GenerationResult> {
  const ragResponse = await tldwClient.ragSearch(
    `Extract structured data from the content and format it as a markdown table.
Identify:
- Key entities (people, organizations, places, products)
- Attributes and values
- Relationships and comparisons

Format as:
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |`,
    {
      media_ids: mediaIds,
      top_k: 25,
      enable_generation: true,
      timeoutMs: STUDIO_GENERATION_RAG_TIMEOUT_MS,
      signal: abortSignal
    }
  )
  const usage = extractUsageMetrics(ragResponse)

  const content = extractRequiredRagText(ragResponse, "data table")
  const parsedTable = parseMarkdownTable(content)

  return {
    content,
    ...usage,
    data: parsedTable ? { table: parsedTable } : undefined
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null

function extractMermaidCode(content: string): string {
  const fencedMatch = content.match(/```(?:mermaid)?\s*([\s\S]*?)```/i)
  if (fencedMatch?.[1]) {
    return fencedMatch[1].trim()
  }
  return content.trim()
}

function isLikelyMermaidDiagram(code: string): boolean {
  const firstLine = code
    .split("\n")
    .map((line) => line.trim())
    .find((line) => line.length > 0)
  if (!firstLine) return false
  return /^(mindmap|graph|flowchart|sequenceDiagram|stateDiagram(?:-v2)?|gantt)\b/i.test(
    firstLine
  )
}

function parseTableCells(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim())
}

function parseMarkdownTable(content: string): MarkdownTableData | null {
  const lines = content
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("|"))

  if (lines.length < 2) return null
  const separatorIndex = lines.findIndex((line) =>
    /^\|(?:\s*:?-{3,}:?\s*\|)+\s*$/.test(line)
  )
  if (separatorIndex <= 0) return null

  const headers = parseTableCells(lines[separatorIndex - 1]).filter(Boolean)
  if (headers.length === 0) return null

  const rows = lines
    .slice(separatorIndex + 1)
    .map((line) => parseTableCells(line))
    .filter((row) => row.some((cell) => cell.length > 0))
    .map((row) => {
      if (row.length === headers.length) return row
      if (row.length < headers.length) {
        return [...row, ...new Array(headers.length - row.length).fill("")]
      }
      return row.slice(0, headers.length)
    })

  if (rows.length === 0) return null
  return { headers, rows }
}

function markdownTableToCsv(table: MarkdownTableData): string {
  const escapeCsv = (value: string) => {
    if (/[",\n]/.test(value)) {
      return `"${value.replace(/"/g, '""')}"`
    }
    return value
  }
  const headerLine = table.headers.map(escapeCsv).join(",")
  const rows = table.rows.map((row) => row.map(escapeCsv).join(","))
  return [headerLine, ...rows].join("\n")
}

function parseFlashcards(
  content: string
): FlashcardDraft[] {
  const cards: FlashcardDraft[] = []
  const lines = content.split("\n")
  let currentFront = ""
  let currentBack = ""

  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.toLowerCase().startsWith("front:")) {
      if (currentFront && currentBack) {
        cards.push({ front: currentFront, back: currentBack })
      }
      currentFront = trimmed.substring(6).trim()
      currentBack = ""
    } else if (trimmed.toLowerCase().startsWith("back:")) {
      currentBack = trimmed.substring(5).trim()
    }
  }

  if (currentFront && currentBack) {
    cards.push({ front: currentFront, back: currentBack })
  }

  return cards
}

function formatFlashcardsContent(cards: FlashcardDraft[]): string {
  return cards
    .map((card) => `Front: ${card.front}\nBack: ${card.back}`)
    .join("\n\n")
}

function parseQuizQuestions(content: string): QuizQuestionDraft[] {
  const questions: QuizQuestionDraft[] = []
  const lines = content.split("\n")
  let current: QuizQuestionDraft | null = null

  for (const rawLine of lines) {
    const line = rawLine.trim()
    if (!line) continue

    const questionMatch = line.match(/^Q\d+:\s*(.+)$/i)
    if (questionMatch) {
      if (current && current.question) {
        questions.push(current)
      }
      current = {
        question: questionMatch[1].trim(),
        options: [],
        answer: "",
        explanation: ""
      }
      continue
    }

    if (!current) continue

    const optionMatch = line.match(/^(?:[-*]\s*)?[A-Z]\.\s*(.+)$/)
    if (optionMatch) {
      current.options.push(optionMatch[1].trim())
      continue
    }

    if (line.toLowerCase().startsWith("answer:")) {
      current.answer = line.substring("answer:".length).trim()
      continue
    }

    if (line.toLowerCase().startsWith("explanation:")) {
      current.explanation = line.substring("explanation:".length).trim()
    }
  }

  if (current && current.question) {
    questions.push(current)
  }
  return questions
}

function formatQuizQuestionsContent(
  questions: QuizQuestionDraft[],
  title: string
): string {
  let content = `Quiz: ${title}\n`
  content += `Total Questions: ${questions.length}\n\n`
  questions.forEach((question, index) => {
    content += `Q${index + 1}: ${question.question}\n`
    question.options.forEach((option, optionIndex) => {
      content += `  ${String.fromCharCode(65 + optionIndex)}. ${option}\n`
    })
    content += `Answer: ${question.answer}\n`
    if (question.explanation && question.explanation.trim().length > 0) {
      content += `Explanation: ${question.explanation}\n`
    }
    content += "\n"
  })
  return content
}

function getArtifactFlashcards(artifact: GeneratedArtifact): FlashcardDraft[] {
  const flashcardsFromData = isRecord(artifact.data) &&
    Array.isArray(artifact.data.flashcards)
      ? artifact.data.flashcards
          .map((entry) => {
            if (!isRecord(entry)) return null
            const front = String(entry.front || "").trim()
            const back = String(entry.back || "").trim()
            if (!front || !back) return null
            return { front, back }
          })
          .filter((entry): entry is FlashcardDraft => entry !== null)
      : []

  if (flashcardsFromData.length > 0) {
    return flashcardsFromData
  }

  const parsed = parseFlashcards(artifact.content || "")
  if (parsed.length > 0) return parsed
  return [{ front: "", back: "" }]
}

function getArtifactQuizQuestions(artifact: GeneratedArtifact): QuizQuestionDraft[] {
  const questionsFromData = isRecord(artifact.data) &&
    Array.isArray(artifact.data.questions)
      ? artifact.data.questions
          .map((entry): ParsedQuizQuestion | null => {
            if (!isRecord(entry)) return null
            const question = String(
              entry.question || entry.question_text || ""
            ).trim()
            const options = Array.isArray(entry.options)
              ? entry.options.map((option) => String(option).trim()).filter(Boolean)
              : []
            const answer = String(
              entry.answer || entry.correct_answer || ""
            ).trim()
            const explanation = entry.explanation
              ? String(entry.explanation)
              : ""
            if (!question) return null
            return { question, options, answer, explanation }
          })
          .filter((entry): entry is ParsedQuizQuestion => entry !== null)
      : []

  if (questionsFromData.length > 0) {
    return questionsFromData
  }

  const parsed = parseQuizQuestions(artifact.content || "")
  if (parsed.length > 0) return parsed
  return [{ question: "", options: [], answer: "", explanation: "" }]
}

function getFileExtension(type: ArtifactType): string {
  switch (type) {
    case "summary":
    case "report":
    case "timeline":
      return "md"
    case "quiz":
    case "flashcards":
      return "json"
    case "mindmap":
      return "mmd"
    case "slides":
      return "md"
    case "data_table":
      return "csv"
    case "audio_overview":
      return "mp3"
    default:
      return "txt"
  }
}

export default StudioPane
