import React, { useCallback, useEffect, useMemo, useState } from "react"
import {
  Button,
  InputNumber,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  message
} from "antd"
import type { ColumnsType } from "antd/es/table"
import { Download, Eye, RefreshCw, RotateCcw } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useWatchlistsStore } from "@/store/watchlists"
import {
  createWatchlistOutput,
  fetchWatchlistJobs,
  fetchWatchlistOutputs,
  fetchWatchlistTemplates,
  downloadWatchlistOutput
} from "@/services/watchlists"
import type { WatchlistJob, WatchlistOutput, WatchlistTemplate } from "@/types/watchlists"
import { formatRelativeTime } from "@/utils/dateFormatters"
import { OutputPreviewDrawer } from "./OutputPreviewDrawer"
import {
  buildRegenerateOutputRequest,
  getDeliveryStatusColor,
  getOutputDeliveryStatuses,
  getOutputTemplateName,
  getOutputTemplateVersion
} from "./outputMetadata"

export const OutputsTab: React.FC = () => {
  const { t } = useTranslation(["watchlists", "common"])

  // Store state
  const outputs = useWatchlistsStore((s) => s.outputs)
  const outputsLoading = useWatchlistsStore((s) => s.outputsLoading)
  const outputsTotal = useWatchlistsStore((s) => s.outputsTotal)
  const outputsPage = useWatchlistsStore((s) => s.outputsPage)
  const outputsPageSize = useWatchlistsStore((s) => s.outputsPageSize)
  const outputsJobFilter = useWatchlistsStore((s) => s.outputsJobFilter)
  const outputPreviewOpen = useWatchlistsStore((s) => s.outputPreviewOpen)
  const selectedOutputId = useWatchlistsStore((s) => s.selectedOutputId)

  // Store actions
  const setOutputs = useWatchlistsStore((s) => s.setOutputs)
  const setOutputsLoading = useWatchlistsStore((s) => s.setOutputsLoading)
  const setOutputsPage = useWatchlistsStore((s) => s.setOutputsPage)
  const setOutputsPageSize = useWatchlistsStore((s) => s.setOutputsPageSize)
  const setOutputsJobFilter = useWatchlistsStore((s) => s.setOutputsJobFilter)
  const openOutputPreview = useWatchlistsStore((s) => s.openOutputPreview)
  const closeOutputPreview = useWatchlistsStore((s) => s.closeOutputPreview)

  const [jobs, setJobs] = useState<WatchlistJob[]>([])
  const [regenOpen, setRegenOpen] = useState(false)
  const [regenOutput, setRegenOutput] = useState<WatchlistOutput | null>(null)
  const [templates, setTemplates] = useState<WatchlistTemplate[]>([])
  const [templatesLoading, setTemplatesLoading] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null)
  const [selectedTemplateVersion, setSelectedTemplateVersion] = useState<number | null>(null)
  const [customTitle, setCustomTitle] = useState("")
  const [regenLoading, setRegenLoading] = useState(false)

  const selectedTemplateVersionOptions = useMemo(() => {
    if (!selectedTemplate) return []
    const template = templates.find((entry) => entry.name === selectedTemplate)
    if (!template?.available_versions || !Array.isArray(template.available_versions)) return []
    return [...template.available_versions]
      .filter((value): value is number => Number.isInteger(value) && value > 0)
      .sort((a, b) => b - a)
      .map((value) => ({ label: `v${value}`, value }))
  }, [selectedTemplate, templates])

  // Fetch outputs
  const loadOutputs = useCallback(async () => {
    setOutputsLoading(true)
    try {
      const result = await fetchWatchlistOutputs({
        job_id: outputsJobFilter || undefined,
        page: outputsPage,
        size: outputsPageSize
      })
      setOutputs(result.items, result.total)
    } catch (err) {
      console.error("Failed to fetch outputs:", err)
      message.error(t("watchlists:outputs.fetchError", "Failed to load outputs"))
    } finally {
      setOutputsLoading(false)
    }
  }, [outputsJobFilter, outputsPage, outputsPageSize, setOutputs, setOutputsLoading, t])

  // Load jobs for filter dropdown
  const loadJobs = useCallback(async () => {
    try {
      const result = await fetchWatchlistJobs({ page: 1, size: 200 })
      setJobs(result.items || [])
    } catch (err) {
      console.error("Failed to fetch jobs:", err)
    }
  }, [])

  // Initial load
  useEffect(() => {
    loadOutputs()
    loadJobs()
  }, [loadOutputs, loadJobs])

  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true)
    try {
      const result = await fetchWatchlistTemplates()
      setTemplates(Array.isArray(result.items) ? result.items : [])
    } catch (err) {
      console.error("Failed to fetch templates:", err)
      setTemplates([])
    } finally {
      setTemplatesLoading(false)
    }
  }, [])

  useEffect(() => {
    if (regenOpen) {
      loadTemplates()
    }
  }, [regenOpen, loadTemplates])

  // Get job name by ID
  const getJobName = useCallback(
    (jobId: number) => {
      const job = jobs.find((j) => j.id === jobId)
      return job?.name || `Job #${jobId}`
    },
    [jobs]
  )

  // Handle download
  const handleDownload = async (output: WatchlistOutput) => {
    try {
      const content = await downloadWatchlistOutput(output.id)
      const mimeType = output.format === "html" ? "text/html" : "text/markdown"
      const blob = new Blob([content], { type: mimeType })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `${output.title || `output-${output.id}`}.${output.format}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      message.success(t("watchlists:outputs.downloaded", "Output downloaded"))
    } catch (err) {
      console.error("Failed to download output:", err)
      message.error(t("watchlists:outputs.downloadError", "Failed to download output"))
    }
  }

  const openRegenerate = (output: WatchlistOutput) => {
    setRegenOutput(output)
    setSelectedTemplate(getOutputTemplateName(output.metadata) || null)
    setSelectedTemplateVersion(getOutputTemplateVersion(output.metadata) || null)
    setCustomTitle(output.title || "")
    setRegenOpen(true)
  }

  const handleRegenerate = async () => {
    if (!regenOutput) return
    setRegenLoading(true)
    try {
      const regeneratePayload = buildRegenerateOutputRequest(regenOutput, {
        title: customTitle,
        templateName: selectedTemplate,
        templateVersion: selectedTemplateVersion
      })
      await createWatchlistOutput(regeneratePayload)
      message.success(t("watchlists:outputs.regenerated", "Output regenerated"))
      setRegenOpen(false)
      loadOutputs()
    } catch (err) {
      console.error("Failed to regenerate output:", err)
      message.error(t("watchlists:outputs.regenerateError", "Failed to regenerate output"))
    } finally {
      setRegenLoading(false)
    }
  }

  // Get selected output for preview
  const selectedOutput = selectedOutputId
    ? outputs.find((o) => o.id === selectedOutputId)
    : null

  // Table columns
  const columns: ColumnsType<WatchlistOutput> = [
    {
      title: t("watchlists:outputs.columns.title", "Title"),
      dataIndex: "title",
      key: "title",
      ellipsis: true,
      render: (title: string | null, record) => (
        <span className="font-medium">
          {title || `Output #${record.id}`}
        </span>
      )
    },
    {
      title: t("watchlists:outputs.columns.job", "Job"),
      key: "job",
      width: 180,
      ellipsis: true,
      render: (_, record) => (
        <span className="text-sm text-text-muted">
          {getJobName(record.job_id)}
        </span>
      )
    },
    {
      title: t("watchlists:outputs.columns.run", "Run"),
      dataIndex: "run_id",
      key: "run_id",
      width: 100,
      render: (runId: number) => (
        <span className="text-sm text-text-muted">#{runId}</span>
      )
    },
    {
      title: t("watchlists:outputs.columns.format", "Format"),
      dataIndex: "format",
      key: "format",
      width: 100,
      render: (format: string) => (
        <Tag color={format === "html" ? "blue" : "green"}>
          {format.toUpperCase()}
        </Tag>
      )
    },
    {
      title: t("watchlists:outputs.columns.created", "Created"),
      dataIndex: "created_at",
      key: "created_at",
      width: 150,
      render: (date: string) => (
        <span className="text-sm text-text-muted">
          {formatRelativeTime(date, t)}
        </span>
      )
    },
    {
      title: t("watchlists:outputs.columns.delivery", "Delivery"),
      key: "delivery",
      width: 220,
      render: (_, record) => {
        const deliveries = getOutputDeliveryStatuses(record.metadata)
        if (deliveries.length === 0) {
          return <span className="text-text-subtle">-</span>
        }
        return (
          <Space size={[4, 4]} wrap>
            {deliveries.map((delivery, index) => (
              <Tooltip key={`${delivery.channel}-${delivery.status}-${index}`} title={delivery.detail}>
                <Tag color={getDeliveryStatusColor(delivery.status)}>
                  {delivery.channel}: {delivery.status}
                </Tag>
              </Tooltip>
            ))}
          </Space>
        )
      }
    },
    {
      title: t("watchlists:outputs.columns.expires", "Expires"),
      dataIndex: "expires_at",
      key: "expires_at",
      width: 150,
      render: (date: string | null, record) => {
        if (record.expired) {
          return <Tag color="red">Expired</Tag>
        }
        if (!date) {
          return <span className="text-text-subtle">Never</span>
        }
        return (
          <span className="text-sm text-text-muted">
            {formatRelativeTime(date, t)}
          </span>
        )
      }
    },
    {
      title: t("watchlists:outputs.columns.actions", "Actions"),
      key: "actions",
      width: 140,
      align: "center",
      render: (_, record) => (
        <Space size="small">
          <Tooltip title={t("watchlists:outputs.preview", "Preview")}>
            <Button
              type="text"
              size="small"
              icon={<Eye className="h-4 w-4" />}
              onClick={() => openOutputPreview(record.id)}
            />
          </Tooltip>
          <Tooltip title={t("watchlists:outputs.download", "Download")}>
            <Button
              type="text"
              size="small"
              icon={<Download className="h-4 w-4" />}
              onClick={() => handleDownload(record)}
            />
          </Tooltip>
          <Tooltip title={t("watchlists:outputs.regenerate", "Regenerate")}>
            <Button
              type="text"
              size="small"
              icon={<RotateCcw className="h-4 w-4" />}
              onClick={() => openRegenerate(record)}
            />
          </Tooltip>
        </Space>
      )
    }
  ]

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <Select
            placeholder={t("watchlists:outputs.filterByJob", "Filter by job")}
            value={outputsJobFilter}
            onChange={setOutputsJobFilter}
            allowClear
            className="w-48"
            options={jobs.map((j) => ({
              label: j.name,
              value: j.id
            }))}
          />
        </div>
        <Button
          icon={<RefreshCw className="h-4 w-4" />}
          onClick={loadOutputs}
          loading={outputsLoading}
        >
          {t("common:refresh", "Refresh")}
        </Button>
      </div>

      {/* Description */}
      <div className="text-sm text-text-muted">
        {t("watchlists:outputs.description", "Generated briefings and reports from your watchlist jobs.")}
      </div>

      {/* Table */}
      <Table
        dataSource={Array.isArray(outputs) ? outputs : []}
        columns={columns}
        rowKey="id"
        loading={outputsLoading}
        pagination={{
          current: outputsPage,
          pageSize: outputsPageSize,
          total: outputsTotal,
          showSizeChanger: true,
          showTotal: (total) =>
            t("watchlists:outputs.totalItems", "{{total}} outputs", { total }),
          onChange: (page, pageSize) => {
            setOutputsPage(page)
            if (pageSize !== outputsPageSize) {
              setOutputsPageSize(pageSize)
            }
          }
        }}
        size="middle"
        scroll={{ x: 800 }}
      />

      {/* Output Preview Drawer */}
      <OutputPreviewDrawer
        output={selectedOutput}
        open={outputPreviewOpen}
        onClose={closeOutputPreview}
      />

      <Modal
        title={t("watchlists:outputs.regenerateTitle", "Regenerate Output")}
        open={regenOpen}
        onCancel={() => setRegenOpen(false)}
        onOk={handleRegenerate}
        okText={t("watchlists:outputs.regenerate", "Regenerate")}
        cancelText={t("common:cancel", "Cancel")}
        confirmLoading={regenLoading}
      >
        <div className="space-y-3">
          <div>
            <div className="text-xs font-medium text-text-muted mb-1">
              {t("watchlists:outputs.templateLabel", "Template")}
            </div>
            <Select
              value={selectedTemplate ?? undefined}
              onChange={(value) => {
                const nextTemplate = value ?? null
                if (nextTemplate !== selectedTemplate) {
                  setSelectedTemplateVersion(null)
                }
                setSelectedTemplate(nextTemplate)
              }}
              placeholder={t("watchlists:outputs.templatePlaceholder", "Select a template")}
              options={templates.map((template) => ({
                label: template.name,
                value: template.name
              }))}
              loading={templatesLoading}
              allowClear
              className="w-full"
            />
          </div>
          <div>
            <div className="text-xs font-medium text-text-muted mb-1">
              {t("watchlists:outputs.templateVersionLabel", "Template version")}
            </div>
            {selectedTemplateVersionOptions.length > 0 ? (
              <Select
                value={selectedTemplateVersion ?? undefined}
                onChange={(value) =>
                  setSelectedTemplateVersion(typeof value === "number" ? value : null)
                }
                placeholder={t("watchlists:outputs.templateVersionPlaceholder", "Latest/default")}
                options={selectedTemplateVersionOptions}
                disabled={!selectedTemplate}
                allowClear
                className="w-full"
              />
            ) : (
              <InputNumber
                value={selectedTemplateVersion ?? undefined}
                min={1}
                precision={0}
                onChange={(value) =>
                  setSelectedTemplateVersion(
                    typeof value === "number" && Number.isInteger(value) && value > 0 ? value : null
                  )
                }
                disabled={!selectedTemplate}
                placeholder={t("watchlists:outputs.templateVersionPlaceholder", "Latest/default")}
                className="w-full"
              />
            )}
          </div>
          <div>
            <div className="text-xs font-medium text-text-muted mb-1">
              {t("watchlists:outputs.titleLabel", "Title")}
            </div>
            <Input
              value={customTitle}
              onChange={(e) => setCustomTitle(e.target.value)}
              placeholder={t("watchlists:outputs.titlePlaceholder", "Optional title override")}
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}
