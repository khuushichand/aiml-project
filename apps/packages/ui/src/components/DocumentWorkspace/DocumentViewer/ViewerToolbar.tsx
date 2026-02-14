import React from "react"
import { useTranslation } from "react-i18next"
import { Input, Select, Tooltip, Progress } from "antd"
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize,
  LayoutGrid,
  FileText,
  List
} from "lucide-react"
import type { ViewMode, DocumentType, EpubScrollMode } from "../types"
import {
  DEFAULT_ZOOM_LEVEL,
  MIN_ZOOM_LEVEL,
  MAX_ZOOM_LEVEL,
  ZOOM_STEP
} from "../types"
import { EpubSettingsPanel } from "./EpubViewer/EpubSettingsPanel"
import { TTSPanel } from "./TTSPanel"

interface ViewerToolbarProps {
  currentPage: number
  totalPages: number
  zoomLevel: number
  viewMode: ViewMode
  documentType?: DocumentType | null
  /** For EPUB: percentage complete (0-100) */
  percentage?: number
  onPageChange: (page: number) => void
  onZoomChange: (zoom: number) => void
  onViewModeChange: (mode: ViewMode) => void
  onPreviousPage: () => void
  onNextPage: () => void
}

const ZOOM_PRESETS = [25, 50, 75, 100, 125, 150, 200, 300, 400]
const TOOLBAR_ICON_BUTTON_CLASS =
  "rounded p-1.5 hover:bg-hover disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-bg"

export const ViewerToolbar: React.FC<ViewerToolbarProps> = ({
  currentPage,
  totalPages,
  zoomLevel,
  viewMode,
  documentType,
  percentage = 0,
  onPageChange,
  onZoomChange,
  onViewModeChange,
  onPreviousPage,
  onNextPage
}) => {
  const { t } = useTranslation(["option", "common"])

  const isEpub = documentType === "epub"

  const handlePageInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value, 10)
    if (!isNaN(value) && value >= 1 && value <= totalPages) {
      onPageChange(value)
    }
  }

  const handlePageInputBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value, 10)
    if (isNaN(value) || value < 1) {
      onPageChange(1)
    } else if (value > totalPages) {
      onPageChange(totalPages)
    }
  }

  const handleZoomIn = () => {
    const newZoom = Math.min(zoomLevel + ZOOM_STEP, MAX_ZOOM_LEVEL)
    onZoomChange(newZoom)
  }

  const handleZoomOut = () => {
    const newZoom = Math.max(zoomLevel - ZOOM_STEP, MIN_ZOOM_LEVEL)
    onZoomChange(newZoom)
  }

  const handleFitWidth = () => {
    // Fit width will be calculated based on container width
    // For now, reset to 100%
    onZoomChange(DEFAULT_ZOOM_LEVEL)
  }

  const viewModeOptions = [
    {
      value: "single" as ViewMode,
      label: (
        <span className="flex items-center gap-1.5">
          <FileText className="h-4 w-4" />
          {t("option:documentWorkspace.singlePage", "Single")}
        </span>
      )
    },
    {
      value: "continuous" as ViewMode,
      label: (
        <span className="flex items-center gap-1.5">
          <List className="h-4 w-4" />
          {t("option:documentWorkspace.continuous", "Continuous")}
        </span>
      )
    },
    {
      value: "thumbnails" as ViewMode,
      label: (
        <span className="flex items-center gap-1.5">
          <LayoutGrid className="h-4 w-4" />
          {t("option:documentWorkspace.thumbnails", "Thumbnails")}
        </span>
      )
    }
  ]

  return (
    <div className="flex h-10 shrink-0 items-center justify-between border-b border-border bg-surface px-2">
      {/* View mode - only for PDF */}
      {!isEpub && (
        <div className="flex items-center">
          <Select
            value={viewMode}
            onChange={onViewModeChange}
            size="small"
            className="w-32"
            options={viewModeOptions}
          />
        </div>
      )}

      {/* Zoom controls - only for PDF */}
      {!isEpub && (
        <div className="flex items-center gap-1">
          <Tooltip title={t("option:documentWorkspace.zoomOut", "Zoom out")}>
            <button
              onClick={handleZoomOut}
              disabled={zoomLevel <= MIN_ZOOM_LEVEL}
              className={TOOLBAR_ICON_BUTTON_CLASS}
              aria-label={t("option:documentWorkspace.zoomOut", "Zoom out")}
            >
              <ZoomOut className="h-4 w-4" />
            </button>
          </Tooltip>

          <Select
            value={zoomLevel}
            onChange={onZoomChange}
            size="small"
            className="w-20"
            options={ZOOM_PRESETS.map((z) => ({
              value: z,
              label: `${z}%`
            }))}
            showSearch={false}
          />

          <Tooltip title={t("option:documentWorkspace.zoomIn", "Zoom in")}>
            <button
              onClick={handleZoomIn}
              disabled={zoomLevel >= MAX_ZOOM_LEVEL}
              className={TOOLBAR_ICON_BUTTON_CLASS}
              aria-label={t("option:documentWorkspace.zoomIn", "Zoom in")}
            >
              <ZoomIn className="h-4 w-4" />
            </button>
          </Tooltip>

          <Tooltip title={t("option:documentWorkspace.fitWidth", "Fit width")}>
            <button
              onClick={handleFitWidth}
              className={TOOLBAR_ICON_BUTTON_CLASS}
              aria-label={t("option:documentWorkspace.fitWidth", "Fit width")}
            >
              <Maximize className="h-4 w-4" />
            </button>
          </Tooltip>
        </div>
      )}

      {/* TTS and EPUB settings */}
      <div className="flex items-center gap-1">
        <TTSPanel />
        {isEpub && <EpubSettingsPanel />}
      </div>

      {/* Navigation section */}
      <div className="flex items-center gap-1">
        <Tooltip title={t("option:documentWorkspace.previousPage", "Previous")}>
          <button
            onClick={onPreviousPage}
            disabled={currentPage <= 1}
            className={TOOLBAR_ICON_BUTTON_CLASS}
            aria-label={t("option:documentWorkspace.previousPage", "Previous")}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        </Tooltip>

        {isEpub ? (
          // EPUB: Show percentage progress
          <div className="flex items-center gap-2 min-w-[120px]">
            <Progress
              percent={Math.round(percentage)}
              size="small"
              showInfo={false}
              className="w-16"
            />
            <span className="text-sm text-muted tabular-nums">
              {Math.round(percentage)}%
            </span>
          </div>
        ) : (
          // PDF: Show page numbers
          <div className="flex items-center gap-1 text-sm">
            <Input
              type="number"
              min={1}
              max={totalPages}
              value={currentPage}
              onChange={handlePageInputChange}
              onBlur={handlePageInputBlur}
              className="w-14 text-center"
              size="small"
            />
            <span className="text-muted">
              / {totalPages || "-"}
            </span>
          </div>
        )}

        <Tooltip title={t("option:documentWorkspace.nextPage", "Next")}>
          <button
            onClick={onNextPage}
            disabled={currentPage >= totalPages}
            className={TOOLBAR_ICON_BUTTON_CLASS}
            aria-label={t("option:documentWorkspace.nextPage", "Next")}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </Tooltip>
      </div>
    </div>
  )
}

export default ViewerToolbar
