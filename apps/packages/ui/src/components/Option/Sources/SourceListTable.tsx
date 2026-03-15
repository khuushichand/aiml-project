import React from "react"
import { Button, Card, Empty, Space, Typography } from "antd"
import { useNavigate } from "react-router-dom"

import { useSyncIngestionSourceMutation, useUpdateIngestionSourceMutation } from "@/hooks/use-ingestion-sources"
import type { IngestionSourceSummary } from "@/types/ingestion-sources"
import { SourceStatusPanels } from "./SourceStatusPanels"

const getSourceLabel = (source: IngestionSourceSummary): string => {
  const configuredLabel = source.config?.label
  if (typeof configuredLabel === "string" && configuredLabel.trim().length > 0) {
    return configuredLabel
  }
  const configuredPath = source.config?.path
  if (typeof configuredPath === "string" && configuredPath.trim().length > 0) {
    return configuredPath
  }
  return `${source.source_type} ${source.id}`
}

const SourceEnabledAction: React.FC<{ source: IngestionSourceSummary }> = ({ source }) => {
  const updateMutation = useUpdateIngestionSourceMutation(source.id)

  return (
    <Button
      onClick={() => {
        void updateMutation.mutateAsync({
          enabled: !source.enabled
        })
      }}
      loading={Boolean((updateMutation as { isPending?: boolean }).isPending)}>
      {source.enabled ? "Disable" : "Enable"}
    </Button>
  )
}

type SourceListTableProps = {
  sources: IngestionSourceSummary[]
}

export const SourceListTable: React.FC<SourceListTableProps> = ({ sources }) => {
  const navigate = useNavigate()
  const syncMutation = useSyncIngestionSourceMutation()

  if (sources.length === 0) {
    return <Empty description="No ingestion sources yet." />
  }

  return (
    <div className="space-y-4">
      {sources.map((source) => (
        <Card key={source.id} className="rounded-2xl">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-2">
              <Typography.Title level={4} className="!mb-0">
                {getSourceLabel(source)}
              </Typography.Title>
              <Typography.Text type="secondary">
                {`${source.source_type} -> ${source.sink_type} (${source.policy})`}
              </Typography.Text>
              <SourceStatusPanels source={source} />
            </div>
            <Space wrap>
              <Button
                type="primary"
                onClick={() => {
                  void syncMutation.mutateAsync(source.id)
                }}
                loading={Boolean((syncMutation as { isPending?: boolean }).isPending)}>
                Sync now
              </Button>
              <SourceEnabledAction source={source} />
              <Button
                onClick={() => {
                  navigate(`/sources/${source.id}`)
                }}>
                Open detail
              </Button>
            </Space>
          </div>
        </Card>
      ))}
    </div>
  )
}
