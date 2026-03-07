import React from "react"
import { useTranslation } from "react-i18next"
import { Button, Dropdown } from "antd"
import type { MenuProps } from "antd"
import { Play, Square, Download, Settings } from "lucide-react"
import { cn } from "@/libs/utils"

export type StreamStatus = "idle" | "connecting" | "streaming" | "complete" | "error"
export type BadgeType = "none" | "gray" | "amber" | "red"

export interface TtsStickyActionBarProps {
  onPlay: () => void
  onStop: () => void
  onDownloadSegment: () => void
  onDownloadAll: () => void
  onToggleInspector: () => void
  isPlayDisabled: boolean
  isStopDisabled: boolean
  isDownloadDisabled: boolean
  playDisabledReason: string | null
  stopDisabledReason: string | null
  downloadDisabledReason: string | null
  streamStatus: StreamStatus
  inspectorOpen: boolean
  inspectorBadge: BadgeType
  segmentCount: number
  provider: string
}

const STATUS_DOT_COLORS: Record<StreamStatus, string> = {
  idle: "bg-gray-400",
  connecting: "bg-amber-400",
  streaming: "bg-green-500",
  complete: "bg-blue-500",
  error: "bg-red-500",
}

const STATUS_LABELS: Record<StreamStatus, string> = {
  idle: "Idle",
  connecting: "Connecting...",
  streaming: "Streaming",
  complete: "Complete",
  error: "Error",
}

const BADGE_DOT_COLORS: Record<BadgeType, string> = {
  none: "",
  gray: "bg-gray-400",
  amber: "bg-amber-400",
  red: "bg-red-500",
}

export function TtsStickyActionBar({
  onPlay,
  onStop,
  onDownloadSegment,
  onDownloadAll,
  isPlayDisabled,
  isStopDisabled,
  isDownloadDisabled,
  playDisabledReason,
  stopDisabledReason,
  downloadDisabledReason,
  streamStatus,
  inspectorOpen,
  inspectorBadge,
  segmentCount,
  provider,
  onToggleInspector,
}: TtsStickyActionBarProps) {
  const { t } = useTranslation("playground")

  const downloadMenuItems: MenuProps["items"] = [
    {
      key: "segment",
      label: t("tts.downloadSegment", "Download current segment"),
      disabled: segmentCount === 0 || isDownloadDisabled,
      onClick: () => onDownloadSegment(),
    },
    {
      key: "all",
      label: t("tts.downloadAll", "Download all segments"),
      disabled: segmentCount <= 1 || isDownloadDisabled,
      onClick: () => onDownloadAll(),
    },
  ]

  const showDisabledReason = isPlayDisabled && playDisabledReason

  return (
    <div
      role="toolbar"
      aria-label={t("tts.playbackControls", "Playback controls")}
      className="sticky bottom-0 z-20 border-t border-border bg-surface/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-surface/85"
    >
      <div className="flex items-center gap-2">
        {/* Play button */}
        <Button
          type="primary"
          icon={<Play className="h-4 w-4" />}
          disabled={isPlayDisabled}
          onClick={onPlay}
          title={playDisabledReason ?? "Play (Ctrl+Enter)"}
          aria-label={t("tts.play", "Play")}
        >
          {t("tts.play", "Play")}
        </Button>

        {/* Stop button */}
        <Button
          icon={<Square className="h-4 w-4" />}
          disabled={isStopDisabled}
          onClick={onStop}
          title={stopDisabledReason ?? "Stop (Escape)"}
          aria-label={t("tts.stop", "Stop")}
        >
          {t("tts.stop", "Stop")}
        </Button>

        {/* Download dropdown */}
        <Dropdown menu={{ items: downloadMenuItems }} trigger={["click"]}>
          <Button
            icon={<Download className="h-4 w-4" />}
            disabled={isDownloadDisabled}
            title={downloadDisabledReason ?? undefined}
            aria-label={t("tts.download", "Download")}
          >
            {t("tts.download", "Download")}
          </Button>
        </Dropdown>

        {/* Flex spacer */}
        <div className="flex-1" />

        {/* Status indicator */}
        <div className="flex items-center gap-2">
          <span
            className={cn("h-2 w-2 rounded-full", STATUS_DOT_COLORS[streamStatus])}
            aria-hidden="true"
          />
          <span className="text-sm text-text-muted" aria-live="polite">
            {t(`tts.status.${streamStatus}`, STATUS_LABELS[streamStatus])}
          </span>
        </div>

        {/* Gear / inspector toggle */}
        <div className="relative">
          <Button
            icon={<Settings className="h-4 w-4" />}
            onClick={onToggleInspector}
            title="Configuration (Ctrl+.)"
            aria-label={t("tts.toggleConfig", "Toggle configuration panel")}
            aria-expanded={inspectorOpen}
          />
          {/* Badge dot */}
          {!inspectorOpen && inspectorBadge !== "none" && (
            <span
              className={cn(
                "absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-surface",
                BADGE_DOT_COLORS[inspectorBadge]
              )}
              aria-hidden="true"
            />
          )}
        </div>
      </div>

      {/* Disabled reason text */}
      {showDisabledReason && (
        <p className="mt-1 text-xs text-text-muted">{playDisabledReason}</p>
      )}
    </div>
  )
}

export default TtsStickyActionBar
