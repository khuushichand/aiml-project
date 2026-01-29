import { Tooltip } from "antd"
import { Activity, Clock, CheckCircle2, AlertCircle } from "lucide-react"
import React from "react"
import { useTranslation } from "react-i18next"
import type { PromptStudioStatus } from "@/services/prompt-studio"

type QueueHealthWidgetProps = {
  status?: PromptStudioStatus | null
}

export const QueueHealthWidget: React.FC<QueueHealthWidgetProps> = ({
  status
}) => {
  const { t } = useTranslation(["settings", "common"])

  if (!status) {
    return null
  }

  const successRate = status.success_rate ?? 1
  const successPercent = Math.round(successRate * 100)
  const hasIssues = successPercent < 90 || status.queue_depth > 10

  const getHealthColor = () => {
    if (successPercent >= 95 && status.queue_depth <= 5) return "text-success"
    if (successPercent >= 80 && status.queue_depth <= 15) return "text-warn"
    return "text-danger"
  }

  const formatProcessingTime = (seconds?: number) => {
    if (!seconds) return "-"
    if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
    if (seconds < 60) return `${seconds.toFixed(1)}s`
    return `${Math.round(seconds / 60)}m`
  }

  const tooltipContent = (
    <div className="space-y-2 text-sm">
      <div className="font-medium border-b border-border pb-1">
        {t("managePrompts.studio.queueHealth.title", {
          defaultValue: "Queue Health"
        })}
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        <span className="text-text-muted">
          {t("managePrompts.studio.queueHealth.queueDepth", {
            defaultValue: "Queue depth:"
          })}
        </span>
        <span>{status.queue_depth}</span>

        <span className="text-text-muted">
          {t("managePrompts.studio.queueHealth.processing", {
            defaultValue: "Processing:"
          })}
        </span>
        <span>{status.processing}</span>

        <span className="text-text-muted">
          {t("managePrompts.studio.queueHealth.successRate", {
            defaultValue: "Success rate:"
          })}
        </span>
        <span className={successPercent < 90 ? "text-danger" : ""}>
          {successPercent}%
        </span>

        <span className="text-text-muted">
          {t("managePrompts.studio.queueHealth.avgTime", {
            defaultValue: "Avg time:"
          })}
        </span>
        <span>{formatProcessingTime(status.avg_processing_time_seconds)}</span>
      </div>

      {status.by_status && Object.keys(status.by_status).length > 0 && (
        <>
          <div className="font-medium border-t border-border pt-1 mt-2">
            {t("managePrompts.studio.queueHealth.byStatus", {
              defaultValue: "By Status"
            })}
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            {Object.entries(status.by_status).map(([key, value]) => (
              <React.Fragment key={key}>
                <span className="text-text-muted capitalize">{key}:</span>
                <span>{value}</span>
              </React.Fragment>
            ))}
          </div>
        </>
      )}
    </div>
  )

  return (
    <Tooltip title={tooltipContent} placement="bottomRight">
      <div
        className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md border cursor-help ${
          hasIssues
            ? "border-warn/30 bg-warn/5"
            : "border-border bg-surface2/50"
        }`}
        data-testid="queue-health-widget"
      >
        <Activity className={`size-4 ${getHealthColor()}`} />

        <div className="flex items-center gap-3 text-xs">
          {/* Queue depth */}
          <span className="flex items-center gap-1">
            <Clock className="size-3 text-text-muted" />
            <span>{status.queue_depth}</span>
          </span>

          {/* Processing */}
          {status.processing > 0 && (
            <span className="flex items-center gap-1 text-success">
              <span className="inline-block size-2 bg-success rounded-full animate-pulse" />
              <span>{status.processing}</span>
            </span>
          )}

          {/* Success rate */}
          <span
            className={`flex items-center gap-1 ${
              successPercent >= 90 ? "text-success" : "text-danger"
            }`}
          >
            {successPercent >= 90 ? (
              <CheckCircle2 className="size-3" />
            ) : (
              <AlertCircle className="size-3" />
            )}
            <span>{successPercent}%</span>
          </span>
        </div>
      </div>
    </Tooltip>
  )
}
