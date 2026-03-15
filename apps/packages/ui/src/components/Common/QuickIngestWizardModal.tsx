import React, { useCallback, useEffect, useMemo, useRef } from "react"
import { Modal, Button, Switch, Select, Radio, Collapse } from "antd"
import type { RadioChangeEvent } from "antd"
import { useTranslation } from "react-i18next"
import {
  ArrowLeft,
  ArrowRight,
  ChevronDown,
  Minimize2,
  XCircle,
  Info,
} from "lucide-react"
import { browser } from "wxt/browser"
import { IngestWizardProvider, useIngestWizard } from "./QuickIngest/IngestWizardContext"
import { IngestWizardStepper } from "./QuickIngest/IngestWizardStepper"
import { AddContentStep } from "./QuickIngest/AddContentStep"
import { PresetSelector } from "./QuickIngest/PresetSelector"
import { ReviewStep } from "./QuickIngest/ReviewStep"
import { ProcessingStep } from "./QuickIngest/ProcessingStep"
import { WizardResultsStep } from "./QuickIngest/WizardResultsStep"
import { FloatingProgressWidget } from "./QuickIngest/FloatingProgressWidget"
import {
  cancelQuickIngestSession,
  startQuickIngestSession,
  submitQuickIngestBatch,
} from "@/services/tldw/quick-ingest-batch"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import type {
  DetectedMediaType,
  ItemProgress,
  ItemProgressStatus,
  TypeDefaults,
  WizardQueueItem,
  WizardResultItem,
} from "./QuickIngest/types"

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

type QuickIngestWizardModalProps = {
  open: boolean
  onClose: () => void
  /** When true, automatically skip to processing on mount (compat with old modal). */
  autoProcessQueued?: boolean
}

// ---------------------------------------------------------------------------
// Configure Step (Step 2) - inline
// ---------------------------------------------------------------------------

