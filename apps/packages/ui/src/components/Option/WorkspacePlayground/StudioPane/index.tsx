import React, { useState, useEffect } from "react"
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
  Table,
  Loader2,
  CheckCircle,
  XCircle,
  Eye,
  Download,
  RefreshCw,
  Trash2,
  ChevronDown,
  ChevronUp,
  Settings2,
  PanelRightClose
} from "lucide-react"
import { Button, Empty, Tooltip, Input, Modal, message, Slider, Select } from "antd"
import { useWorkspaceStore } from "@/store/workspace"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { generateQuiz } from "@/services/quizzes"
import { createFlashcard, createDeck, listDecks } from "@/services/flashcards"
import { fetchTldwVoiceCatalog, type TldwVoice } from "@/services/tldw/audio-voices"
import { inferTldwProviderFromModel } from "@/services/tts-provider"
import type { ArtifactType, GeneratedArtifact, AudioTtsProvider } from "@/types/workspace"
import { QuickNotesSection } from "./QuickNotesSection"

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
  data_table: Table
}

// Output type button configuration
const OUTPUT_BUTTONS: {
  type: ArtifactType
  label: string
  icon: React.ElementType
}[] = [
  { type: "audio_overview", label: "Audio Overview", icon: Headphones },
  { type: "summary", label: "Summary", icon: FileText },
  { type: "mindmap", label: "Mind Map", icon: GitBranch },
  { type: "report", label: "Report", icon: FileSpreadsheet },
  { type: "flashcards", label: "Flashcards", icon: Layers },
  { type: "quiz", label: "Quiz", icon: HelpCircle },
  { type: "timeline", label: "Timeline", icon: Calendar },
  { type: "slides", label: "Slides", icon: Presentation },
  { type: "data_table", label: "Data Table", icon: Table }
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

/**
 * StudioPane - Right pane for generating outputs
 */
export const StudioPane: React.FC<StudioPaneProps> = ({ onHide }) => {
  const { t } = useTranslation(["playground", "common"])
  const [messageApi, contextHolder] = message.useMessage()

  // Store state
  const selectedSourceIds = useWorkspaceStore((s) => s.selectedSourceIds)
  const getSelectedMediaIds = useWorkspaceStore((s) => s.getSelectedMediaIds)
  const generatedArtifacts = useWorkspaceStore((s) => s.generatedArtifacts)
  const isGeneratingOutput = useWorkspaceStore((s) => s.isGeneratingOutput)
  const generatingOutputType = useWorkspaceStore((s) => s.generatingOutputType)
  const workspaceTag = useWorkspaceStore((s) => s.workspaceTag)
  const audioSettings = useWorkspaceStore((s) => s.audioSettings)

  // Store actions
  const addArtifact = useWorkspaceStore((s) => s.addArtifact)
  const updateArtifactStatus = useWorkspaceStore((s) => s.updateArtifactStatus)
  const removeArtifact = useWorkspaceStore((s) => s.removeArtifact)
  const setIsGeneratingOutput = useWorkspaceStore((s) => s.setIsGeneratingOutput)
  const setAudioSettings = useWorkspaceStore((s) => s.setAudioSettings)

  // Local state for TTS settings panel
  const [showTtsSettings, setShowTtsSettings] = useState(false)
  const [tldwVoices, setTldwVoices] = useState<TldwVoice[]>([])
  const [loadingVoices, setLoadingVoices] = useState(false)

  // Local state for collapsible sections
  const [studioExpanded, setStudioExpanded] = useState(true)
  const [outputsExpanded, setOutputsExpanded] = useState(true)
  const [notesExpanded, setNotesExpanded] = useState(true)

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

  const hasSelectedSources = selectedSourceIds.length > 0

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

  const handleGenerateOutput = async (type: ArtifactType) => {
    if (!hasSelectedSources) return

    const mediaIds = getSelectedMediaIds()
    if (mediaIds.length === 0) return

    // Start generation
    setIsGeneratingOutput(true, type)

    // Create artifact placeholder
    const artifact = addArtifact({
      type,
      title: `${OUTPUT_BUTTONS.find((b) => b.type === type)?.label || type}`,
      status: "generating"
    })

    try {
      let result: {
        serverId?: number | string
        content?: string
        audioUrl?: string
        audioFormat?: string
        presentationId?: string
        presentationVersion?: number
      } = {}

      switch (type) {
        case "summary":
          result = await generateSummary(mediaIds, workspaceTag)
          break
        case "report":
          result = await generateReport(mediaIds, workspaceTag)
          break
        case "timeline":
          result = await generateTimeline(mediaIds, workspaceTag)
          break
        case "quiz":
          result = await generateQuizFromMedia(mediaIds[0], workspaceTag)
          break
        case "flashcards":
          result = await generateFlashcards(mediaIds[0], workspaceTag)
          break
        case "mindmap":
          result = await generateMindMap(mediaIds)
          break
        case "audio_overview":
          result = await generateAudioOverview(mediaIds, audioSettings)
          break
        case "slides":
          result = await generateSlidesFromApi(mediaIds[0])
          break
        case "data_table":
          result = await generateDataTable(mediaIds, workspaceTag)
          break
        default:
          throw new Error(`Unsupported output type: ${type}`)
      }

      // Update artifact with success
      updateArtifactStatus(artifact.id, "completed", {
        serverId: result.serverId,
        content: result.content,
        audioUrl: result.audioUrl,
        audioFormat: result.audioFormat,
        presentationId: result.presentationId,
        presentationVersion: result.presentationVersion
      })

      messageApi.success(
        t("playground:studio.generateSuccess", "{{type}} generated successfully", {
          type: OUTPUT_BUTTONS.find((b) => b.type === type)?.label || type
        })
      )
    } catch (error) {
      updateArtifactStatus(artifact.id, "failed", {
        errorMessage:
          error instanceof Error ? error.message : "Generation failed"
      })

      messageApi.error(
        t("playground:studio.generateError", "Failed to generate {{type}}", {
          type: OUTPUT_BUTTONS.find((b) => b.type === type)?.label || type
        })
      )
    } finally {
      setIsGeneratingOutput(false)
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
        width: 500
      })
    } else if (artifact.content) {
      Modal.info({
        title: artifact.title,
        content: (
          <div className="max-h-96 overflow-y-auto whitespace-pre-wrap">
            {artifact.content}
          </div>
        ),
        width: 600
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
        {studioExpanded && (
          <div className="px-4 pb-4">
        <div className="grid grid-cols-2 gap-3">
          {OUTPUT_BUTTONS.map(({ type, label, icon: Icon }) => {
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
                    : label
                }
              >
                <button
                  type="button"
                  disabled={isDisabled}
                  onClick={() => handleGenerateOutput(type)}
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
        {!hasSelectedSources && (
          <p className="mt-2 text-center text-xs text-text-muted">
            {t(
              "playground:studio.selectSourcesHint",
              "Select sources from the left pane to enable generation"
            )}
          </p>
        )}

        {/* TTS Settings Panel */}
        <div className="mt-4">
          <button
            type="button"
            onClick={() => setShowTtsSettings(!showTtsSettings)}
            className="flex w-full items-center justify-between rounded border border-border bg-surface2/50 px-3 py-2 text-xs text-text-muted hover:bg-surface2"
          >
            <span className="flex items-center gap-2">
              <Settings2 className="h-3.5 w-3.5" />
              {t("playground:studio.audioSettings", "Audio Settings")}
            </span>
            {showTtsSettings ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </button>

          {showTtsSettings && (
            <div className="mt-2 space-y-3 rounded border border-border bg-surface2/30 p-3">
              {/* Provider */}
              <div>
                <label className="mb-1 block text-xs font-medium text-text-muted">
                  {t("playground:studio.ttsProvider", "TTS Provider")}
                </label>
                <Select
                  size="small"
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
                    size="small"
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
                    size="small"
                    className="w-full"
                    value={audioSettings.voice}
                    onChange={(value) => setAudioSettings({ voice: value })}
                    options={getVoiceOptions()}
                    loading={loadingVoices}
                    showSearch
                    optionFilterProp="label"
                  />
                </div>
              )}

              {/* Speed */}
              <div>
                <label className="mb-1 block text-xs font-medium text-text-muted">
                  {t("playground:studio.ttsSpeed", "Speed")}: {audioSettings.speed.toFixed(1)}x
                </label>
                <Slider
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
                  size="small"
                  className="w-full"
                  value={audioSettings.format}
                  onChange={(value) => setAudioSettings({ format: value as any })}
                  options={AUDIO_FORMATS}
                />
              </div>
            </div>
          )}
        </div>
        </div>
        )}
      </div>

      {/* Generated Outputs Section - Collapsible */}
      <div className="border-b border-border">
        <button
          type="button"
          onClick={() => setOutputsExpanded(!outputsExpanded)}
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
        {outputsExpanded && (
          <div className="custom-scrollbar max-h-64 overflow-y-auto px-4 pb-4">
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
                            >
                              <Eye className="h-4 w-4" />
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
                          >
                            <Download className="h-4 w-4" />
                          </button>
                        </Tooltip>
                        <Tooltip title={t("common:regenerate", "Regenerate")}>
                          <button
                            type="button"
                            onClick={() => handleGenerateOutput(artifact.type)}
                            className="rounded p-1 text-text-muted hover:bg-surface hover:text-text"
                          >
                            <RefreshCw className="h-4 w-4" />
                          </button>
                        </Tooltip>
                        <Tooltip title={t("common:delete", "Delete")}>
                          <button
                            type="button"
                            onClick={() => removeArtifact(artifact.id)}
                            className="rounded p-1 text-text-muted hover:bg-error/10 hover:text-error"
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
        )}
      </div>

      {/* Quick Notes Section - Collapsible */}
      <div className="flex-1">
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

// ─────────────────────────────────────────────────────────────────────────────
// Output Generation Functions
// ─────────────────────────────────────────────────────────────────────────────

async function generateSummary(
  mediaIds: number[],
  workspaceTag?: string
): Promise<{ serverId?: number; content?: string }> {
  // Use RAG to get content and generate summary via chat
  const ragResponse = await tldwClient.ragSearch(
    "Provide a comprehensive summary of the key points and main ideas.",
    {
      media_ids: mediaIds,
      top_k: 20,
      enable_generation: true,
      enable_citations: true
    }
  )

  return {
    content: ragResponse?.generation || ragResponse?.answer || "Summary generation failed"
  }
}

async function generateReport(
  mediaIds: number[],
  workspaceTag?: string
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
      enable_citations: true
    }
  )

  return {
    content: ragResponse?.generation || ragResponse?.answer || "Report generation failed"
  }
}

async function generateTimeline(
  mediaIds: number[],
  workspaceTag?: string
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
      enable_citations: true
    }
  )

  return {
    content: ragResponse?.generation || ragResponse?.answer || "Timeline generation failed"
  }
}

async function generateQuizFromMedia(
  mediaId: number,
  workspaceTag?: string
): Promise<{ serverId?: number; content?: string }> {
  const response = await generateQuiz({
    media_id: mediaId,
    num_questions: 10,
    question_types: ["multiple_choice", "true_false"],
    difficulty: "mixed",
    workspace_tag: workspaceTag || undefined
  })

  return {
    serverId: response.quiz.id,
    content: formatQuizContent(response)
  }
}

async function generateFlashcards(
  mediaId: number,
  workspaceTag?: string
): Promise<{ serverId?: number; content?: string }> {
  // First, get content via RAG
  const ragResponse = await tldwClient.ragSearch(
    `Extract key concepts, definitions, and important facts that would make good flashcards.
Format each as:
Front: [Question or term]
Back: [Answer or definition]

Generate 10-15 flashcards.`,
    {
      media_ids: [mediaId],
      top_k: 20,
      enable_generation: true
    }
  )

  const content = ragResponse?.generation || ragResponse?.answer || ""

  // Parse and create flashcards
  const flashcards = parseFlashcards(content)

  // Ensure we have a deck
  const decks = await listDecks()
  let deckId: number | undefined

  if (decks.length === 0) {
    const newDeck = await createDeck({ name: "Workspace Flashcards" })
    deckId = newDeck.id
  } else {
    deckId = decks[0].id
  }

  // Create flashcards
  for (const card of flashcards) {
    try {
      await createFlashcard({
        deck_id: deckId,
        front: card.front,
        back: card.back,
        source_ref_type: "media",
        source_ref_id: String(mediaId)
      })
    } catch {
      // Continue with other cards
    }
  }

  return {
    content: `Created ${flashcards.length} flashcards\n\n${content}`
  }
}

async function generateMindMap(
  mediaIds: number[]
): Promise<{ serverId?: number; content?: string }> {
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
      enable_generation: true
    }
  )

  return {
    content: ragResponse?.generation || ragResponse?.answer || "Mind map generation failed"
  }
}

