import React, { useCallback, useEffect, useMemo, useState } from "react"
import { Alert, Button, Modal, Select, Space, Switch, Table, Tag, Upload, message } from "antd"
import type { UploadFile } from "antd/es/upload/interface"
import { UploadCloud } from "lucide-react"
import { useTranslation } from "react-i18next"
import { fetchWatchlistSources, importOpml } from "@/services/watchlists"
import type { SourcesImportResponse, WatchlistGroup, WatchlistTag } from "@/types/watchlists"
import { buildOpmlPreflightSummary, type OpmlPreflightItem, type OpmlPreflightStatus } from "./opml-preflight"

const EXISTING_URL_LOOKUP_PAGE_SIZE = 200
const EXISTING_URL_LOOKUP_MAX_PAGES = 10
const PREVIEW_ROW_LIMIT = 200

interface SourcesBulkImportProps {
  open: boolean
  onClose: () => void
  groups: WatchlistGroup[]
  tags: WatchlistTag[]
  defaultGroupId?: number | null
  onImported: () => void
}

const PREVIEW_STATUS_COLOR: Record<OpmlPreflightStatus, string> = {
  ready: "green",
  duplicate_existing: "orange",
  duplicate_file: "gold",
  missing_url: "red",
  invalid_url: "red"
}

