import React from "react"
import { Button, InputNumber, Modal } from "antd"
import { ContextFootprintPanel } from "./ContextFootprintPanel"
import { SessionInsightsPanel } from "./SessionInsightsPanel"
import { CONTEXT_FOOTPRINT_THRESHOLD_PERCENT } from "./hooks"
import type { Switch, Select, Input, Radio } from "antd"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PlaygroundContextWindowModalProps {
  // Context window
  contextWindowModalOpen: boolean
  onCloseContextWindow: () => void
  onSaveContextWindow: () => void
  onResetContextWindow: () => void
  contextWindowDraftValue: number | undefined
  onContextWindowDraftChange: (value: number | undefined) => void
  resolvedMaxContext: number
  requestedContextWindowOverride: number | undefined
  modelContextLength: number | undefined
  isContextWindowOverrideActive: boolean
  isContextWindowOverrideClamped: boolean
  nonMessageContextPercent: number | null
  showNonMessageContextWarning: boolean
  tokenBudgetRiskLabel: string
  tokenBudgetRisk: { overflowTokens: number }
  contextFootprintRows: any[]
  formatContextWindowValue: (value: number | undefined) => string

  // Footprint actions
  onClearPromptContext: () => void
  onClearPinnedSourceContext: () => void
  onClearHistoryContext: () => void
  onCreateSummaryCheckpoint: () => void
  onReviewCharacterContext: () => void
  onTrimLargestContextContributor: () => void

  // Session insights
  sessionInsightsOpen: boolean
  onCloseSessionInsights: () => void
  sessionInsights: any

  t: (key: string, defaultValue?: string, options?: any) => any
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const PlaygroundContextWindowModal: React.FC<PlaygroundContextWindowModalProps> =
  React.memo(function PlaygroundContextWindowModal(props) {
    const {
      contextWindowModalOpen,
      onCloseContextWindow,
      onSaveContextWindow,
      onResetContextWindow,
      contextWindowDraftValue,
      onContextWindowDraftChange,
      resolvedMaxContext,
      requestedContextWindowOverride,
      modelContextLength,
      isContextWindowOverrideActive,
      isContextWindowOverrideClamped,
      nonMessageContextPercent,
      showNonMessageContextWarning,
      tokenBudgetRiskLabel,
      tokenBudgetRisk,
      contextFootprintRows,
      formatContextWindowValue,
      onClearPromptContext,
      onClearPinnedSourceContext,
      onClearHistoryContext,
      onCreateSummaryCheckpoint,
      onReviewCharacterContext,
      onTrimLargestContextContributor,
      sessionInsightsOpen,
      onCloseSessionInsights,
      sessionInsights,
      t
    } = props

    return (
      <>
        <Modal
          title={t(
            "common:modelSettings.form.numCtx.label",
            "Context Window Size (num_ctx)"
          )}
          open={contextWindowModalOpen}
          onCancel={onCloseContextWindow}
          onOk={onSaveContextWindow}
          okText={t("common:save", "Save")}
          destroyOnHidden
          footer={
            <div className="flex flex-wrap justify-end gap-2">
              <Button onClick={onCloseContextWindow}>
                {t("common:cancel", "Cancel")}
              </Button>
              <Button onClick={onResetContextWindow}>
                {t(
                  "playground:tokens.useModelDefault",
                  "Use model default"
                )}
              </Button>
              <Button type="primary" onClick={onSaveContextWindow}>
                {t("common:save", "Save")}
              </Button>
            </div>
          }
        >
          <div className="space-y-3">
            <p className="text-sm text-text-muted">
              {t(
                "playground:tokens.contextWindowOverrideDescription",
                "Set a chat-level context window override. Leave empty to use the model default."
              )}
            </p>
            <InputNumber
              style={{ width: "100%" }}
              min={1}
              step={256}
              value={contextWindowDraftValue}
              placeholder={t(
                "common:modelSettings.form.numCtx.placeholder",
                "e.g. 4096"
              )}
              onChange={(value) => {
                onContextWindowDraftChange(
                  typeof value === "number" && Number.isFinite(value)
                    ? value
                    : undefined
                )
              }}
            />
            <div className="space-y-1 text-xs text-text-muted">
              <p>
                {t(
                  "playground:tokens.effectiveContextWindow",
                  "Effective context window"
                )}
                : {formatContextWindowValue(resolvedMaxContext)}{" "}
                {t("playground:tokens.tokenUnit", "tokens")}
              </p>
              <p>
                {t(
                  "playground:tokens.requestedContextWindow",
                  "Requested context window"
                )}
                : {formatContextWindowValue(requestedContextWindowOverride)}{" "}
                {t("playground:tokens.tokenUnit", "tokens")}
              </p>
              <p>
                {t(
                  "playground:tokens.modelDefaultContextWindow",
                  "Model default context window"
                )}
                : {formatContextWindowValue(modelContextLength)}{" "}
                {t("playground:tokens.tokenUnit", "tokens")}
              </p>
              <p>
                {t(
                  "playground:tokens.chatOverrideStatus",
                  "Chat override"
                )}
                :{" "}
                {isContextWindowOverrideActive
                  ? t("common:enabled", "Enabled")
                  : t("common:disabled", "Disabled")}
              </p>
              {nonMessageContextPercent != null && (
                <p>
                  {t(
                    "playground:tokens.nonMessageShare",
                    "Non-message context share"
                  )}
                  : {Math.round(nonMessageContextPercent)}%
                </p>
              )}
              <p>
                {t(
                  "playground:tokens.truncationRisk",
                  "Projected truncation risk"
                )}
                : {tokenBudgetRiskLabel}
                {tokenBudgetRisk.overflowTokens > 0
                  ? ` (${t(
                      "playground:tokens.overflowTokens",
                      "{{count}} tokens over",
                      {
                        count: tokenBudgetRisk.overflowTokens
                      } as any
                    )})`
                  : ""}
              </p>
              {isContextWindowOverrideClamped && (
                <p className="text-warn">
                  {t(
                    "playground:tokens.contextWindowClamped",
                    "Requested override exceeds the model maximum. Effective value is clamped to the model limit."
                  )}
                </p>
              )}
            </div>
            <ContextFootprintPanel
              t={t}
              rows={contextFootprintRows}
              nonMessageContextPercent={nonMessageContextPercent}
              showNonMessageContextWarning={showNonMessageContextWarning}
              thresholdPercent={CONTEXT_FOOTPRINT_THRESHOLD_PERCENT}
              onClearPromptContext={onClearPromptContext}
              onClearPinnedSourceContext={onClearPinnedSourceContext}
              onClearHistoryContext={onClearHistoryContext}
              onCreateSummaryCheckpoint={onCreateSummaryCheckpoint}
              onReviewCharacterContext={onReviewCharacterContext}
              onTrimLargestContextContributor={
                onTrimLargestContextContributor
              }
            />
          </div>
        </Modal>
        <Modal
          title={t("playground:insights.modalTitle", "Session insights")}
          open={sessionInsightsOpen}
          onCancel={onCloseSessionInsights}
          destroyOnHidden
          width={760}
          footer={
            <div className="flex justify-end">
              <Button onClick={onCloseSessionInsights}>
                {t("common:close", "Close")}
              </Button>
            </div>
          }
        >
          <SessionInsightsPanel t={t} insights={sessionInsights} />
        </Modal>
      </>
    )
  })
