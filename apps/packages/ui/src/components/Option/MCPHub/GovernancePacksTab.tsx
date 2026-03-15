import { useEffect, useMemo, useState } from "react"
import { Alert, Button, Card, Descriptions, Empty, Input, List, Modal, Space, Tag, Typography } from "antd"

import {
  dryRunGovernancePack,
  dryRunGovernancePackUpgrade,
  executeGovernancePackUpgrade,
  getGovernancePackDetail,
  importGovernancePack,
  listGovernancePackUpgradeHistory,
  listGovernancePacks,
  type McpHubGovernancePackDetail,
  type McpHubGovernancePackDocument,
  type McpHubGovernancePackDryRunReport,
  type McpHubGovernancePackUpgradeHistoryEntry,
  type McpHubGovernancePackUpgradeObjectDiff,
  type McpHubGovernancePackUpgradePlan,
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

const getInstallStateTag = (pack: Pick<McpHubGovernancePackSummary, "is_active_install">) =>
  pack.is_active_install ? (
    <Tag color="green">Active install</Tag>
  ) : (
    <Tag color="default">Inactive install</Tag>
  )

const describeUpgradeDiffs = (diffs: McpHubGovernancePackUpgradeObjectDiff[]) =>
  diffs.map((diff) => `${diff.object_type}:${diff.source_object_id}`)

export const GovernancePacksTab = () => {
  const [packs, setPacks] = useState<McpHubGovernancePackSummary[]>([])
  const [selectedPackId, setSelectedPackId] = useState<number | null>(null)
  const [selectedPack, setSelectedPack] = useState<McpHubGovernancePackDetail | null>(null)
  const [upgradeHistory, setUpgradeHistory] = useState<McpHubGovernancePackUpgradeHistoryEntry[]>([])
  const [report, setReport] = useState<McpHubGovernancePackDryRunReport | null>(null)
  const [upgradePlan, setUpgradePlan] = useState<McpHubGovernancePackUpgradePlan | null>(null)
  const [packJson, setPackJson] = useState(DEFAULT_PACK_JSON)
  const [loadingInventory, setLoadingInventory] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [previewingUpgrade, setPreviewingUpgrade] = useState(false)
  const [importing, setImporting] = useState(false)
  const [executingUpgrade, setExecutingUpgrade] = useState(false)
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false)
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
      setUpgradeHistory([])
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
        setUpgradeHistory([])
        setErrorMessage((current) => (current === DETAIL_LOAD_ERROR ? null : current))
        return
      }
      setLoadingDetail(true)
      setLoadingHistory(true)
      try {
        const [detail, history] = await Promise.all([
          getGovernancePackDetail(selectedPackId),
          listGovernancePackUpgradeHistory(selectedPackId)
        ])
        if (!cancelled) {
          setSelectedPack(detail)
          setUpgradeHistory(Array.isArray(history) ? history : [])
          setErrorMessage((current) => (current === DETAIL_LOAD_ERROR ? null : current))
        }
      } catch {
        if (!cancelled) {
          setSelectedPack(null)
          setUpgradeHistory([])
          setErrorMessage(DETAIL_LOAD_ERROR)
        }
      } finally {
        if (!cancelled) {
          setLoadingDetail(false)
          setLoadingHistory(false)
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

  const handlePreviewUpgrade = async () => {
    setSuccessMessage(null)
    if (!selectedPackId) {
      setErrorMessage("Select an installed governance pack before previewing an upgrade.")
      setUpgradePlan(null)
      return
    }
    if (!parsedPack) {
      setErrorMessage("Governance pack JSON must be valid JSON.")
      setUpgradePlan(null)
      return
    }
    setUpgradeModalOpen(true)
    setPreviewingUpgrade(true)
    setErrorMessage(null)
    try {
      const response = await dryRunGovernancePackUpgrade({
        source_governance_pack_id: selectedPackId,
        owner_scope_type: "user",
        pack: parsedPack
      })
      setUpgradePlan(response.plan)
    } catch {
      setUpgradePlan(null)
      setUpgradeModalOpen(false)
      setErrorMessage("Failed to preview governance pack upgrade.")
    } finally {
      setPreviewingUpgrade(false)
    }
  }

  const handleExecuteUpgrade = async () => {
    setSuccessMessage(null)
    if (!selectedPackId || !parsedPack || !upgradePlan) {
      return
    }
    setExecutingUpgrade(true)
    setErrorMessage(null)
    try {
      const response = await executeGovernancePackUpgrade({
        source_governance_pack_id: selectedPackId,
        owner_scope_type: "user",
        planner_inputs_fingerprint: upgradePlan.planner_inputs_fingerprint,
        adapter_state_fingerprint: upgradePlan.adapter_state_fingerprint,
        pack: parsedPack
      })
      setUpgradeModalOpen(false)
      setUpgradePlan(null)
      setSelectedPackId(response.target_governance_pack_id)
      setSuccessMessage(
        `Executed upgrade ${response.from_pack_version} -> ${response.to_pack_version}.`
      )
      await loadInventory()
    } catch {
      setErrorMessage("Failed to execute governance pack upgrade.")
    } finally {
      setExecutingUpgrade(false)
    }
  }

  const canImport = !importing && report?.verdict === "importable" && Boolean(parsedPack)
  const addedDiffs = useMemo(
    () => (upgradePlan?.object_diff ?? []).filter((diff) => diff.change_type === "added"),
    [upgradePlan]
  )
  const modifiedDiffs = useMemo(
    () => (upgradePlan?.object_diff ?? []).filter((diff) => diff.change_type === "modified"),
    [upgradePlan]
  )
  const removedDiffs = useMemo(
    () => (upgradePlan?.object_diff ?? []).filter((diff) => diff.change_type === "removed"),
    [upgradePlan]
  )
  const blockingConflicts = useMemo(
    () => [...(upgradePlan?.structural_conflicts ?? []), ...(upgradePlan?.behavioral_conflicts ?? [])],
    [upgradePlan]
  )
  const canExecuteUpgrade =
    Boolean(parsedPack) &&
    Boolean(selectedPackId) &&
    Boolean(upgradePlan?.upgradeable) &&
    !executingUpgrade

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
                    {getInstallStateTag(pack)}
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
          loading={loadingDetail || loadingHistory}
          style={{ flex: 1, minWidth: 320 }}
        >
          {selectedPack ? (
            <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
              <Descriptions column={1} size="small">
                <Descriptions.Item label="Pack">
                  {`${selectedPack.pack_id}@${selectedPack.pack_version}`}
                </Descriptions.Item>
                <Descriptions.Item label="Install state">
                  {getInstallStateTag(selectedPack)}
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

              <div>
                <Typography.Title level={5} style={{ marginTop: 0 }}>
                  Upgrade History
                </Typography.Title>
                <List
                  size="small"
                  bordered
                  dataSource={upgradeHistory}
                  locale={{ emptyText: <Empty description="No upgrade history recorded." /> }}
                  renderItem={(entry) => (
                    <List.Item>
                      <Space orientation="vertical" size={2} style={{ width: "100%" }}>
                        <Space wrap>
                          <Typography.Text strong>{`${entry.from_pack_version} -> ${entry.to_pack_version}`}</Typography.Text>
                          <Tag color={entry.status === "executed" ? "green" : "default"}>
                            {entry.status}
                          </Tag>
                        </Space>
                        <Typography.Text type="secondary">
                          {`Object diffs: ${String(entry.plan_summary.object_diff_count ?? 0)}, dependency impacts: ${String(entry.plan_summary.dependency_impact_count ?? 0)}`}
                        </Typography.Text>
                      </Space>
                    </List.Item>
                  )}
                />
              </div>
            </Space>
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
            <Button
              onClick={() => void handlePreviewUpgrade()}
              disabled={!selectedPackId || !parsedPack}
              loading={previewingUpgrade}
            >
              Preview Upgrade
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

      <Modal
        title="Governance Pack Upgrade"
        open={upgradeModalOpen}
        onCancel={() => {
          setUpgradeModalOpen(false)
          setUpgradePlan(null)
        }}
        onOk={() => void handleExecuteUpgrade()}
        okText="Execute Upgrade"
        okButtonProps={{ disabled: !canExecuteUpgrade }}
        confirmLoading={executingUpgrade}
      >
        {upgradePlan ? (
          <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="Source pack">
                {String(upgradePlan.source_manifest.pack_version ?? "")}
              </Descriptions.Item>
              <Descriptions.Item label="Target pack">
                {String(upgradePlan.target_manifest.pack_version ?? "")}
              </Descriptions.Item>
              <Descriptions.Item label="Upgradeable">
                <Tag color={upgradePlan.upgradeable ? "green" : "red"}>
                  {upgradePlan.upgradeable ? "Ready to execute" : "Blocked"}
                </Tag>
              </Descriptions.Item>
            </Descriptions>

            {modifiedDiffs.length ? (
              <div>
                <Typography.Title level={5}>Modified objects</Typography.Title>
                {describeItems(describeUpgradeDiffs(modifiedDiffs), "None")}
              </div>
            ) : null}
            {addedDiffs.length ? (
              <div>
                <Typography.Title level={5}>Added objects</Typography.Title>
                {describeItems(describeUpgradeDiffs(addedDiffs), "None")}
              </div>
            ) : null}
            {removedDiffs.length ? (
              <div>
                <Typography.Title level={5}>Removed objects</Typography.Title>
                {describeItems(describeUpgradeDiffs(removedDiffs), "None")}
              </div>
            ) : null}
            {!upgradePlan.object_diff.length ? (
              <Typography.Text type="secondary">No runtime object changes detected.</Typography.Text>
            ) : null}

            {blockingConflicts.length ? (
              <div>
                <Typography.Title level={5}>Blocking conflicts</Typography.Title>
                {describeItems(blockingConflicts, "None")}
              </div>
            ) : null}
            {upgradePlan.warnings.length ? (
              <div>
                <Typography.Title level={5}>Warnings</Typography.Title>
                {describeItems(upgradePlan.warnings, "None")}
              </div>
            ) : null}
            {upgradePlan.dependency_impact.length ? (
              <div>
                <Typography.Title level={5}>Dependency impacts</Typography.Title>
                {describeItems(
                  upgradePlan.dependency_impact.map(
                    (impact) =>
                      `${impact.dependent_type}:${impact.dependent_id} via ${impact.reference_field}`
                  ),
                  "None"
                )}
              </div>
            ) : null}
          </Space>
        ) : (
          <Typography.Text type="secondary">
            {previewingUpgrade ? "Loading upgrade preview..." : "Run an upgrade dry-run to inspect the plan."}
          </Typography.Text>
        )}
      </Modal>
    </Space>
  )
}