async function generateAudioOverview(
  mediaIds: number[],
  audioSettings: import("@/types/workspace").AudioGenerationSettings
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
      enable_generation: true
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
      speed: audioSettings.speed
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
    // If TTS fails, fall back to returning just the script
    console.error("TTS generation failed:", ttsError)
    return {
      content: `[Audio Script]\n\n${script}\n\n[Note: Audio generation failed - TTS service unavailable]`
    }
  }
}

async function generateSlidesFromApi(
  mediaId: number
): Promise<{
  serverId?: number
  content?: string
  presentationId?: string
  presentationVersion?: number
}> {
  try {
    // Use the Slides API to generate a real presentation
    const presentation = await tldwClient.generateSlidesFromMedia(mediaId)

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
    // Fallback to RAG-based generation if API fails
    console.error("Slides API failed, falling back to RAG:", error)
    return generateSlidesFallback([mediaId])
  }
}

async function generateSlidesFallback(
  mediaIds: number[]
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
      enable_generation: true
    }
  )

  return {
    content: ragResponse?.generation || ragResponse?.answer || "Slides generation failed"
  }
}

async function generateDataTable(
  mediaIds: number[],
  workspaceTag?: string
): Promise<{ serverId?: number; content?: string }> {
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
      enable_generation: true
    }
  )

  return {
    content: ragResponse?.generation || ragResponse?.answer || "Data table generation failed"
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

function formatQuizContent(response: { quiz: any; questions: any[] }): string {
  let content = `Quiz: ${response.quiz.name}\n`
  content += `${response.quiz.description || ""}\n\n`
  content += `Total Questions: ${response.questions.length}\n\n`

  response.questions.forEach((q, idx) => {
    content += `Q${idx + 1}: ${q.question_text}\n`
    if (q.options) {
      q.options.forEach((opt: string, optIdx: number) => {
        content += `  ${String.fromCharCode(65 + optIdx)}. ${opt}\n`
      })
    }
    content += `Answer: ${q.correct_answer}\n`
    if (q.explanation) {
      content += `Explanation: ${q.explanation}\n`
    }
    content += "\n"
  })

  return content
}

function parseFlashcards(
  content: string
): Array<{ front: string; back: string }> {
  const cards: Array<{ front: string; back: string }> = []
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
