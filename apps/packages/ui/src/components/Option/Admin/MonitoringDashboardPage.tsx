import React, { useState, useRef, useCallback, useEffect } from "react"
import {
  Card,
  Table,
  Button,
  Input,
  InputNumber,
  Form,
  Tag,
  Space,
  Alert,
  Select,
  Popconfirm,
  message
} from "antd"
import {
  deriveAdminGuardFromError,
  sanitizeAdminErrorMessage
} from "./admin-error-utils"
import { CollapsibleSection } from "./CollapsibleSection"
import { tldwClient } from "@/services/tldw/TldwApiClient"

const MonitoringDashboardPage: React.FC = () => {
  // Admin guard state
  const [adminGuard, setAdminGuard] = useState<"forbidden" | "notFound" | null>(null)

  // System overview state
  const [systemStats, setSystemStats] = useState<any>(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [securityStatus, setSecurityStatus] = useState<any>(null)
  const [securityLoading, setSecurityLoading] = useState(false)

  // Alert rules state
  const [alertRules, setAlertRules] = useState<any[]>([])
  const [rulesLoading, setRulesLoading] = useState(false)
  const [ruleForm] = Form.useForm()
  const [creatingRule, setCreatingRule] = useState(false)

  // Alert history state
  const [alertHistory, setAlertHistory] = useState<any[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  // Activity state
  const [activity, setActivity] = useState<any>(null)
  const [activityLoading, setActivityLoading] = useState(false)

  const initialLoadRef = useRef(false)

  const markAdminGuardFromError = useCallback((err: any) => {
    const guardState = deriveAdminGuardFromError(err)
    if (guardState) setAdminGuard(guardState)
  }, [])

  // ── System Overview ──

  const loadSystemStats = useCallback(async () => {
    setStatsLoading(true)
    try {
      const stats = await tldwClient.getSystemStats()
      setSystemStats(stats)
    } catch (err) {
      markAdminGuardFromError(err)
    } finally {
      setStatsLoading(false)
    }
  }, [markAdminGuardFromError])

  const loadSecurityStatus = useCallback(async () => {
    setSecurityLoading(true)
    try {
      const status = await tldwClient.getSecurityAlertStatus()
      setSecurityStatus(status)
    } catch (err) {
      markAdminGuardFromError(err)
    } finally {
      setSecurityLoading(false)
    }
  }, [markAdminGuardFromError])

  // ── Alert Rules ──

  const loadAlertRules = useCallback(async () => {
    setRulesLoading(true)
    try {
      const result = await tldwClient.listAlertRules()
      setAlertRules(Array.isArray(result) ? result : [])
    } catch (err) {
      markAdminGuardFromError(err)
    } finally {
      setRulesLoading(false)
    }
  }, [markAdminGuardFromError])

  const handleCreateRule = async () => {
    try {
      const values = await ruleForm.validateFields()
      setCreatingRule(true)
      await tldwClient.createAlertRule({
        metric: values.metric.trim(),
        operator: values.operator,
        threshold: values.threshold,
        duration_minutes: values.duration_minutes || undefined,
        severity: values.severity || undefined
      })
      ruleForm.resetFields()
      message.success("Alert rule created")
      await loadAlertRules()
    } catch (err: any) {
      if (err?.errorFields) return
      message.error(sanitizeAdminErrorMessage(err, "Failed to create alert rule"))
    } finally {
      setCreatingRule(false)
    }
  }

  const handleDeleteRule = async (ruleId: number) => {
    try {
      await tldwClient.deleteAlertRule(ruleId)
      message.success("Alert rule deleted")
      await loadAlertRules()
    } catch (err: any) {
      message.error(sanitizeAdminErrorMessage(err, "Failed to delete alert rule"))
    }
  }

  // ── Alert History ──

  const loadAlertHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const result = await tldwClient.listAlertHistory()
      setAlertHistory(Array.isArray(result) ? result : [])
    } catch (err) {
      markAdminGuardFromError(err)
    } finally {
      setHistoryLoading(false)
    }
  }, [markAdminGuardFromError])

  const handleAssignAlert = async (alertId: string, userId: number | null) => {
    try {
      await tldwClient.assignAlert(alertId, { user_id: userId })
      message.success("Alert assigned")
      await loadAlertHistory()
    } catch (err: any) {
      message.error(sanitizeAdminErrorMessage(err, "Failed to assign alert"))
    }
  }

  const handleSnoozeAlert = async (alertId: string, until: string) => {
    try {
      await tldwClient.snoozeAlert(alertId, { until })
      message.success("Alert snoozed")
      await loadAlertHistory()
    } catch (err: any) {
      message.error(sanitizeAdminErrorMessage(err, "Failed to snooze alert"))
    }
  }

  const handleEscalateAlert = async (alertId: string) => {
    try {
      await tldwClient.escalateAlert(alertId)
      message.success("Alert escalated")
      await loadAlertHistory()
    } catch (err: any) {
      message.error(sanitizeAdminErrorMessage(err, "Failed to escalate alert"))
    }
  }

  // ── Activity ──

  const loadActivity = useCallback(async () => {
    setActivityLoading(true)
    try {
      const result = await tldwClient.getDashboardActivity({ days: 7 })
      setActivity(result)
    } catch (err) {
      markAdminGuardFromError(err)
    } finally {
      setActivityLoading(false)
    }
  }, [markAdminGuardFromError])

  // ── Initial Load ──

  useEffect(() => {
    if (initialLoadRef.current) return
    initialLoadRef.current = true
    void loadSystemStats()
    void loadSecurityStatus()
    void loadAlertRules()
    void loadAlertHistory()
    void loadActivity()
  }, [loadSystemStats, loadSecurityStatus, loadAlertRules, loadAlertHistory, loadActivity])

  // ── Alert Rules Table Columns ──

  const ruleColumns = [
    {
      title: "Metric",
      dataIndex: "metric",
      key: "metric",
      render: (metric: string) => <code>{metric}</code>
    },
    {
      title: "Operator",
      dataIndex: "operator",
      key: "operator"
    },
    {
      title: "Threshold",
      dataIndex: "threshold",
      key: "threshold"
    },
    {
      title: "Duration (min)",
      dataIndex: "duration_minutes",
      key: "duration_minutes",
      render: (val: number | null) => val ?? "\u2014"
    },
    {
      title: "Severity",
      dataIndex: "severity",
      key: "severity",
      render: (severity: string) => {
        const color = severity === "critical" ? "red" : severity === "high" ? "orange" : severity === "medium" ? "gold" : "default"
        return <Tag color={color}>{severity || "low"}</Tag>
      }
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: any, record: any) => (
        <Popconfirm
          title="Delete this alert rule?"
          onConfirm={() => handleDeleteRule(record.id)}
        >
          <Button size="small" danger>Delete</Button>
        </Popconfirm>
      )
    }
  ]

  // ── Alert History Table Columns ──

  const historyColumns = [
    {
      title: "Alert",
      dataIndex: "alert",
      key: "alert",
      render: (alert: string, record: any) => alert || record.metric || record.id || "\u2014"
    },
    {
      title: "Severity",
      dataIndex: "severity",
      key: "severity",
      render: (severity: string) => {
        const color = severity === "critical" ? "red" : severity === "high" ? "orange" : severity === "medium" ? "gold" : "default"
        return <Tag color={color}>{severity || "low"}</Tag>
      }
    },
    {
      title: "Time",
      dataIndex: "triggered_at",
      key: "triggered_at",
      render: (val: string) => val ? new Date(val).toLocaleString() : "\u2014"
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status: string) => {
        const color = status === "resolved" ? "green" : status === "snoozed" ? "blue" : status === "escalated" ? "red" : "orange"
        return <Tag color={color}>{status || "active"}</Tag>
      }
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: any, record: any) => {
        const identity = String(record.id ?? record.alert ?? "")
        return (
          <Space size="small">
            <Popconfirm
              title="Assign this alert?"
              description="This will assign the alert to you (or unassign)."
              onConfirm={() => handleAssignAlert(identity, 1)}
            >
              <Button size="small">Assign</Button>
            </Popconfirm>
            <Popconfirm
              title="Snooze for 1 hour?"
              onConfirm={() => {
                const until = new Date(Date.now() + 60 * 60 * 1000).toISOString()
                handleSnoozeAlert(identity, until)
              }}
            >
              <Button size="small">Snooze</Button>
            </Popconfirm>
            <Popconfirm
              title="Escalate this alert?"
              onConfirm={() => handleEscalateAlert(identity)}
            >
              <Button size="small" danger>Escalate</Button>
            </Popconfirm>
          </Space>
        )
      }
    }
  ]

  // ── Render ──

  if (adminGuard === "forbidden") {
    return <Alert type="error" message="Access Denied" description="You don't have permission to access the monitoring dashboard." showIcon />
  }
  if (adminGuard === "notFound") {
    return <Alert type="warning" message="Not Available" description="The monitoring dashboard is not available on this server." showIcon />
  }

  const activityEntries = Array.isArray(activity?.entries)
    ? activity.entries
    : Array.isArray(activity)
      ? activity
      : []

  return (
    <div style={{ padding: "24px", maxWidth: 1200 }}>
      <h2 style={{ marginBottom: 16 }}>Monitoring &amp; Alerting</h2>

      {/* System Overview Card */}
      <Card
        title="System Overview"
        loading={statsLoading || securityLoading}
        style={{ marginBottom: 16 }}
        extra={
          <Button size="small" onClick={() => { void loadSystemStats(); void loadSecurityStatus() }}>
            Refresh
          </Button>
        }
      >
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          {systemStats && (
            <div>
              <strong>System Stats:</strong>
              <Table
                dataSource={Object.entries(systemStats).map(([key, value]) => ({
                  key,
                  stat: key,
                  value: typeof value === "object" ? JSON.stringify(value) : String(value ?? "\u2014")
                }))}
                columns={[
                  { title: "Stat", dataIndex: "stat", key: "stat" },
                  { title: "Value", dataIndex: "value", key: "value" }
                ]}
                rowKey="key"
                pagination={false}
                size="small"
              />
            </div>
          )}
          {securityStatus && (
            <div>
              <strong>Security Alert Status:</strong>
              <Table
                dataSource={Object.entries(securityStatus).map(([key, value]) => ({
                  key,
                  field: key,
                  value: typeof value === "object" ? JSON.stringify(value) : String(value ?? "\u2014")
                }))}
                columns={[
                  { title: "Field", dataIndex: "field", key: "field" },
                  { title: "Value", dataIndex: "value", key: "value" }
                ]}
                rowKey="key"
                pagination={false}
                size="small"
              />
            </div>
          )}
          {!systemStats && !securityStatus && !statsLoading && !securityLoading && (
            <Alert type="info" message="No system data available yet." showIcon />
          )}
        </Space>
      </Card>

      {/* Alert Rules Card */}
      <Card
        title="Alert Rules"
        style={{ marginBottom: 16 }}
        extra={
          <Button onClick={() => loadAlertRules()} size="small">
            Refresh
          </Button>
        }
      >
        <div style={{ marginBottom: 16 }}>
          <Form form={ruleForm} layout="inline">
            <Form.Item
              name="metric"
              rules={[{ required: true, message: "Metric is required" }]}
            >
              <Input placeholder="Metric name" style={{ width: 160 }} />
            </Form.Item>
            <Form.Item
              name="operator"
              rules={[{ required: true, message: "Operator is required" }]}
            >
              <Select
                placeholder="Operator"
                style={{ width: 100 }}
                options={[
                  { value: ">", label: ">" },
                  { value: ">=", label: ">=" },
                  { value: "<", label: "<" },
                  { value: "<=", label: "<=" },
                  { value: "==", label: "==" }
                ]}
              />
            </Form.Item>
            <Form.Item
              name="threshold"
              rules={[{ required: true, message: "Threshold is required" }]}
            >
              <InputNumber placeholder="Threshold" style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="duration_minutes">
              <InputNumber placeholder="Duration (min)" style={{ width: 130 }} min={1} />
            </Form.Item>
            <Form.Item name="severity">
              <Select
                placeholder="Severity"
                style={{ width: 120 }}
                allowClear
                options={[
                  { value: "low", label: "Low" },
                  { value: "medium", label: "Medium" },
                  { value: "high", label: "High" },
                  { value: "critical", label: "Critical" }
                ]}
              />
            </Form.Item>
            <Form.Item>
              <Button type="primary" onClick={handleCreateRule} loading={creatingRule}>
                Create Rule
              </Button>
            </Form.Item>
          </Form>
        </div>
        <Table
          dataSource={alertRules}
          columns={ruleColumns}
          rowKey="id"
          loading={rulesLoading}
          pagination={false}
          size="small"
        />
      </Card>

      {/* Alert History Card */}
      <Card
        title="Alert History"
        style={{ marginBottom: 16 }}
        extra={
          <Button onClick={() => loadAlertHistory()} size="small">
            Refresh
          </Button>
        }
      >
        <Table
          dataSource={alertHistory}
          columns={historyColumns}
          rowKey={(record) => String(record.id ?? record.alert ?? Math.random())}
          loading={historyLoading}
          pagination={{ pageSize: 20 }}
          size="small"
        />
      </Card>

      {/* Activity (Collapsible) */}
      <CollapsibleSection title="Recent Activity" description="Dashboard activity over the last 7 days">
        {activityLoading ? (
          <Card loading={true} />
        ) : activityEntries.length > 0 ? (
          <Table
            dataSource={activityEntries.map((entry: any, idx: number) => ({ ...entry, _key: idx }))}
            columns={[
              {
                title: "Time",
                dataIndex: "timestamp",
                key: "timestamp",
                render: (val: string) => val ? new Date(val).toLocaleString() : "\u2014"
              },
              {
                title: "Action",
                dataIndex: "action",
                key: "action"
              },
              {
                title: "User",
                dataIndex: "user",
                key: "user",
                render: (val: string) => val || "\u2014"
              },
              {
                title: "Details",
                dataIndex: "details",
                key: "details",
                render: (val: any) => typeof val === "object" ? JSON.stringify(val) : String(val ?? "\u2014")
              }
            ]}
            rowKey="_key"
            pagination={false}
            size="small"
          />
        ) : (
          <Alert type="info" message="No recent activity data available." showIcon />
        )}
      </CollapsibleSection>
    </div>
  )
}

export default MonitoringDashboardPage
