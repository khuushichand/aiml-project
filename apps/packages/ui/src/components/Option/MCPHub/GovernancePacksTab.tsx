import { useEffect, useMemo, useState } from "react"
import { Alert, Button, Card, Descriptions, Empty, Input, List, Space, Tag, Typography } from "antd"

import {
  dryRunGovernancePack,
  getGovernancePackDetail,
  importGovernancePack,
  listGovernancePacks,
  type McpHubGovernancePackDetail,
  type McpHubGovernancePackDocument,
  type McpHubGovernancePackDryRunReport,
  type McpHubGovernancePackSummary
} from "@/services/tldw/mcp-hub"

const DEFAULT_PACK_JSON = JSON.stringify(
  {
    manifest: {},
    profiles: [],
    approvals: [],
    personas: [],
    assignments: []
  },
  null,
  2
)
const DETAIL_LOAD_ERROR = "Failed to load pack details."

const getVerdictColor = (verdict?: McpHubGovernancePackDryRunReport["verdict"]) => {
  if (verdict === "importable") return "green"
  if (verdict === "blocked") return "red"
  return "default"
}

const describeItems = (values: string[], emptyLabel: string) => {
  if (!values.length) {
    return <Typography.Text type="secondary">{emptyLabel}</Typography.Text>
  }
  return (
    <Space wrap>
      {values.map((value) => (
        <Tag key={value}>{value}</Tag>
      ))}
    </Space>
  )
}

