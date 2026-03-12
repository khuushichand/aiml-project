import React from "react"
import { Collapse } from "antd"
import { SourceFeedback } from "@/components/Sidepanel/Chat/SourceFeedback"
import type { FeedbackThumb, SourceFeedbackEntry } from "@/store/feedback"
import { getSourceFeedbackKey } from "@/utils/feedback"

interface MessageSourcesSectionProps {
  sources: any[]
  t: (...args: any[]) => any
  feedbackDisabled: boolean
  isFeedbackSubmitting: boolean
  sourceFeedback: Record<string, SourceFeedbackEntry> | null
  submitSourceThumb: (args: {
    sourceKey: string
    source: any
    thumb: FeedbackThumb
  }) => void
  trackSourcesExpanded: () => void
  trackSourceClick: (...args: any[]) => void
  trackCitationUsed: (...args: any[]) => void
  trackDwellTime: (ms: number, source?: any, index?: number) => void
  resolveSourcePinnedState: (source: any) => "active" | "inactive" | null
  onAskWithSources: (sources: any[]) => void
  onOpenKnowledgePanel: () => void
  onSourceClick?: (source: any) => void
}

export const MessageSourcesSection = React.memo(function MessageSourcesSection(
  props: MessageSourcesSectionProps
) {
  const {
    sources,
    t,
    feedbackDisabled,
    isFeedbackSubmitting,
    sourceFeedback,
    submitSourceThumb,
    trackSourcesExpanded,
    trackSourceClick,
    trackCitationUsed,
    trackDwellTime,
    resolveSourcePinnedState,
    onAskWithSources,
    onOpenKnowledgePanel,
    onSourceClick
  } = props

  return (
    <Collapse
      className="mt-6"
      ghost
      onChange={(activeKey) => {
        const opened = Array.isArray(activeKey)
          ? activeKey.length > 0
          : Boolean(activeKey)
        if (opened) {
          trackSourcesExpanded()
        }
      }}
      items={[
        {
          key: "1",
          label: (
            <div className="italic text-text-muted">
              {t("citations")}
            </div>
          ),
          children: (
            <div className="mb-3 flex flex-col gap-2">
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-surface2 px-2 py-1 text-[11px] text-text-muted">
                <span>
                  {t(
                    "playground:sources.citationWorkflowHint",
                    "Inspect source rationale, then seed a follow-up from selected citations."
                  )}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onAskWithSources(sources)}
                    className="rounded border border-border bg-surface px-2 py-0.5 text-[10px] font-medium text-text-subtle hover:bg-surface2 hover:text-text"
                  >
                    {t(
                      "playground:sources.askWithSources",
                      "Ask with these sources"
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={onOpenKnowledgePanel}
                    className="rounded border border-border bg-surface px-2 py-0.5 text-[10px] font-medium text-text-subtle hover:bg-surface2 hover:text-text"
                  >
                    {t(
                      "playground:sources.openKnowledgePanel",
                      "Open Search & Context"
                    )}
                  </button>
                </div>
              </div>
              {sources.map((source, index) => {
                const sourceKey = getSourceFeedbackKey(source, index)
                const selected =
                  sourceFeedback?.[sourceKey]?.thumb ?? null
                const pinnedState = resolveSourcePinnedState(source)
                return (
                  <SourceFeedback
                    key={sourceKey}
                    source={source}
                    sourceKey={sourceKey}
                    sourceIndex={index}
                    pinnedState={pinnedState}
                    selected={selected}
                    disabled={feedbackDisabled || isFeedbackSubmitting}
                    onRate={(key, payload, thumb) =>
                      submitSourceThumb({
                        sourceKey: key,
                        source: payload,
                        thumb
                      })
                    }
                    onAskWithSource={(payload) =>
                      onAskWithSources([payload])
                    }
                    onOpenKnowledgePanel={onOpenKnowledgePanel}
                    onSourceClick={onSourceClick}
                    onTrackClick={trackSourceClick}
                    onTrackCitation={trackCitationUsed}
                    onTrackDwell={(
                      sourcePayload,
                      dwellMs,
                      sourceIndex
                    ) =>
                      trackDwellTime(dwellMs, sourcePayload, sourceIndex)
                    }
                  />
                )
              })}
            </div>
          )
        }
      ]}
    />
  )
})
