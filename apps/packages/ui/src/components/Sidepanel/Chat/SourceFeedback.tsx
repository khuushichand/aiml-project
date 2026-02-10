import React from "react"
import { Tooltip } from "antd"
import { ThumbsDown, ThumbsUp } from "lucide-react"
import { useTranslation } from "react-i18next"
import { MessageSource } from "@/components/Common/Playground/MessageSource"
import type { FeedbackThumb } from "@/store/feedback"

type Props = {
  source: any
  sourceKey: string
  sourceIndex?: number
  selected?: FeedbackThumb
  disabled?: boolean
  onRate?: (sourceKey: string, source: any, thumb: FeedbackThumb) => void
  onSourceClick?: (source: any) => void
  onTrackClick?: (source: any, index?: number) => void
  onTrackCitation?: (source: any, index?: number) => void
  onTrackDwell?: (source: any, dwellMs: number, index?: number) => void
}

const buttonBase =
  "inline-flex h-5 w-5 items-center justify-center rounded-full border text-[10px] transition-colors"

export const SourceFeedback = ({
  source,
  sourceKey,
  sourceIndex,
  selected = null,
  disabled = false,
  onRate,
  onSourceClick,
  onTrackClick,
  onTrackCitation,
  onTrackDwell
}: Props) => {
  const { t } = useTranslation("playground")

  const handleSourceClick = React.useCallback(
    (payload: any) => {
      onTrackClick?.(payload, sourceIndex)
      onSourceClick?.(payload)
    },
    [onSourceClick, onTrackClick, sourceIndex]
  )

  const handleSourceNavigate = React.useCallback(
    (payload: any) => {
      onTrackClick?.(payload, sourceIndex)
      onTrackCitation?.(payload, sourceIndex)
    },
    [onTrackCitation, onTrackClick, sourceIndex]
  )

  const handleSourceDwell = React.useCallback(
    (payload: any, dwellMs: number) => {
      onTrackDwell?.(payload, dwellMs, sourceIndex)
    },
    [onTrackDwell, sourceIndex]
  )

  const isDisabled = disabled

  return (
    <div className="flex items-center gap-2">
      <MessageSource
        source={source}
        onSourceClick={handleSourceClick}
        onSourceNavigate={handleSourceNavigate}
        onSourceDwell={handleSourceDwell}
      />
      <div className="flex items-center gap-1">
        <Tooltip title={t("feedback.sourceHelpful", "Helpful source")}>
          <button
            type="button"
            aria-label={t("feedback.sourceHelpful", "Helpful source")}
            aria-pressed={selected === "up"}
            disabled={isDisabled}
            onClick={() => onRate?.(sourceKey, source, "up")}
            title={t("feedback.sourceHelpful", "Helpful source")}
            className={`${buttonBase} ${
              selected === "up"
                ? "border-success/30 bg-success/10 text-success"
                : "border-border text-text-subtle hover:bg-surface2"
            } ${isDisabled ? "cursor-not-allowed opacity-50" : ""}`}>
            <ThumbsUp className="h-3 w-3" />
          </button>
        </Tooltip>
        <Tooltip title={t("feedback.sourceUnhelpful", "Unhelpful source")}>
          <button
            type="button"
            aria-label={t("feedback.sourceUnhelpful", "Unhelpful source")}
            aria-pressed={selected === "down"}
            disabled={isDisabled}
            onClick={() => onRate?.(sourceKey, source, "down")}
            title={t("feedback.sourceUnhelpful", "Unhelpful source")}
            className={`${buttonBase} ${
              selected === "down"
                ? "border-danger/30 bg-danger/10 text-danger"
                : "border-border text-text-subtle hover:bg-surface2"
            } ${isDisabled ? "cursor-not-allowed opacity-50" : ""}`}>
            <ThumbsDown className="h-3 w-3" />
          </button>
        </Tooltip>
      </div>
    </div>
  )
}