export const GovernancePacksTab = () => {
  const [packs, setPacks] = useState<McpHubGovernancePackSummary[]>([])
  const [selectedPackId, setSelectedPackId] = useState<number | null>(null)
  const [selectedPack, setSelectedPack] = useState<McpHubGovernancePackDetail | null>(null)
  const [report, setReport] = useState<McpHubGovernancePackDryRunReport | null>(null)
  const [packJson, setPackJson] = useState(DEFAULT_PACK_JSON)
  const [loadingInventory, setLoadingInventory] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [importing, setImporting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const parsedPack = useMemo<McpHubGovernancePackDocument | null>(() => {
    try {
      const parsed = JSON.parse(packJson) as McpHubGovernancePackDocument
      return {
        manifest: parsed?.manifest ?? {},
        profiles: Array.isArray(parsed?.profiles) ? parsed.profiles : [],
        approvals: Array.isArray(parsed?.approvals) ? parsed.approvals : [],
        personas: Array.isArray(parsed?.personas) ? parsed.personas : [],
        assignments: Array.isArray(parsed?.assignments) ? parsed.assignments : []
      }
    } catch {
      return null
    }
  }, [packJson])

  const loadInventory = async () => {
    setLoadingInventory(true)
    setErrorMessage(null)
    try {
      const rows = await listGovernancePacks()
      const safeRows = Array.isArray(rows) ? rows : []
      setPacks(safeRows)
      setSelectedPackId((current) => {
        if (safeRows.some((row) => row.id === current)) {
          return current
        }
        return safeRows[0]?.id ?? null
      })
    } catch {
      setPacks([])
      setSelectedPackId(null)
      setSelectedPack(null)
      setErrorMessage("Failed to load governance packs.")
    } finally {
      setLoadingInventory(false)
    }
  }

  useEffect(() => {
    void loadInventory()
  }, [])

  useEffect(() => {
    let cancelled = false
    const loadDetail = async () => {
      if (!selectedPackId) {
        setSelectedPack(null)
        setErrorMessage((current) => (current === DETAIL_LOAD_ERROR ? null : current))
        return
      }
      setLoadingDetail(true)
      try {
        const detail = await getGovernancePackDetail(selectedPackId)
        if (!cancelled) {
          setSelectedPack(detail)
          setErrorMessage((current) => (current === DETAIL_LOAD_ERROR ? null : current))
        }
      } catch {
        if (!cancelled) {
          setSelectedPack(null)
          setErrorMessage(DETAIL_LOAD_ERROR)
        }
      } finally {
        if (!cancelled) {
          setLoadingDetail(false)
        }
      }
    }
    void loadDetail()
    return () => {
      cancelled = true
    }
  }, [selectedPackId])

  const handlePreview = async () => {
    setSuccessMessage(null)
    if (!parsedPack) {
      setErrorMessage("Governance pack JSON must be valid JSON.")
      setReport(null)
      return
    }
    setPreviewing(true)
    setErrorMessage(null)
    try {
      const response = await dryRunGovernancePack({
        owner_scope_type: "user",
        pack: parsedPack
      })
      setReport(response.report)
    } catch {
      setReport(null)
      setErrorMessage("Failed to preview governance pack compatibility.")
    } finally {
      setPreviewing(false)
    }
  }

  const handleImport = async () => {
    setSuccessMessage(null)
    if (!parsedPack) {
      setErrorMessage("Governance pack JSON must be valid JSON.")
      return
    }
    setImporting(true)
    setErrorMessage(null)
    try {
      const response = await importGovernancePack({
        owner_scope_type: "user",
        pack: parsedPack
      })
      setReport(response.report)
      setSelectedPackId(response.governance_pack_id)
      setSuccessMessage(`Imported ${response.report.manifest.title}.`)
      await loadInventory()
    } catch {
      setErrorMessage("Failed to import governance pack.")
    } finally {
      setImporting(false)
    }
  }

  const canImport = !importing && report?.verdict === "importable" && Boolean(parsedPack)

  return (
    <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Text type="secondary">
        Governance packs provide portable MCP Hub policy templates that can be previewed before import.
      </Typography.Text>
      {errorMessage ? <Alert type="error" title={errorMessage} showIcon /> : null}
      {successMessage ? <Alert type="success" title={successMessage} showIcon /> : null}

      <Space align="start" size="middle" style={{ width: "100%", justifyContent: "space-between" }}>
        <Card title="Installed Packs" style={{ flex: 1, minWidth: 320 }}>
          <List
            bordered
            loading={loadingInventory}
            dataSource={packs}
            locale={{ emptyText: <Empty description="No governance packs imported yet" /> }}
            renderItem={(pack) => (
              <List.Item
                style={{
                  cursor: "pointer",
                  borderColor: pack.id === selectedPackId ? "var(--ant-color-primary, #1677ff)" : undefined
                }}
                onClick={() => setSelectedPackId(pack.id)}
              >
                <Space orientation="vertical" size={4} style={{ width: "100%" }}>
                  <Space wrap>
                    <Typography.Text strong>{pack.title}</Typography.Text>
                    <Tag>{pack.owner_scope_type}</Tag>
                    <Tag color="blue">{`${pack.pack_id}@${pack.pack_version}`}</Tag>
                  </Space>
                  {pack.description ? (
                    <Typography.Text type="secondary">{pack.description}</Typography.Text>
                  ) : null}
                </Space>
              </List.Item>
            )}
          />
        </Card>

        <Card
          title="Pack Details"
          loading={loadingDetail}
          style={{ flex: 1, minWidth: 320 }}
        >
          {selectedPack ? (
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Pack">
                {`${selectedPack.pack_id}@${selectedPack.pack_version}`}
              </Descriptions.Item>
              <Descriptions.Item label="Digest">
                <Typography.Text code>{selectedPack.bundle_digest}</Typography.Text>
              </Descriptions.Item>
              <Descriptions.Item label="Imported Objects">
                {describeItems(
                  selectedPack.imported_objects.map(
                    (item) => `${item.object_type}:${item.source_object_id}`
                  ),
                  "No imported objects recorded."
                )}
              </Descriptions.Item>
            </Descriptions>
          ) : (
            <Empty description="Select a governance pack to inspect its imported objects." />
          )}
        </Card>
      </Space>

      <Card title="Preview Import">
        <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
          <Space orientation="vertical" size={4} style={{ width: "100%" }}>
            <label htmlFor="mcp-governance-pack-json">Governance Pack JSON</label>
            <Input.TextArea
              id="mcp-governance-pack-json"
              aria-label="Governance Pack JSON"
              value={packJson}
              rows={12}
              onChange={(event) => setPackJson(event.target.value)}
              spellCheck={false}
            />
          </Space>
          <Space>
            <Button type="primary" onClick={() => void handlePreview()} loading={previewing}>
              Preview Pack
            </Button>
            <Button onClick={() => void handleImport()} disabled={!canImport} loading={importing}>
              Import Pack
            </Button>
          </Space>
          {report ? (
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="Pack">{report.manifest.title}</Descriptions.Item>
              <Descriptions.Item label="Verdict">
                <Tag color={getVerdictColor(report.verdict)}>
                  {report.verdict === "importable" ? "Importable" : "Blocked"}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Resolved capabilities">
                {describeItems(report.resolved_capabilities, "None")}
              </Descriptions.Item>
              <Descriptions.Item label="Unresolved capabilities">
                {describeItems(report.unresolved_capabilities, "None")}
              </Descriptions.Item>
              <Descriptions.Item label="Warnings">
                {describeItems(report.warnings, "None")}
              </Descriptions.Item>
              <Descriptions.Item label="Blocked objects">
                {describeItems(report.blocked_objects, "None")}
              </Descriptions.Item>
            </Descriptions>
          ) : null}
        </Space>
      </Card>
    </Space>
  )
}
