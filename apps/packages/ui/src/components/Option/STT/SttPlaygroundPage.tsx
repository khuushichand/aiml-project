import React, { useCallback, useEffect, useMemo, useState } from "react"
import { useStorage } from "@plasmohq/storage/hook"
import { useTranslation } from "react-i18next"
import { Typography } from "antd"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { PageShell } from "@/components/Common/PageShell"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import { isTimeoutLikeError } from "@/utils/request-timeout"
import { RecordingStrip } from "./RecordingStrip"
import { InlineSettingsPanel } from "./InlineSettingsPanel"
import type { SttLocalSettings } from "./InlineSettingsPanel"
import { ComparisonPanel } from "./ComparisonPanel"
import { HistoryPanel } from "./HistoryPanel"
import type { SttHistoryEntry, SttHistoryResult } from "./HistoryPanel"
import type { ComparisonResult } from "@/hooks/useComparisonTranscribe"
import {
  saveSttRecording,
  getSttRecording,
  deleteSttRecording
} from "@/db/dexie/stt-recordings"

const { Text, Title } = Typography

export const SttPlaygroundPage: React.FC = () => {
  const { t } = useTranslation(["playground"])
  const notification = useAntdNotification()

  // ── Server models (fetched on mount) ──────────────────────────────
  const [serverModels, setServerModels] = useState<string[]>([])

  useEffect(() => {
    let cancelled = false
    const fetchModels = async () => {
      try {
        const res = await tldwClient.getTranscriptionModels({
          timeoutMs: 10_000
        })
        const all = Array.isArray(res?.all_models)
          ? (res.all_models as string[])
          : []
        if (!cancelled && all.length > 0) {
          const unique = Array.from(new Set(all)).sort()
          setServerModels(unique)
        }
      } catch (e) {
        if (!cancelled) {
          notification.error({
            message: t("playground:stt.modelsLoadError", "Model load failed"),
            description: isTimeoutLikeError(e)
              ? t("playground:stt.modelsTimeout", "Model list took longer than 10 seconds. Check server health and retry.")
              : t("playground:stt.modelsLoadErrorDesc", "Unable to load transcription models. Retry or check server settings.")
          })
        }
      }
    }
    fetchModels()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Current blob from RecordingStrip ──────────────────────────────
  const [currentBlob, setCurrentBlob] = useState<Blob | null>(null)
  const [currentDurationMs, setCurrentDurationMs] = useState<number>(0)

  const handleBlobReady = useCallback((blob: Blob, durationMs: number) => {
    setCurrentBlob(blob)
    setCurrentDurationMs(durationMs)
  }, [])

  // ── Settings ──────────────────────────────────────────────────────
  const [sttSettings, setSttSettings] = useState<SttLocalSettings | null>(null)
  const [showSettings, setShowSettings] = useState(false)

  const toggleSettings = useCallback(() => {
    setShowSettings((prev) => !prev)
  }, [])

  const sttOptions = useMemo(() => {
    if (!sttSettings) return {}
    const opts: Record<string, unknown> = {}
    if (sttSettings.language) opts.language = sttSettings.language
    if (sttSettings.task) opts.task = sttSettings.task
    if (sttSettings.responseFormat)
      opts.response_format = sttSettings.responseFormat
    if (typeof sttSettings.temperature === "number")
      opts.temperature = sttSettings.temperature
    if (sttSettings.prompt) opts.prompt = sttSettings.prompt
    if (sttSettings.useSegmentation) {
      opts.segment = true
      if (typeof sttSettings.segK === "number") opts.seg_K = sttSettings.segK
      if (typeof sttSettings.segMinSegmentSize === "number")
        opts.seg_min_segment_size = sttSettings.segMinSegmentSize
      if (typeof sttSettings.segLambdaBalance === "number")
        opts.seg_lambda_balance = sttSettings.segLambdaBalance
      if (typeof sttSettings.segUtteranceExpansionWidth === "number")
        opts.seg_utterance_expansion_width =
          sttSettings.segUtteranceExpansionWidth
      if (sttSettings.segEmbeddingsProvider)
        opts.seg_embeddings_provider = sttSettings.segEmbeddingsProvider
      if (sttSettings.segEmbeddingsModel)
        opts.seg_embeddings_model = sttSettings.segEmbeddingsModel
    }
    return opts
  }, [sttSettings])

  // ── History (persisted via Plasmo storage) ────────────────────────
  const [history, setHistory] = useStorage<SttHistoryEntry[]>(
    "sttComparisonHistory",
    []
  )

  // ── Callbacks ─────────────────────────────────────────────────────

  const handleComparisonComplete = useCallback(
    async (compResults: ComparisonResult[]) => {
      if (!currentBlob || compResults.length === 0) return
      try {
        const recordingId = await saveSttRecording({
          blob: currentBlob,
          durationMs: currentDurationMs,
          mimeType: currentBlob.type || "audio/webm"
        })
        const historyResults: SttHistoryResult[] = compResults
          .filter((r) => r.status === "done")
          .map((r) => ({
            model: r.model,
            text: r.text,
            latencyMs: r.latencyMs,
            wordCount: r.wordCount
          }))
        if (historyResults.length === 0) return
        const entry: SttHistoryEntry = {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          recordingId,
          createdAt: new Date().toISOString(),
          durationMs: currentDurationMs,
          results: historyResults
        }
        setHistory((prev) => [entry, ...(prev ?? [])].slice(0, 20))
      } catch (e) {
        console.error("Failed to save comparison to history", e)
      }
    },
    [currentBlob, currentDurationMs, setHistory]
  )

  const handleSaveToNotes = useCallback(
    async (text: string, model: string) => {
      const title = `STT Comparison: ${model} - ${new Date().toLocaleString()}`
      try {
        await tldwClient.createNote(text, {
          title,
          metadata: {
            origin: "stt-playground",
            stt_model: model
          }
        })
        notification.success({
          message: t("playground:stt.savedToNotes", "Saved to Notes"),
          description: t("playground:stt.savedToNotesDesc", "Transcription saved as a note.")
        })
      } catch (e: unknown) {
        notification.error({
          message: t("error", "Error"),
          description: e instanceof Error ? e.message : t("somethingWentWrong", "Something went wrong")
        })
      }
    },
    [notification]
  )

  const handleRecompare = useCallback(
    async (entry: SttHistoryEntry) => {
      try {
        const recording = await getSttRecording(entry.recordingId)
        if (recording) {
          setCurrentBlob(recording.blob)
          setCurrentDurationMs(recording.durationMs ?? entry.durationMs ?? 0)
        } else {
          notification.error({
            message: t("playground:stt.recordingNotFound", "Recording not found"),
            description: t("playground:stt.recordingNotFoundDesc",
              "The audio recording was not found in local storage. It may have been deleted.")
          })
        }
      } catch (e: unknown) {
        notification.error({
          message: t("error", "Error"),
          description: e instanceof Error ? e.message : t("playground:stt.loadFailed", "Failed to load recording")
        })
      }
    },
    [notification]
  )

  const handleExport = useCallback(
    async (entry: SttHistoryEntry) => {
      const lines = [
        `# STT Comparison - ${new Date(entry.createdAt).toLocaleString()}`,
        "",
        `Duration: ${entry.durationMs ? (entry.durationMs / 1000).toFixed(1) + "s" : "unknown"}`,
        ""
      ]
      if (entry.results) {
        for (const result of entry.results) {
          lines.push(`## ${result.model}`)
          lines.push("")
          lines.push(result.text || "(no text)")
          lines.push("")
        }
      }
      const markdown = lines.join("\n")
      try {
        await navigator.clipboard.writeText(markdown)
        notification.success({
          message: t("playground:stt.exported", "Copied"),
          description: t("playground:stt.exportedDesc", "Comparison results copied to clipboard as Markdown.")
        })
      } catch {
        notification.error({
          message: t("playground:stt.exportFailed", "Copy failed"),
          description: t("playground:stt.exportFailedDesc", "Unable to copy to clipboard.")
        })
      }
    },
    [notification]
  )

  const handleDeleteEntry = useCallback(
    async (id: string) => {
      const entry = (history ?? []).find((e) => e.id === id)
      if (entry) {
        try {
          await deleteSttRecording(entry.recordingId)
        } catch {
          // Dexie record may already be gone; proceed with removal
        }
      }
      setHistory((prev) => (prev ?? []).filter((e) => e.id !== id))
      notification.info({
        message: t("playground:stt.deleted", "Deleted"),
        description: t("playground:stt.deletedDesc", "History entry removed.")
      })
    },
    [history, setHistory, notification]
  )

  const handleClearAll = useCallback(async () => {
    const entries = history ?? []
    for (const entry of entries) {
      try {
        await deleteSttRecording(entry.recordingId)
      } catch {
        // best-effort cleanup
      }
    }
    setHistory([])
  }, [history, setHistory])

  // ── Keyboard shortcuts ────────────────────────────────────────────
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code !== "Space") return
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase()
      const isEditable = (e.target as HTMLElement)?.isContentEditable
      if (
        tag === "input" ||
        tag === "textarea" ||
        tag === "select" ||
        tag === "button" ||
        isEditable
      ) {
        return
      }
      e.preventDefault()
      window.dispatchEvent(new CustomEvent("stt-toggle-record"))
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [])

  // ── Render ────────────────────────────────────────────────────────
  return (
    <PageShell maxWidthClassName="max-w-5xl" className="py-6">
      <Title level={3}>
        {t("playground:stt.title", "STT Playground")}
      </Title>
      <Text type="secondary">
        {t("playground:stt.subtitle", "Record audio and compare transcription results across multiple models.")}
      </Text>

      <div className="mt-4 space-y-4">
        <RecordingStrip
          onBlobReady={handleBlobReady}
          onSettingsToggle={toggleSettings}
        />
        {showSettings && <InlineSettingsPanel onChange={setSttSettings} />}
        <ComparisonPanel
          blob={currentBlob}
          availableModels={serverModels}
          sttOptions={sttOptions}
          onSaveToNotes={handleSaveToNotes}
          onComparisonComplete={handleComparisonComplete}
        />
        <HistoryPanel
          entries={history ?? []}
          onRecompare={handleRecompare}
          onExport={handleExport}
          onDelete={handleDeleteEntry}
          onClearAll={handleClearAll}
        />
      </div>
    </PageShell>
  )
}

export default SttPlaygroundPage
