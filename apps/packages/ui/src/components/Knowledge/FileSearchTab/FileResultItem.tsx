import React from "react"
import { Button, Tooltip } from "antd"
import { Check, Eye, ExternalLink, Paperclip, Pin } from "lucide-react"
import { useTranslation } from "react-i18next"
import {
  getResultTitle,
  getResultText,
  getResultType,
  getResultDate,
  getResultScore
} from "@/components/Knowledge/hooks"
import type { RagResult } from "@/components/Knowledge/hooks"
import { highlightText } from "@/utils/text-highlight"

type FileResultItemProps = {
  result: RagResult
  query?: string
  onAttach: (result: RagResult) => void
  onPreview: (result: RagResult) => void
  onOpen: (result: RagResult) => void
  onPin: (result: RagResult) => void
  isAttached?: boolean
  isPinned?: boolean
}

const formatDate = (value?: string | number) => {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric"
  }).format(date)
}

const formatScore = (score?: number) =>
  typeof score === "number" && Number.isFinite(score)
    ? score.toFixed(2)
    : null

/**
 * File search result with Attach as primary action.
 * Shows "Attached" badge when the item has been inserted this session.
 */
export const FileResultItem: React.FC<FileResultItemProps> = React.memo(
  ({
    result,
    query,
    onAttach,
    onPreview,
    onOpen,
    onPin,
    isAttached = false,
    isPinned = false
  }) => {
    const { t } = useTranslation(["sidepanel"])

    const title = getResultTitle(result)
    const text = getResultText(result)
    const type = getResultType(result)
    const date = formatDate(getResultDate(result))
    const score = formatScore(getResultScore(result))

    const snippet = text.slice(0, 300) + (text.length > 300 ? "..." : "")

    return (
      <div
        className={`rounded-lg border bg-surface p-3 transition-colors ${
          isAttached
            ? "border-accent/40 bg-accent/5"
            : "border-border hover:border-accent/50"
        }`}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-2 mb-1">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <h4 className="text-sm font-medium text-text line-clamp-1 flex-1">
              {title || t("sidepanel:rag.untitledResult", "Untitled")}
            </h4>
            {isAttached && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium text-accent bg-accent/10 rounded-full flex-shrink-0">
                <Check className="h-3 w-3" />
                {t("sidepanel:fileSearch.attached", "Attached")}
              </span>
            )}
          </div>
          {score && (
            <span className="text-xs text-text-muted whitespace-nowrap">
              {score}
            </span>
          )}
        </div>

        {/* Metadata */}
        {(type || date) && (
          <div className="flex items-center gap-2 text-xs text-text-muted mb-2">
            {type && <span className="capitalize">{type}</span>}
            {type && date && <span>&middot;</span>}
            {date && <span>{date}</span>}
          </div>
        )}

        {/* Snippet */}
        <p className="text-xs text-text-muted line-clamp-3 mb-3">
          {highlightText(snippet, query ?? "", {
            highlightClassName: "bg-warn/20 text-text rounded px-0.5"
          })}
        </p>

        {/* Actions */}
        <div className="flex items-center gap-1">
          <Tooltip
            title={
              isAttached
                ? t("sidepanel:fileSearch.alreadyAttached", "Already attached")
                : t("sidepanel:fileSearch.attach", "Attach to chat")
            }
          >
            <Button
              type={isAttached ? "text" : "primary"}
              size="small"
              onClick={() => onAttach(result)}
              icon={
                isAttached ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  <Paperclip className="h-3.5 w-3.5" />
                )
              }
              className={isAttached ? "text-accent" : ""}
            >
              {isAttached
                ? t("sidepanel:fileSearch.attached", "Attached")
                : t("sidepanel:fileSearch.attach", "Attach")}
            </Button>
          </Tooltip>

          <Tooltip title={t("sidepanel:rag.actions.preview", "Preview")}>
            <Button
              type="text"
              size="small"
              onClick={() => onPreview(result)}
              icon={<Eye className="h-3.5 w-3.5" />}
              className="text-text-muted hover:text-accent"
            >
              {t("sidepanel:rag.actions.preview", "Preview")}
            </Button>
          </Tooltip>

          <Tooltip title={t("sidepanel:fileSearch.openExternal", "Open")}>
            <Button
              type="text"
              size="small"
              onClick={() => onOpen(result)}
              icon={<ExternalLink className="h-3.5 w-3.5" />}
              className="text-text-muted hover:text-accent"
            >
              {t("sidepanel:fileSearch.open", "Open")}
            </Button>
          </Tooltip>

          <Tooltip
            title={
              isPinned
                ? t("sidepanel:rag.actions.pinned", "Already pinned")
                : t("sidepanel:rag.actions.pin", "Pin")
            }
          >
            <span className="inline-block">
              <Button
                type="text"
                size="small"
                onClick={() => onPin(result)}
                disabled={isPinned}
                icon={
                  <Pin
                    className={`h-3.5 w-3.5 ${isPinned ? "fill-current" : ""}`}
                  />
                }
                className={
                  isPinned
                    ? "text-accent"
                    : "text-text-muted hover:text-accent"
                }
              >
                {t("sidepanel:rag.actions.pin", "Pin")}
              </Button>
            </span>
          </Tooltip>
        </div>
      </div>
    )
  }
)

FileResultItem.displayName = "FileResultItem"
