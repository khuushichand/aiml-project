import React from "react"
import { Tag } from "antd"

import type { IngestionSourceSummary } from "@/types/ingestion-sources"

type SourceStatusPanelsProps = {
  source: IngestionSourceSummary
}

export const SourceStatusPanels: React.FC<SourceStatusPanelsProps> = ({ source }) => {
  const summary = source.last_successful_sync_summary
  if (!summary) {
    return (
      <div className="flex flex-wrap gap-2">
        <Tag>{source.last_sync_status || "Unknown status"}</Tag>
      </div>
    )
  }

  return (
    <div className="flex flex-wrap gap-2">
      <Tag color="blue">Changed {summary.changed_count}</Tag>
      {summary.degraded_count > 0 && <Tag color="orange">Degraded {summary.degraded_count}</Tag>}
      {summary.conflict_count > 0 && <Tag color="volcano">Detached {summary.conflict_count}</Tag>}
      <Tag>{source.last_sync_status || "Unknown status"}</Tag>
    </div>
  )
}