export const SourcesBulkImport: React.FC<SourcesBulkImportProps> = ({
  open,
  onClose,
  groups,
  tags,
  defaultGroupId,
  onImported
}) => {
  const { t } = useTranslation(["watchlists", "common"])
  const [active, setActive] = useState(true)
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(defaultGroupId ?? null)
  const [importing, setImporting] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [preflight, setPreflight] = useState<ReturnType<typeof buildOpmlPreflightSummary> | null>(null)
  const [existingUrls, setExistingUrls] = useState<string[]>([])
  const [existingUrlsLoading, setExistingUrlsLoading] = useState(false)
  const [existingUrlsLoaded, setExistingUrlsLoaded] = useState(false)
  const [result, setResult] = useState<SourcesImportResponse | null>(null)

  const resetState = useCallback(() => {
    setActive(true)
    setSelectedTags([])
    setSelectedGroupId(defaultGroupId ?? null)
    setImporting(false)
    setSelectedFile(null)
    setPreflight(null)
    setExistingUrls([])
    setExistingUrlsLoading(false)
    setExistingUrlsLoaded(false)
    setResult(null)
  }, [defaultGroupId])

  const loadExistingUrls = useCallback(async (): Promise<string[]> => {
    setExistingUrlsLoading(true)
    try {
      const urls: string[] = []
      let page = 1
      while (page <= EXISTING_URL_LOOKUP_MAX_PAGES) {
        const response = await fetchWatchlistSources({
          page,
          size: EXISTING_URL_LOOKUP_PAGE_SIZE
        })
        const pageItems = Array.isArray(response.items) ? response.items : []
        urls.push(...pageItems.map((item) => item.url).filter(Boolean))
        if (
          pageItems.length < EXISTING_URL_LOOKUP_PAGE_SIZE ||
          urls.length >= Number(response.total || 0)
        ) {
          break
        }
        page += 1
      }
      setExistingUrls(urls)
      setExistingUrlsLoaded(true)
      return urls
    } catch (err) {
      console.error("Failed to load existing sources for import preview:", err)
      setExistingUrlsLoaded(true)
      message.warning(
        t(
          "watchlists:sources.importPreviewLookupError",
          "Could not load existing feeds for duplicate checks."
        )
      )
      return []
    } finally {
      setExistingUrlsLoading(false)
    }
  }, [t])

  useEffect(() => {
    if (!open) {
      resetState()
      return
    }
    void loadExistingUrls()
  }, [loadExistingUrls, open, resetState])

  const summary = useMemo(() => {
    if (!result?.items?.length) return null
    const created = result.items.filter((item) => item.status === "created").length
    const skipped = result.items.filter((item) => item.status === "skipped").length
    const errors = result.items.filter((item) => item.status === "error").length
    return { created, skipped, errors }
  }, [result])

  const canCommitImport = Boolean(
    selectedFile &&
    preflight &&
    preflight.ready > 0 &&
    !preflight.parseError &&
    !importing
  )

  const handlePreflight = useCallback(async (file: File) => {
    setSelectedFile(file)
    setResult(null)
    try {
      const opml = await file.text()
      const urls = existingUrlsLoaded ? existingUrls : await loadExistingUrls()
      const preview = buildOpmlPreflightSummary(opml, { existingUrls: urls })
      setPreflight(preview)
    } catch (err) {
      console.error("OPML preview failed:", err)
      setPreflight(null)
      message.error(
        t("watchlists:sources.importPreviewError", "Failed to preview OPML file")
      )
    }
  }, [existingUrls, existingUrlsLoaded, loadExistingUrls, t])

  const handleCommitImport = async () => {
    if (!selectedFile || !preflight) return
    if (preflight.parseError || preflight.ready === 0) {
      message.warning(
        t(
          "watchlists:sources.importPreviewNothingToImport",
          "No valid feed entries to import."
        )
      )
      return
    }

    setImporting(true)
    try {
      const response = await importOpml(selectedFile, {
        active,
        tags: selectedTags,
        group_id: selectedGroupId ?? undefined
      })
      setResult(response)
      onImported()
      message.success(t("watchlists:sources.imported", "OPML imported"))
    } catch (err) {
      console.error("OPML import failed:", err)
      message.error(t("watchlists:sources.importError", "Failed to import OPML"))
    } finally {
      setImporting(false)
    }
  }

  const uploadProps = {
    accept: ".opml,.xml",
    multiple: false,
    showUploadList: false,
    beforeUpload: async (file: UploadFile) => {
      if (!file.originFileObj) return false
      await handlePreflight(file.originFileObj as File)
      return false
    }
  }

  const errorItems = (result?.items || []).filter((item) => item.status === "error")

  const renderPreflightStatus = (status: OpmlPreflightStatus) => (
    <Tag color={PREVIEW_STATUS_COLOR[status]}>
      {t(
        `watchlists:sources.importPreviewStatus.${status}`,
        status.replace(/_/g, " ")
      )}
    </Tag>
  )

  return (
    <Modal
      title={t("watchlists:sources.importTitle", "Import OPML")}
      open={open}
      onCancel={onClose}
      footer={(
        <Space>
          <Button onClick={onClose}>
            {t("common:close", "Close")}
          </Button>
          <Button
            type="primary"
            onClick={handleCommitImport}
            loading={importing}
            disabled={!canCommitImport}
          >
            {t(
              "watchlists:sources.importConfirm",
              "Import {{count}} feed{{plural}}",
              {
                count: preflight?.ready ?? 0,
                plural: (preflight?.ready ?? 0) === 1 ? "" : "s"
              }
            )}
          </Button>
        </Space>
      )}
      width={900}
    >
      <div className="space-y-4">
        <Upload.Dragger {...uploadProps} disabled={importing}>
          <div className="flex flex-col items-center justify-center gap-2 py-6 text-text-muted">
            <UploadCloud className="h-6 w-6" />
            <div className="text-sm font-medium">
              {t("watchlists:sources.importDrop", "Drop OPML file here or click to upload")}
            </div>
            <div className="text-xs">
              {t("watchlists:sources.importHint", "Supports standard OPML exports")}
            </div>
            {selectedFile && (
              <div className="text-xs text-text-subtle">
                {t("watchlists:sources.importSelectedFile", "Selected: {{file}}", {
                  file: selectedFile.name
                })}
              </div>
            )}
          </div>
        </Upload.Dragger>

        <div className="grid gap-3 md:grid-cols-3">
          <div>
            <div className="text-xs font-medium text-text-muted mb-1">
              {t("watchlists:sources.importGroup", "Assign Group")}
            </div>
            <Select
              value={selectedGroupId ?? undefined}
              onChange={(value) => setSelectedGroupId(value ?? null)}
              allowClear
              placeholder={t("watchlists:sources.importGroupPlaceholder", "None")}
              options={groups.map((group) => ({
                label: group.name,
                value: group.id
              }))}
              className="w-full"
            />
          </div>
          <div>
            <div className="text-xs font-medium text-text-muted mb-1">
              {t("watchlists:sources.importTags", "Apply Tags")}
            </div>
            <Select
              mode="multiple"
              value={selectedTags}
              onChange={setSelectedTags}
              placeholder={t("watchlists:sources.importTagsPlaceholder", "Select tags")}
              options={tags.map((tag) => ({ label: tag.name, value: tag.name }))}
              className="w-full"
            />
          </div>
          <div>
            <div className="text-xs font-medium text-text-muted mb-1">
              {t("watchlists:sources.importActive", "Set Active")}
            </div>
            <Switch checked={active} onChange={setActive} />
          </div>
        </div>

        {existingUrlsLoading && (
          <Alert
            type="info"
            showIcon
            message={t(
              "watchlists:sources.importPreviewLoadingExisting",
              "Loading existing feeds for duplicate checks..."
            )}
          />
        )}

        {preflight && (
          <Alert
            type={preflight.parseError ? "error" : preflight.ready > 0 ? "info" : "warning"}
            showIcon
            message={t("watchlists:sources.importPreviewSummaryTitle", "Preflight Summary")}
            description={preflight.parseError
              ? t(
                  "watchlists:sources.importPreviewParseError",
                  "Could not parse this OPML file. Verify it contains outline nodes with xmlUrl attributes."
                )
              : t(
                  "watchlists:sources.importPreviewSummary",
                  "{{ready}} ready, {{duplicateExisting}} existing duplicates, {{duplicateFile}} file duplicates, {{invalidUrl}} invalid URLs, {{missingUrl}} missing URLs.",
                  {
                    ready: preflight.ready,
                    duplicateExisting: preflight.duplicateExisting,
                    duplicateFile: preflight.duplicateFile,
                    invalidUrl: preflight.invalidUrl,
                    missingUrl: preflight.missingUrl
                  }
                )}
          />
        )}

        {preflight && preflight.items.length > 0 && (
          <Table<OpmlPreflightItem>
            dataSource={preflight.items.slice(0, PREVIEW_ROW_LIMIT)}
            rowKey={(item, idx) => `${item.url}-${idx}`}
            pagination={false}
            size="small"
            columns={[
              {
                title: t("watchlists:sources.columns.name", "Name"),
                dataIndex: "name",
                key: "name",
                render: (name: string, record) => name || record.url || "-"
              },
              {
                title: t("watchlists:sources.columns.url", "URL"),
                dataIndex: "url",
                key: "url",
                ellipsis: true,
                render: (url: string) => url || "-"
              },
              {
                title: t("watchlists:sources.importPreviewStatusTitle", "Preflight Status"),
                dataIndex: "status",
                key: "status",
                width: 180,
                render: (status: OpmlPreflightStatus) => renderPreflightStatus(status)
              }
            ]}
          />
        )}

        {summary && (
          <Alert
            type={summary.errors > 0 ? "warning" : "success"}
            showIcon
            message={t("watchlists:sources.importSummary", "Import Summary")}
            description={t(
              "watchlists:sources.importSummaryDesc",
              "{{created}} created, {{skipped}} skipped, {{errors}} errors",
              summary
            )}
          />
        )}

        {errorItems.length > 0 && (
          <Table
            dataSource={errorItems}
            rowKey={(item, idx) => `${item.url}-${idx}`}
            pagination={false}
            size="small"
            columns={[
              {
                title: t("watchlists:sources.columns.name", "Name"),
                dataIndex: "name",
                key: "name",
                render: (name: string | null, record) => name || record.url
              },
              {
                title: t("watchlists:sources.columns.url", "URL"),
                dataIndex: "url",
                key: "url",
                ellipsis: true
              },
              {
                title: t("watchlists:sources.columns.status", "Status"),
                dataIndex: "status",
                key: "status"
              },
              {
                title: t("watchlists:sources.columns.error", "Error"),
                dataIndex: "error",
                key: "error",
                ellipsis: true
              }
            ]}
          />
        )}
      </div>
    </Modal>
  )
}
