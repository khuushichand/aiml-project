import React, { useState, useEffect, useRef } from "react"
import { useTranslation } from "react-i18next"
import {
  Headphones,
  FileText,
  GitBranch,
  FileSpreadsheet,
  Layers,
  HelpCircle,
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
import { Button, Empty, Tooltip, Input, Modal, message, Slider, Select, Dropdown, Table as AntTable } from "antd"
import { useMobile } from "@/hooks/useMediaQuery"
import { useWorkspaceStore } from "@/store/workspace"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { generateQuiz } from "@/services/quizzes"
import { createFlashcard, createDeck, listDecks } from "@/services/flashcards"
import { fetchTldwVoiceCatalog, type TldwVoice } from "@/services/tldw/audio-voices"
import { inferTldwProviderFromModel } from "@/services/tts-provider"
import { OUTPUT_TYPES } from "@/types/workspace"
import type { ArtifactType, GeneratedArtifact, AudioTtsProvider } from "@/types/workspace"
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
    label: "Audio Overview",
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
    types: ["summary", "report", "timeline", "data_table"]
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

const WORKSPACE_DISCUSS_EVENT = "workspace-playground:discuss-artifact"
const VOICE_PREVIEW_TEXT =
  "This is a quick voice preview from your current audio settings."

const isAbortLikeError = (error: unknown): boolean => {
  if ((error as { name?: string } | null)?.name === "AbortError") {
    return true
  }
  const message = error instanceof Error ? error.message : String(error ?? "")
  return /abort|cancel/i.test(message)
}

export const estimateGenerationSeconds = (
  type: ArtifactType,
  sourceCount: number
): number => {
  const normalizedSourceCount = Math.max(1, sourceCount)
  const baseSeconds: Record<ArtifactType, number> = {
    summary: 8,
    report: 16,
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

/**
 * StudioPane - Right pane for generating outputs
 */
export const StudioPane: React.FC<StudioPaneProps> = ({ onHide }) => {
  const { t } = useTranslation(["playground", "common"])
  const isMobile = useMobile()
  const [messageApi, contextHolder] = message.useMessage()

  // Store state
  const selectedSourceIds = useWorkspaceStore((s) => s.selectedSourceIds)
  const getSelectedMediaIds = useWorkspaceStore((s) => s.getSelectedMediaIds)
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
  const previewAudioRef = useRef<HTMLAudioElement | null>(null)

  // Local state for collapsible sections
  const [studioExpanded, setStudioExpanded] = useState(true)
  const [outputsExpanded, setOutputsExpanded] = useState(true)
  const [notesExpanded, setNotesExpanded] = useState(true)
  const generationAbortRef = useRef<AbortController | null>(null)

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

  const hasSelectedSources = selectedSourceIds.length > 0
  const selectedMediaCount = Math.max(
    getSelectedMediaIds().length,
    selectedSourceIds.length
  )
  const contextualAudioSettingsVisible =
    activeOutputType === "audio_overview" ||
    generatingOutputType === "audio_overview"
  const showAudioSettingsPanel = showTtsSettings || contextualAudioSettingsVisible
  const studioControlSize = isMobile ? "large" : "small"
  const mobileSliderClassName = isMobile
    ? "[&_.ant-slider-rail]:!h-2 [&_.ant-slider-track]:!h-2 [&_.ant-slider-handle]:!h-5 [&_.ant-slider-handle]:!w-5"
    : undefined
  const etaSeconds =
    isGeneratingOutput && generatingOutputType
      ? estimateGenerationSeconds(
          generatingOutputType,
          Math.max(1, selectedMediaCount)
        )
      : null

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
    if (!hasSelectedSources) return

    const mediaIds = getSelectedMediaIds()
    if (mediaIds.length === 0) return

    const activeAbort = new AbortController()
    generationAbortRef.current = activeAbort

    // Start generation
    setIsGeneratingOutput(true, type)

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
            status: "generating"
          })
        }
      } else {
        artifact = addArtifact({
          type,
          title: `${artifactLabel}`,
          status: "generating"
        })
      }

      let result: {
        serverId?: number | string
        content?: string
        audioUrl?: string
        audioFormat?: string
        presentationId?: string
        presentationVersion?: number
        data?: Record<string, unknown>
      } = {}

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

      // Update artifact with success
      if (!artifact) {
        throw new Error("Artifact placeholder was not created")
      }

      updateArtifactStatus(artifact.id, "completed", {
        serverId: result.serverId,
        content: result.content,
        audioUrl: result.audioUrl,
        audioFormat: result.audioFormat,
        presentationId: result.presentationId,
        presentationVersion: result.presentationVersion,
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

  return (
    <div className="flex h-full flex-col">
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
              className="hidden rounded p-1.5 text-text-muted transition hover:bg-surface2 hover:text-text lg:block"
              aria-label={t("playground:workspace.hideStudio", "Hide studio")}
            >
              <PanelRightClose className="h-4 w-4" />
            </button>
          </Tooltip>
        )}
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
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-text-muted">
              {t(
                "playground:studio.generatingWithEta",
                "Generating {{type}}... (~{{seconds}}s for {{count}} source{{suffix}})",
                {
                  type:
                    OUTPUT_BUTTONS.find(
                      (button) => button.type === generatingOutputType
                    )?.label || generatingOutputType || "output",
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
        )}
        <div className="space-y-4">
          {OUTPUT_GROUPS.map((group) => (
            <section key={group.id} aria-label={group.label}>
              <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                {group.label}
              </h4>
              <div className="grid grid-cols-2 gap-3">
                {group.types.map((type) => {
                  const button = OUTPUT_BUTTONS.find((entry) => entry.type === type)
                  if (!button) return null
                  const { label, icon: Icon, description } = button
                  const isGenerating =
                    isGeneratingOutput && generatingOutputType === type
                  const isDisabled = !hasSelectedSources || isGeneratingOutput

                  return (
                    <Tooltip
                      key={type}
                      title={
                        !hasSelectedSources
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
                        className={`flex flex-col items-center justify-center rounded-lg border p-3 transition-colors ${
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
                      </button>
                    </Tooltip>
                  )
                })}
              </div>
            </section>
          ))}
        </div>
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
                "Select Audio Overview to configure TTS voice and speed."
              )}
            </p>
          )}
          <button
            type="button"
            onClick={() => setShowTtsSettings(!showTtsSettings)}
            aria-expanded={showAudioSettingsPanel}
            aria-controls="studio-audio-settings-panel"
            className="flex w-full items-center justify-between rounded border border-border bg-surface2/50 px-3 py-2 text-xs text-text-muted hover:bg-surface2"
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
              className={`mt-2 rounded border border-border bg-surface2/30 p-3 ${
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
          hidden={!outputsExpanded}
          className="custom-scrollbar min-h-[10rem] overflow-y-auto px-4 pb-4"
          style={{ maxHeight: "40vh" }}
        >
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
            <div className="space-y-2">
              {generatedArtifacts.map((artifact) => {
                const Icon = ARTIFACT_TYPE_ICONS[artifact.type] || FileText
                const StatusConfig = STATUS_ICONS[artifact.status]
                const StatusIcon = StatusConfig.icon

                return (
                  <div
                    key={artifact.id}
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
                          <StatusIcon
                            className={`h-4 w-4 shrink-0 ${StatusConfig.className}`}
                          />
                        </div>
                        <p className="text-xs text-text-muted">
                          {artifact.createdAt.toLocaleString()}
                        </p>
                        {artifact.status === "failed" && artifact.errorMessage && (
                          <p className="mt-1 text-xs text-error">
                            {artifact.errorMessage}
                          </p>
                        )}
                      </div>
                    </div>
                    {artifact.status === "completed" && (
                      <div className="mt-2 flex gap-1">
                        {(artifact.content || artifact.audioUrl) && (
                          <Tooltip title={t("common:view", "View")}>
                            <button
                              type="button"
                              onClick={() => handleViewArtifact(artifact)}
                            className="rounded p-1 text-text-muted hover:bg-surface hover:text-text"
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
                              className="rounded p-1 text-text-muted hover:bg-surface hover:text-text"
                              aria-label={t("common:edit", "Edit")}
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
                            className="rounded p-1 text-text-muted hover:bg-surface hover:text-text"
                            aria-label={t("common:download", "Download")}
                          >
                            <Download className="h-4 w-4" />
                          </button>
                        </Tooltip>
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
                                targetArtifactId:
                                  mode === "replace" ? artifact.id : undefined
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
                            className="rounded p-1 text-text-muted hover:bg-error/10 hover:text-error"
                            aria-label={t("common:delete", "Delete")}
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </Tooltip>
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

  const removeCard = (index: number) => {
    setDraftCards((previous) => previous.filter((_card, cardIndex) => cardIndex !== index))
  }

  return (
    <div className="flex max-h-[70vh] flex-col gap-3">
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

  const removeQuestion = (index: number) => {
    setDraftQuestions((previous) =>
      previous.filter((_question, questionIndex) => questionIndex !== index)
    )
  }

  return (
    <div className="flex max-h-[70vh] flex-col gap-3">
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
): Promise<{ serverId?: number; content?: string }> {
  // Use RAG to get content and generate summary via chat
  const ragResponse = await tldwClient.ragSearch(
    "Provide a comprehensive summary of the key points and main ideas.",
    {
      media_ids: mediaIds,
      top_k: 20,
      enable_generation: true,
      enable_citations: true,
      signal: abortSignal
    }
  )

  return {
    content: ragResponse?.generation || ragResponse?.answer || "Summary generation failed"
  }
}

async function generateReport(
  mediaIds: number[],
  workspaceTag?: string,
  abortSignal?: AbortSignal
): Promise<{ serverId?: number; content?: string }> {
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
      signal: abortSignal
    }
  )

  return {
    content: ragResponse?.generation || ragResponse?.answer || "Report generation failed"
  }
}

async function generateTimeline(
  mediaIds: number[],
  workspaceTag?: string,
  abortSignal?: AbortSignal
): Promise<{ serverId?: number; content?: string }> {
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
      signal: abortSignal
    }
  )

  return {
    content: ragResponse?.generation || ragResponse?.answer || "Timeline generation failed"
  }
}

async function generateQuizFromMedia(
  mediaIds: number[],
  workspaceTag?: string,
  abortSignal?: AbortSignal
): Promise<{ serverId?: number; content?: string; data?: Record<string, unknown> }> {
  const uniqueMediaIds = Array.from(new Set(mediaIds))
  if (uniqueMediaIds.length === 0) {
    throw new Error("No media selected for quiz generation")
  }

  const generationResponses: Array<{ mediaId: number; response: any }> = []
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
    generationResponses.push({ mediaId, response })
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

  return {
    serverId: generationResponses[0]?.response?.quiz?.id,
    content,
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
): Promise<{ serverId?: number; content?: string; data?: Record<string, unknown> }> {
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
      signal: abortSignal
    }
  )

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
): Promise<{ serverId?: number; content?: string; data?: Record<string, unknown> }> {
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
      signal: abortSignal
    }
  )

  const content =
    ragResponse?.generation || ragResponse?.answer || "Mind map generation failed"
  return {
    content,
    data: {
      mermaid: extractMermaidCode(content)
    }
  }
}

async function generateAudioOverview(
  mediaIds: number[],
  audioSettings: import("@/types/workspace").AudioGenerationSettings,
  abortSignal?: AbortSignal
): Promise<{ serverId?: number; content?: string; audioUrl?: string; audioFormat?: string }> {
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
      signal: abortSignal
    }
  )

  const script = ragResponse?.generation || ragResponse?.answer || ""

  if (!script.trim()) {
    throw new Error("Failed to generate audio script")
  }

  // Use browser TTS if selected
  if (audioSettings.provider === "browser") {
    return {
      content: script,
      audioFormat: "browser"
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
      audioFormat: audioSettings.format
    }
  } catch (ttsError) {
    if (isAbortLikeError(ttsError)) {
      throw ttsError
    }
    // If TTS fails, fall back to returning just the script
    console.error("TTS generation failed:", ttsError)
    return {
      content: `[Audio Script]\n\n${script}\n\n[Note: Audio generation failed - TTS service unavailable]`
    }
  }
}

async function generateSlidesFromApi(
  mediaId: number,
  abortSignal?: AbortSignal
): Promise<{
  serverId?: number
  content?: string
  presentationId?: string
  presentationVersion?: number
}> {
  try {
    // Use the Slides API to generate a real presentation
    const presentation = await tldwClient.generateSlidesFromMedia(mediaId, {
      signal: abortSignal
    })

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
      presentationVersion: presentation.version
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
): Promise<{ serverId?: number; content?: string }> {
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
      signal: abortSignal
    }
  )

  return {
    content: ragResponse?.generation || ragResponse?.answer || "Slides generation failed"
  }
}

async function generateDataTable(
  mediaIds: number[],
  workspaceTag?: string,
  abortSignal?: AbortSignal
): Promise<{ serverId?: number; content?: string; data?: Record<string, unknown> }> {
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
      signal: abortSignal
    }
  )

  const content =
    ragResponse?.generation || ragResponse?.answer || "Data table generation failed"
  const parsedTable = parseMarkdownTable(content)

  return {
    content,
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
          .map((entry) => {
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
          .filter((entry): entry is QuizQuestionDraft => entry !== null)
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