const ConfigureStep: React.FC = () => {
  const { t } = useTranslation(["option"])
  const { state, setPreset, setCustomOptions, goNext, goBack } = useIngestWizard()
  const { queueItems, selectedPreset, presetConfig } = state

  const qi = useCallback(
    (key: string, defaultValue: string, options?: Record<string, unknown>) =>
      options
        ? t(`quickIngest.${key}`, { defaultValue, ...options })
        : t(`quickIngest.${key}`, defaultValue),
    [t],
  )

  // Detect which content types are present in the queue
  const detectedTypes = useMemo(() => {
    const types = new Set<DetectedMediaType>()
    for (const item of queueItems) {
      types.add(item.detectedType)
    }
    return types
  }, [queueItems])

  const hasAudio = detectedTypes.has("audio")
  const hasVideo = detectedTypes.has("video")
  const hasDocument =
    detectedTypes.has("document") ||
    detectedTypes.has("pdf") ||
    detectedTypes.has("ebook") ||
    detectedTypes.has("image")

  // Handlers for type-specific options
  const handleLanguageChange = useCallback(
    (value: string) => {
      setCustomOptions({
        typeDefaults: {
          ...presetConfig.typeDefaults,
          audio: { ...presetConfig.typeDefaults.audio, language: value },
        },
      })
    },
    [presetConfig.typeDefaults, setCustomOptions],
  )

  const handleDiarizeToggle = useCallback(
    (checked: boolean) => {
      setCustomOptions({
        typeDefaults: {
          ...presetConfig.typeDefaults,
          audio: { ...presetConfig.typeDefaults.audio, diarize: checked },
        },
      })
    },
    [presetConfig.typeDefaults, setCustomOptions],
  )

  const handleOcrToggle = useCallback(
    (checked: boolean) => {
      setCustomOptions({
        typeDefaults: {
          ...presetConfig.typeDefaults,
          document: { ...presetConfig.typeDefaults.document, ocr: checked },
        },
      })
    },
    [presetConfig.typeDefaults, setCustomOptions],
  )

  const handleCaptionsToggle = useCallback(
    (checked: boolean) => {
      setCustomOptions({
        typeDefaults: {
          ...presetConfig.typeDefaults,
          video: { ...presetConfig.typeDefaults.video, captions: checked },
        },
      })
    },
    [presetConfig.typeDefaults, setCustomOptions],
  )

  const handleStorageChange = useCallback(
    (e: RadioChangeEvent) => {
      setCustomOptions({ storeRemote: e.target.value })
    },
    [setCustomOptions],
  )

  return (
    <div className="py-3 space-y-5">
      {/* Preset cards */}
      <PresetSelector
        qi={qi}
        value={selectedPreset}
        onChange={setPreset}
        queueItems={queueItems}
      />

      {/* Type-specific options */}
      {(hasAudio || hasVideo || hasDocument) && (
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-text">
            {qi("wizard.configure.typeOptions", "Content-specific options")}
          </h4>

          {/* Audio options */}
          {hasAudio && (
            <div className="flex items-center gap-4 rounded-md border border-border px-3 py-2">
              <span className="text-sm text-text min-w-[80px]">
                {qi("wizard.configure.audio", "Audio")}
              </span>
              <div className="flex items-center gap-3 flex-1">
                <label className="flex items-center gap-1.5 text-xs text-text-muted">
                  {qi("wizard.configure.language", "Language")}
                  <Select
                    size="small"
                    value={presetConfig.typeDefaults.audio?.language ?? "auto"}
                    onChange={handleLanguageChange}
                    className="w-28"
                    options={[
                      { value: "auto", label: "Auto-detect" },
                      { value: "en", label: "English" },
                      { value: "es", label: "Spanish" },
                      { value: "fr", label: "French" },
                      { value: "de", label: "German" },
                      { value: "ja", label: "Japanese" },
                      { value: "zh", label: "Chinese" },
                      { value: "ko", label: "Korean" },
                      { value: "pt", label: "Portuguese" },
                      { value: "ru", label: "Russian" },
                    ]}
                  />
                </label>
                <label className="flex items-center gap-1.5 text-xs text-text-muted">
                  {qi("wizard.configure.diarization", "Diarization")}
                  <Switch
                    size="small"
                    checked={presetConfig.typeDefaults.audio?.diarize ?? false}
                    onChange={handleDiarizeToggle}
                  />
                </label>
              </div>
            </div>
          )}

          {/* Document options */}
          {hasDocument && (
            <div className="flex items-center gap-4 rounded-md border border-border px-3 py-2">
              <span className="text-sm text-text min-w-[80px]">
                {qi("wizard.configure.documents", "Documents")}
              </span>
              <div className="flex items-center gap-3 flex-1">
                <label className="flex items-center gap-1.5 text-xs text-text-muted">
                  {qi("wizard.configure.ocr", "OCR")}
                  <Switch
                    size="small"
                    checked={presetConfig.typeDefaults.document?.ocr ?? false}
                    onChange={handleOcrToggle}
                  />
                </label>
              </div>
            </div>
          )}

          {/* Video options */}
          {hasVideo && (
            <div className="flex items-center gap-4 rounded-md border border-border px-3 py-2">
              <span className="text-sm text-text min-w-[80px]">
                {qi("wizard.configure.video", "Video")}
              </span>
              <div className="flex items-center gap-3 flex-1">
                <label className="flex items-center gap-1.5 text-xs text-text-muted">
                  {qi("wizard.configure.captions", "Captions")}
                  <Switch
                    size="small"
                    checked={presetConfig.typeDefaults.video?.captions ?? false}
                    onChange={handleCaptionsToggle}
                  />
                </label>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Storage option */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-text">
          {qi("wizard.configure.storage", "Storage")}
        </h4>
        <Radio.Group
          value={presetConfig.storeRemote}
          onChange={handleStorageChange}
          className="flex gap-4"
        >
          <Radio value={true}>
            <span className="text-sm">{qi("wizard.configure.server", "Server")}</span>
          </Radio>
          <Radio value={false}>
            <span className="text-sm">{qi("wizard.configure.local", "Local only")}</span>
          </Radio>
        </Radio.Group>
      </div>

      {/* Advanced options placeholder */}
      <Collapse
        ghost
        expandIcon={({ isActive }) => (
          <ChevronDown
            className={`h-4 w-4 text-text-muted transition-transform ${
              isActive ? "rotate-180" : ""
            }`}
          />
        )}
        items={[
          {
            key: "advanced",
            label: (
              <span className="text-xs text-text-muted">
                {qi("wizard.configure.advanced", "Advanced options")}
              </span>
            ),
            children: (
              <div className="flex items-center gap-2 rounded-md bg-surface2 px-3 py-3 text-xs text-text-muted">
                <Info className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
                <span>
                  {qi(
                    "wizard.configure.advancedPlaceholder",
                    "Advanced options are available in the full ingest modal.",
                  )}
                </span>
              </div>
            ),
          },
        ]}
      />

      {/* Navigation buttons */}
      <div className="flex items-center justify-between pt-2">
        <Button onClick={goBack}>
          <ArrowLeft className="mr-1 h-4 w-4" />
          {qi("wizard.back", "Back")}
        </Button>
        <Button type="primary" onClick={goNext}>
          {qi("wizard.next", "Next")}
          <ArrowRight className="ml-1 h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

type QuickIngestEntryType = "auto" | "html" | "pdf" | "document" | "audio" | "video"

type QuickIngestRequestPayload = {
  entries: Array<{
    id: string
    url: string
    type: QuickIngestEntryType
    defaults?: TypeDefaults
  }>
  files: Array<{
    id: string
    name: string
    type?: string
    data: number[]
    defaults?: TypeDefaults
  }>
  storeRemote: boolean
  processOnly: boolean
  common: {
    perform_analysis: boolean
    perform_chunking: boolean
    overwrite_existing: boolean
  }
  advancedValues: Record<string, unknown>
  fileDefaults: TypeDefaults
  __quickIngestSessionId?: string
}

type QuickIngestRuntimeMessage = {
  type: string
  payload?: {
    sessionId?: string
    result?: Partial<WizardResultItem>
    results?: Array<Partial<WizardResultItem>>
    error?: string
    reason?: string
  }
}

const RESULT_SUCCESS_STATUS_TOKENS = [
  "ok",
  "success",
  "completed",
  "complete",
  "done",
  "ingested",
  "processed",
  "ready",
]

const RESULT_CANCELLED_STATUS_TOKENS = ["cancelled", "canceled"]

const mapDetectedTypeToEntryType = (
  detectedType: DetectedMediaType
): QuickIngestEntryType => {
  switch (detectedType) {
    case "audio":
    case "video":
    case "pdf":
    case "document":
      return detectedType
    case "web":
      return "html"
    default:
      return "auto"
  }
}

const buildDefaultsForQueueItem = (
  item: WizardQueueItem,
  typeDefaults: TypeDefaults
): TypeDefaults | undefined => {
  switch (item.detectedType) {
    case "audio":
      return typeDefaults.audio ? { audio: typeDefaults.audio } : undefined
    case "video":
      return {
        ...(typeDefaults.audio ? { audio: typeDefaults.audio } : {}),
        ...(typeDefaults.video ? { video: typeDefaults.video } : {}),
      }
    case "document":
    case "pdf":
    case "ebook":
    case "image":
      return typeDefaults.document ? { document: typeDefaults.document } : undefined
    default:
      return undefined
  }
}

const normalizeResultStatus = (status: unknown): "ok" | "error" => {
  const normalized = String(status || "").trim().toLowerCase()
  if (RESULT_SUCCESS_STATUS_TOKENS.includes(normalized)) return "ok"
  return "error"
}

const isCancelledError = (value: unknown) =>
  RESULT_CANCELLED_STATUS_TOKENS.some((token) =>
    String(value || "").trim().toLowerCase().includes(token)
  )

const normalizeWizardResult = (
  item: Partial<WizardResultItem> | null | undefined
): WizardResultItem | null => {
  if (!item?.id) return null
  const id = String(item.id).trim()
  if (!id) return null
  const status = normalizeResultStatus(item.status)
  const error = typeof item.error === "string" ? item.error : undefined
  return {
    id,
    status,
    outcome:
      status === "ok"
        ? item.outcome || "processed"
        : isCancelledError(error)
          ? "cancelled"
          : item.outcome || "failed",
    url: item.url,
    fileName: item.fileName,
    type: String(item.type || "item"),
    data: item.data,
    error,
    title: item.title,
    durationMs: item.durationMs,
    mediaId: item.mediaId,
  }
}

const mergeWizardResults = (
  existing: WizardResultItem[],
  incoming: WizardResultItem[]
): WizardResultItem[] => {
  const merged = new Map<string, WizardResultItem>()
  for (const item of existing) {
    merged.set(item.id, item)
  }
  for (const item of incoming) {
    const previous = merged.get(item.id)
    merged.set(item.id, previous ? { ...previous, ...item } : item)
  }
  return Array.from(merged.values())
}

const buildTerminalProgress = (
  previous: ItemProgress,
  result: WizardResultItem
): ItemProgress => {
  const cancelled = result.outcome === "cancelled" || isCancelledError(result.error)
  const nextStatus: ItemProgressStatus =
    result.status === "ok" ? "complete" : cancelled ? "cancelled" : "failed"
  return {
    ...previous,
    status: nextStatus,
    progressPercent: 100,
    currentStage:
      nextStatus === "complete"
        ? "Complete"
        : nextStatus === "cancelled"
          ? "Cancelled"
          : result.error || "Failed",
    estimatedRemaining: 0,
    error: nextStatus === "failed" ? result.error : undefined,
  }
}

const buildFailureResults = (
  items: WizardQueueItem[],
  message: string,
  outcome: "failed" | "cancelled"
): WizardResultItem[] =>
  items.map((item) => ({
    id: item.id,
    status: "error",
    outcome,
    url: item.url,
    fileName: item.fileName,
    type: mapDetectedTypeToEntryType(item.detectedType),
    error: message,
  }))

const buildQuickIngestPayload = async (
  items: WizardQueueItem[],
  options: QuickIngestRequestPayload["common"] & {
    storeRemote: boolean
    reviewBeforeStorage: boolean
    advancedValues?: Record<string, unknown>
    typeDefaults: TypeDefaults
  }
): Promise<QuickIngestRequestPayload> => {
  const validItems = items.filter((item) => item.validation.valid)
  const entries = validItems
    .filter((item): item is WizardQueueItem & { url: string } => Boolean(item.url))
    .map((item) => ({
      id: item.id,
      url: item.url,
      type: mapDetectedTypeToEntryType(item.detectedType),
      defaults: buildDefaultsForQueueItem(item, options.typeDefaults),
    }))

  const files = await Promise.all(
    validItems
      .filter((item): item is WizardQueueItem & { file: File } => Boolean(item.file))
      .map(async (item) => ({
        id: item.id,
        name: item.file.name,
        type: item.file.type || undefined,
        data: Array.from(new Uint8Array(await item.file.arrayBuffer())),
        defaults: buildDefaultsForQueueItem(item, options.typeDefaults),
      }))
  )

  return {
    entries,
    files,
    storeRemote: options.storeRemote,
    processOnly: options.reviewBeforeStorage || !options.storeRemote,
    common: {
      perform_analysis: options.perform_analysis,
      perform_chunking: options.perform_chunking,
      overwrite_existing: options.overwrite_existing,
    },
    advancedValues: options.advancedValues ?? {},
    fileDefaults: options.typeDefaults,
  }
}

// ---------------------------------------------------------------------------
// Inner modal content (must be inside IngestWizardProvider)
// ---------------------------------------------------------------------------

type WizardModalContentProps = {
  onClose: () => void
  autoProcessQueued?: boolean
}

const WizardModalContent: React.FC<WizardModalContentProps> = ({
  onClose,
  autoProcessQueued = false,
}) => {
  const { t } = useTranslation(["option"])
  const {
    state,
    minimize,
    cancelProcessing,
    skipToProcessing,
    updateItemProgress,
    updateProcessingState,
    setResults,
    goNext,
  } = useIngestWizard()
  const { currentStep, queueItems, processingState, presetConfig, results } = state
  const activeSessionIdRef = useRef<string | null>(null)
  const resultsRef = useRef(results)
  const hasStartedRunRef = useRef(false)
  const runStartedAtRef = useRef<number | null>(null)
  const cancelledSessionIdsRef = useRef<Set<string>>(new Set())
  const validQueueItems = useMemo(
    () => queueItems.filter((item) => item.validation.valid),
    [queueItems]
  )

  useEffect(() => {
    resultsRef.current = results
  }, [results])

  // Auto-process on mount if autoProcessQueued is set and there are queued items
  const autoProcessedRef = useRef(false)
  useEffect(() => {
    if (autoProcessQueued && !autoProcessedRef.current && queueItems.length > 0) {
      autoProcessedRef.current = true
      skipToProcessing()
    }
  }, [autoProcessQueued, queueItems.length, skipToProcessing])

  const qi = useCallback(
    (key: string, defaultValue: string, options?: Record<string, unknown>) =>
      options
        ? t(`quickIngest.${key}`, { defaultValue, ...options })
        : t(`quickIngest.${key}`, defaultValue),
    [t],
  )

  // Whether processing is actively running
  const isProcessingActive = processingState.status === "running"

  const syncElapsed = useCallback(() => {
    const startedAt = runStartedAtRef.current
    if (!startedAt) return
    updateProcessingState({
      elapsed: Math.max(0, Math.floor((Date.now() - startedAt) / 1000)),
    })
  }, [updateProcessingState])

  useEffect(() => {
    if (processingState.status !== "running") return
    syncElapsed()
    const timer = window.setInterval(syncElapsed, 1000)
    return () => window.clearInterval(timer)
  }, [processingState.status, syncElapsed])

  const applyResults = useCallback(
    (incoming: WizardResultItem[]) => {
      const next = mergeWizardResults(resultsRef.current, incoming)
      resultsRef.current = next
      setResults(next)
      const progressMap = new Map(
        processingState.perItemProgress.map((item) => [item.id, item])
      )
      for (const result of incoming) {
        const previous = progressMap.get(result.id)
        if (!previous) continue
        updateItemProgress(buildTerminalProgress(previous, result))
      }
      return next
    },
    [processingState.perItemProgress, setResults, updateItemProgress]
  )

  const finalizeRun = useCallback(
    (
      nextStatus: "complete" | "cancelled" | "error",
      incomingResults: WizardResultItem[]
    ) => {
      syncElapsed()
      applyResults(incomingResults)
      updateProcessingState({
        status: nextStatus,
        estimatedRemaining: 0,
      })
      hasStartedRunRef.current = false
      activeSessionIdRef.current = null
      goNext()
    },
    [applyResults, goNext, syncElapsed, updateProcessingState]
  )

  const finalizeFailure = useCallback(
    (message: string, outcome: "failed" | "cancelled") => {
      const fallbackResults = buildFailureResults(validQueueItems, message, outcome)
      finalizeRun(outcome === "cancelled" ? "cancelled" : "error", fallbackResults)
    },
    [finalizeRun, validQueueItems]
  )

  const markRunActive = useCallback(() => {
    runStartedAtRef.current = Date.now()
    for (const item of validQueueItems) {
      const initialStatus: ItemProgressStatus = item.file ? "uploading" : "processing"
      updateItemProgress({
        id: item.id,
        status: initialStatus,
        progressPercent: 10,
        currentStage: initialStatus === "uploading" ? "Uploading" : "Processing",
        estimatedRemaining: 0,
      })
    }
  }, [updateItemProgress, validQueueItems])

  const handleRuntimeMessage = useCallback(
    (message: QuickIngestRuntimeMessage) => {
      if (!message || typeof message.type !== "string") return
      const sessionId = String(message.payload?.sessionId || "").trim()
      if (!sessionId || sessionId !== String(activeSessionIdRef.current || "").trim()) {
        return
      }
      if (
        cancelledSessionIdsRef.current.has(sessionId) &&
        message.type !== "tldw:quick-ingest/progress"
      ) {
        return
      }

      if (message.type === "tldw:quick-ingest/progress") {
        const result = normalizeWizardResult(message.payload?.result)
        if (result) {
          applyResults([result])
        }
        return
      }

      if (message.type === "tldw:quick-ingest/completed") {
        const normalizedResults = (message.payload?.results || [])
          .map((item) => normalizeWizardResult(item))
          .filter((item): item is WizardResultItem => Boolean(item))
        if (normalizedResults.length === 0) {
          finalizeFailure("Ingest request finished without item results.", "failed")
          return
        }
        finalizeRun("complete", normalizedResults)
        return
      }

      if (message.type === "tldw:quick-ingest/failed") {
        finalizeFailure(
          String(message.payload?.error || "Quick ingest failed."),
          "failed"
        )
        return
      }

      if (message.type === "tldw:quick-ingest/cancelled") {
        finalizeFailure(
          String(message.payload?.reason || "Cancelled by user."),
          "cancelled"
        )
      }
    },
    [applyResults, finalizeFailure, finalizeRun]
  )

  useEffect(() => {
    const listener = (message: QuickIngestRuntimeMessage) => {
      handleRuntimeMessage(message)
    }
    try {
      if (browser?.runtime?.onMessage?.addListener) {
        browser.runtime.onMessage.addListener(listener)
      }
    } catch {
      return
    }

    return () => {
      try {
        if (browser?.runtime?.onMessage?.removeListener) {
          browser.runtime.onMessage.removeListener(listener)
        }
      } catch {
        // Ignore cleanup failures in non-extension runtimes.
      }
    }
  }, [handleRuntimeMessage])

  const startRun = useCallback(async () => {
    if (hasStartedRunRef.current || validQueueItems.length === 0) return
    hasStartedRunRef.current = true
    markRunActive()

    try {
      try {
        await tldwClient.initialize()
      } catch {
        // Best effort; background proxy handles auth for direct runtimes.
      }

      const requestPayload = await buildQuickIngestPayload(validQueueItems, {
        ...presetConfig.common,
        storeRemote: presetConfig.storeRemote,
        reviewBeforeStorage: presetConfig.reviewBeforeStorage,
        advancedValues: presetConfig.advancedValues,
        typeDefaults: presetConfig.typeDefaults,
      })

      const startAck = await startQuickIngestSession(requestPayload)
      if (!startAck?.ok || !startAck?.sessionId) {
        finalizeFailure(
          startAck?.error ||
            "Quick ingest failed to start. Check tldw server settings and try again.",
          "failed"
        )
        return
      }

      const sessionId = String(startAck.sessionId).trim()
      activeSessionIdRef.current = sessionId
      cancelledSessionIdsRef.current.delete(sessionId)

      if (!sessionId.startsWith("qi-direct-")) {
        return
      }

      const response = await submitQuickIngestBatch({
        ...requestPayload,
        __quickIngestSessionId: sessionId,
      })

      if (
        cancelledSessionIdsRef.current.has(sessionId) ||
        sessionId !== String(activeSessionIdRef.current || "").trim()
      ) {
        return
      }

      if (!response?.ok) {
        finalizeFailure(
          response?.error ||
            "Quick ingest failed. Check tldw server settings and try again.",
          "failed"
        )
        return
      }

      const normalizedResults = (response.results || [])
        .map((item) => normalizeWizardResult(item))
        .filter((item): item is WizardResultItem => Boolean(item))

      if (normalizedResults.length === 0) {
        finalizeFailure("Ingest request finished without item results.", "failed")
        return
      }

      finalizeRun("complete", normalizedResults)
    } catch (error) {
      finalizeFailure(
        error instanceof Error ? error.message : "Quick ingest failed.",
        "failed"
      )
    }
  }, [
    finalizeFailure,
    finalizeRun,
    markRunActive,
    presetConfig.advancedValues,
    presetConfig.common,
    presetConfig.reviewBeforeStorage,
    presetConfig.storeRemote,
    presetConfig.typeDefaults,
    validQueueItems,
  ])

  useEffect(() => {
    if (currentStep !== 4 || processingState.status !== "running") return
    void startRun()
  }, [currentStep, processingState.status, startRun])

  useEffect(() => {
    if (processingState.status !== "cancelled") return
    const sessionId = String(activeSessionIdRef.current || "").trim()
    if (!sessionId || cancelledSessionIdsRef.current.has(sessionId)) return
    cancelledSessionIdsRef.current.add(sessionId)
    void cancelQuickIngestSession({
      sessionId,
      reason: "user_cancelled",
    }).catch(() => {
      // best effort cancellation
    })
    finalizeFailure("Cancelled by user.", "cancelled")
  }, [finalizeFailure, processingState.status])

  // Modal title with item count
  const modalTitle = useMemo(() => {
    const base = qi("wizard.title", "Quick Ingest")
    if (queueItems.length > 0 && currentStep <= 3) {
      return `${base} (${queueItems.length})`
    }
    return base
  }, [qi, queueItems.length, currentStep])

  // Close handler with confirmation when processing
  const handleCloseAttempt = useCallback(() => {
    if (isProcessingActive) {
      Modal.confirm({
        title: qi(
          "wizard.closeConfirm.title",
          "Processing is in progress",
        ),
        content: qi(
          "wizard.closeConfirm.content",
          "Would you like to minimize to background or cancel all items?",
        ),
        okText: qi("wizard.closeConfirm.minimize", "Minimize to Background"),
        okButtonProps: { type: "primary" },
        cancelText: qi("wizard.closeConfirm.stay", "Stay"),
        footer: (_, { OkBtn, CancelBtn }) => (
          <div className="flex items-center justify-end gap-2">
            <CancelBtn />
            <Button
              danger
              onClick={() => {
                Modal.destroyAll()
                cancelProcessing()
                onClose()
              }}
            >
              <XCircle className="mr-1 h-4 w-4" />
              {qi("wizard.closeConfirm.cancelAll", "Cancel All")}
            </Button>
            <OkBtn />
          </div>
        ),
        onOk: () => {
          minimize()
          onClose()
        },
        icon: null,
        maskClosable: true,
      })
    } else {
      onClose()
    }
  }, [isProcessingActive, qi, minimize, cancelProcessing, onClose])

  // Quick-process callback for AddContentStep (skip to processing with defaults)
  const handleQuickProcess = useCallback(() => {
    skipToProcessing()
  }, [skipToProcessing])

  // Render the current step
  const stepContent = useMemo(() => {
    switch (currentStep) {
      case 1:
        return <AddContentStep onQuickProcess={handleQuickProcess} />
      case 2:
        return <ConfigureStep />
      case 3:
        return <ReviewStep />
      case 4:
        return <ProcessingStep />
      case 5:
        return <WizardResultsStep onClose={onClose} />
      default:
        return null
    }
  }, [currentStep, handleQuickProcess, onClose])

  return (
    <>
      <Modal
        open={!state.isMinimized}
        onCancel={handleCloseAttempt}
        title={modalTitle}
        footer={null}
        width={800}
        destroyOnHidden
        className="quick-ingest-modal quick-ingest-wizard-modal"
        styles={{
          body: { padding: "0 16px 16px" },
        }}
      >
        {/* Stepper navigation */}
        <IngestWizardStepper />

        {/* Step content */}
        <div className="min-h-[300px]">{stepContent}</div>
      </Modal>

      {/* Floating progress widget (renders via portal when minimized) */}
      <FloatingProgressWidget />
    </>
  )
}

// ---------------------------------------------------------------------------
// Exported modal component
// ---------------------------------------------------------------------------

export const QuickIngestWizardModal: React.FC<QuickIngestWizardModalProps> = ({
  open,
  onClose,
  autoProcessQueued = false,
}) => {
  if (!open) return null

  return (
    <IngestWizardProvider>
      <WizardModalContent onClose={onClose} autoProcessQueued={autoProcessQueued} />
    </IngestWizardProvider>
  )
}

export default QuickIngestWizardModal
