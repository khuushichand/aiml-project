import React from "react"
import { Link } from "react-router-dom"
import { FlaskConical, X } from "lucide-react"
import { useTranslation } from "react-i18next"

import type { AttachedResearchContext } from "./research-chat-context"

type AttachedResearchContextChipProps = {
  context: AttachedResearchContext
  pinned?: AttachedResearchContext | null
  history?: AttachedResearchContext[]
  onPreview?: () => void
  onRemove: () => void
  onPin?: () => void
  onUnpin?: () => void
  onRestorePinned?: () => void
  onSelectHistory?: (context: AttachedResearchContext) => void
}

export const AttachedResearchContextChip = ({
  context,
  pinned = null,
  history = [],
  onPreview,
  onRemove,
  onPin,
  onUnpin,
  onRestorePinned,
  onSelectHistory
}: AttachedResearchContextChipProps) => {
  const { t } = useTranslation(["playground", "common"])
  const pinnedMatchesActive = pinned?.run_id === context.run_id

  return (
    <div
      data-testid="attached-research-context-chip"
      className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-primaryStrong"
    >
      <div className="flex min-w-0 items-center gap-2">
        <FlaskConical className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <div className="min-w-0">
          <div className="font-medium">
            {t(
              "playground:composer.researchContextAttached",
              "Deep Research attached"
            )}
          </div>
          <div className="truncate text-[11px] text-primaryStrong/90">
            {context.query}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {onPreview ? (
          <button
            type="button"
            onClick={onPreview}
            className="rounded border border-primary/30 bg-surface px-2 py-0.5 text-[11px] font-medium text-primaryStrong hover:bg-primary/10"
          >
            {t(
              "playground:actions.previewAttachedResearchContext",
              "Edit attached research"
            )}
          </button>
        ) : null}
        {pinnedMatchesActive ? (
          <button
            type="button"
            onClick={onUnpin}
            className="rounded border border-primary/30 bg-surface px-2 py-0.5 text-[11px] font-medium text-primaryStrong hover:bg-primary/10"
          >
            {t("playground:actions.unpinResearchContext", "Unpin")}
          </button>
        ) : (
          <button
            type="button"
            onClick={onPin}
            className="rounded border border-primary/30 bg-surface px-2 py-0.5 text-[11px] font-medium text-primaryStrong hover:bg-primary/10"
          >
            {t("playground:actions.pinResearchContext", "Pin")}
          </button>
        )}
        <Link
          to={context.research_url}
          className="rounded border border-primary/30 bg-surface px-2 py-0.5 text-[11px] font-medium text-primaryStrong hover:bg-primary/10"
        >
          {t("playground:actions.openInResearch", "Open in Research")}
        </Link>
        <button
          type="button"
          onClick={onRemove}
          className="rounded p-1 text-primaryStrong/80 hover:bg-primary/10 hover:text-primaryStrong"
          aria-label={
            t(
              "playground:composer.removeResearchContext",
              "Remove attached research"
            ) as string
          }
          title={
            t(
              "playground:composer.removeResearchContext",
              "Remove attached research"
            ) as string
          }
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>
      {pinned && !pinnedMatchesActive ? (
        <div
          data-testid="attached-research-context-pinned"
          className="flex w-full flex-wrap items-center gap-2 border-t border-primary/20 pt-2 text-[11px]"
        >
          <span className="font-medium text-primaryStrong/90">
            {t("playground:composer.pinnedResearch", "Pinned research")}
          </span>
          <button
            type="button"
            onClick={onRestorePinned}
            className="rounded border border-primary/20 bg-surface px-2 py-0.5 text-[11px] text-primaryStrong hover:bg-primary/10"
          >
            {pinned.query}
          </button>
          <button
            type="button"
            onClick={onUnpin}
            className="rounded border border-primary/20 bg-surface px-2 py-0.5 text-[11px] text-primaryStrong hover:bg-primary/10"
          >
            {t("playground:actions.unpinResearchContext", "Unpin")}
          </button>
        </div>
      ) : null}
      {history.length > 0 ? (
        <div
          data-testid="attached-research-context-history"
          className="flex w-full flex-wrap items-center gap-2 border-t border-primary/20 pt-2 text-[11px]"
        >
          <span className="font-medium text-primaryStrong/90">
            {t("playground:composer.recentResearch", "Recent research")}
          </span>
          {history.map((entry) => (
            <button
              key={entry.run_id}
              type="button"
              onClick={() => onSelectHistory?.(entry)}
              className="rounded border border-primary/20 bg-surface px-2 py-0.5 text-[11px] text-primaryStrong hover:bg-primary/10"
            >
              {entry.query}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
