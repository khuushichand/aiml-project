import React, { useState } from "react"
import { useTranslation } from "react-i18next"
import { Modal, Button, Checkbox, Tag, Progress } from "antd"
import {
  Shield,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  Wrench,
} from "lucide-react"
import { useACPSessionsStore } from "@/store/acp-sessions"
import { useACPSession } from "@/hooks/useACPSession"
import { UI_CONFIG } from "@/services/acp/constants"
import type { ACPPendingPermission, ACPPermissionTier } from "@/services/acp/types"

export const ACPPermissionModal: React.FC = () => {
  const { t } = useTranslation(["playground", "common"])

  const [batchApprove, setBatchApprove] = useState(false)

  // Store
  const activeSessionId = useACPSessionsStore((s) => s.activeSessionId)
  const activeSession = useACPSessionsStore((s) =>
    s.activeSessionId ? s.getSession(s.activeSessionId) : undefined
  )

  // WebSocket connection
  const { approvePermission, denyPermission } = useACPSession({
    sessionId: activeSessionId ?? undefined,
    autoConnect: false, // Already connected from chat panel
  })

  const pendingPermissions = activeSession?.pendingPermissions || []
  const currentPermission = pendingPermissions[0]

  if (!currentPermission) {
    return null
  }

  const handleApprove = () => {
    approvePermission(
      currentPermission.request_id,
      batchApprove ? currentPermission.tier : undefined
    )
    setBatchApprove(false)
  }

  const handleDeny = () => {
    denyPermission(currentPermission.request_id)
    setBatchApprove(false)
  }

  const getTierColor = (tier: ACPPermissionTier) => {
    return UI_CONFIG.TIER_COLORS[tier] || "default"
  }

  const getTierIcon = (tier: ACPPermissionTier) => {
    switch (tier) {
      case "auto":
        return <CheckCircle className="h-4 w-4" />
      case "batch":
        return <AlertTriangle className="h-4 w-4" />
      case "individual":
        return <Shield className="h-4 w-4" />
      default:
        return null
    }
  }

  // Calculate time remaining
  const timeElapsed = Date.now() - currentPermission.requestedAt.getTime()
  const timeRemaining = Math.max(0, currentPermission.timeout_seconds * 1000 - timeElapsed)
  const progressPercent = (timeRemaining / (currentPermission.timeout_seconds * 1000)) * 100

  return (
    <Modal
      open={true}
      closable={false}
      maskClosable={false}
      footer={null}
      width={500}
      centered
      className="acp-permission-modal"
    >
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-warning/10">
            <Shield className="h-5 w-5 text-warning" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-text">
              {t("playground:acp.permissionRequired", "Permission Required")}
            </h3>
            <p className="text-sm text-text-muted">
              {t("playground:acp.agentWantsTo", "The agent wants to execute a tool")}
            </p>
          </div>
        </div>

        {/* Queue indicator */}
        {pendingPermissions.length > 1 && (
          <div className="rounded-lg bg-info/10 px-3 py-2 text-sm text-info">
            {t("playground:acp.queuedPermissions", "{{count}} more permission requests queued", {
              count: pendingPermissions.length - 1,
            })}
          </div>
        )}

        {/* Tool info */}
        <div className="rounded-lg border border-border bg-surface2 p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Wrench className="h-4 w-4 text-text-muted" />
              <span className="font-mono text-sm font-medium text-text">
                {currentPermission.tool_name}
              </span>
            </div>
            <Tag
              color={getTierColor(currentPermission.tier)}
              className="flex items-center gap-1"
            >
              {getTierIcon(currentPermission.tier)}
              {UI_CONFIG.TIER_LABELS[currentPermission.tier]}
            </Tag>
          </div>

          {/* Tool arguments */}
          <div className="mb-3">
            <div className="mb-1 text-xs font-medium text-text-muted uppercase">
              {t("playground:acp.arguments", "Arguments")}
            </div>
            <div className="max-h-40 overflow-auto rounded bg-bg p-2">
              <pre className="text-xs text-text">
                {JSON.stringify(currentPermission.tool_arguments, null, 2)}
              </pre>
            </div>
          </div>

          {/* Tier description */}
          <div className="text-xs text-text-muted">
            {UI_CONFIG.TIER_DESCRIPTIONS[currentPermission.tier]}
          </div>
        </div>

        {/* Timeout progress */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs text-text-muted">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {t("playground:acp.timeRemaining", "Time remaining")}
            </span>
            <span>{Math.ceil(timeRemaining / 1000)}s</span>
          </div>
          <Progress
            percent={progressPercent}
            showInfo={false}
            strokeColor={progressPercent < 20 ? "#ef4444" : progressPercent < 50 ? "#f59e0b" : "#22c55e"}
            size="small"
          />
        </div>

        {/* Batch approve checkbox */}
        {currentPermission.tier !== "individual" && (
          <Checkbox
            checked={batchApprove}
            onChange={(e) => setBatchApprove(e.target.checked)}
          >
            <span className="text-sm text-text">
              {t(
                "playground:acp.batchApprove",
                "Auto-approve all future '{{tier}}' tier requests in this session",
                { tier: currentPermission.tier }
              )}
            </span>
          </Checkbox>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <Button
            danger
            icon={<XCircle className="h-4 w-4" />}
            onClick={handleDeny}
            className="flex-1"
          >
            {t("playground:acp.deny", "Deny")}
          </Button>
          <Button
            type="primary"
            icon={<CheckCircle className="h-4 w-4" />}
            onClick={handleApprove}
            className="flex-1"
          >
            {t("playground:acp.approve", "Approve")}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
