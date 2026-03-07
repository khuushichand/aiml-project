import React, { useCallback, useEffect, useMemo, useState } from "react"
import { useStorage } from "@plasmohq/storage/hook"
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
import type { SttHistoryEntry } from "./HistoryPanel"
import {
  saveSttRecording,
  getSttRecording,
  deleteSttRecording
} from "@/db/dexie/stt-recordings"

const { Text, Title } = Typography

export const SttPlaygroundPage: React.FC = () => {
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
            message: "Model load failed",
            description: isTimeoutLikeError(e)
              ? "Model list took longer than 10 seconds. Check server health and retry."
              : "Unable to load transcription models. Retry or check server settings."
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
    if (sttSettings.timestampGranularities)
      opts.timestamp_granularities = sttSettings.timestampGranularities
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
          message: "Saved to Notes",
          description: "Transcription saved as a note."
        })
      } catch (e: any) {
        notification.error({
          message: "Error",
          description: e?.message || "Something went wrong"
        })
      }
    },
    [notification]
  )

  const handleRecompare = useCallback(
    async (entry: SttHistoryEntry) => {
      try {
        const blob = await getSttRecording(entry.recordingId)
        if (blob) {
          setCurrentBlob(blob)
          setCurrentDurationMs(entry.durationMs ?? 0)
        } else {
          notification.error({
            message: "Recording not found",
            description:
              "The audio recording was not found in local storage. It may have been deleted."
          })
        }
      } catch (e: any) {
        notification.error({
          message: "Error",
          description: e?.message || "Failed to load recording"
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
          message: "Copied",
          description: "Comparison results copied to clipboard as Markdown."
        })
      } catch {
        notification.error({
          message: "Copy failed",
          description: "Unable to copy to clipboard."
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
        message: "Deleted",
        description: "History entry removed."
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
      <Title level={3}>STT Playground</Title>
      <Text type="secondary">
        Record audio and compare transcription results across multiple models.
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
