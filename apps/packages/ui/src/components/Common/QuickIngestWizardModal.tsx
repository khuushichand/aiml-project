import React, { useCallback, useMemo } from "react"
import { Modal, Button, Switch, Select, Radio, Collapse } from "antd"
import { useTranslation } from "react-i18next"
import {
  ArrowLeft,
  ArrowRight,
  ChevronDown,
  Minimize2,
  XCircle,
  Info,
} from "lucide-react"
import { IngestWizardProvider, useIngestWizard } from "./QuickIngest/IngestWizardContext"
import { IngestWizardStepper } from "./QuickIngest/IngestWizardStepper"
import { AddContentStep } from "./QuickIngest/AddContentStep"
import { PresetSelector } from "./QuickIngest/PresetSelector"
import { ReviewStep } from "./QuickIngest/ReviewStep"
import { ProcessingStep } from "./QuickIngest/ProcessingStep"
import { WizardResultsStep } from "./QuickIngest/WizardResultsStep"
import { FloatingProgressWidget } from "./QuickIngest/FloatingProgressWidget"
import type { DetectedMediaType, WizardStep } from "./QuickIngest/types"

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

type QuickIngestWizardModalProps = {
  open: boolean
  onClose: () => void
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
    (e: { target: { value: boolean } }) => {
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

// ---------------------------------------------------------------------------
// Inner modal content (must be inside IngestWizardProvider)
// ---------------------------------------------------------------------------

const WizardModalContent: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const { t } = useTranslation(["option"])
  const { state, minimize, cancelProcessing, skipToProcessing } = useIngestWizard()
  const { currentStep, queueItems, processingState } = state

  const qi = useCallback(
    (key: string, defaultValue: string, options?: Record<string, unknown>) =>
      options
        ? t(`quickIngest.${key}`, { defaultValue, ...options })
        : t(`quickIngest.${key}`, defaultValue),
    [t],
  )

  // Whether processing is actively running
  const isProcessingActive = processingState.status === "running"

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
        className="quick-ingest-wizard-modal"
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
}) => {
  if (!open) return null

  return (
    <IngestWizardProvider>
      <WizardModalContent onClose={onClose} />
    </IngestWizardProvider>
  )
}

export default QuickIngestWizardModal
