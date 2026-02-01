import React from "react"
import { useTranslation } from "react-i18next"
import { Button, Empty, Tag, Tooltip, Collapse } from "antd"
import {
  X,
  Wrench,
  FileText,
  Terminal,
  GitBranch,
  Search,
  FolderOpen,
  Shield,
  CheckCircle,
  AlertTriangle,
  XCircle,
} from "lucide-react"
import { useACPSessionsStore } from "@/store/acp-sessions"
import { TOOL_TIERS, UI_CONFIG } from "@/services/acp/constants"
import type { ACPPermissionTier } from "@/services/acp/types"

interface ACPToolsPanelProps {
  onHide?: () => void
}

export const ACPToolsPanel: React.FC<ACPToolsPanelProps> = ({ onHide }) => {
  const { t } = useTranslation(["playground", "option", "common"])

  // Store
  const activeSession = useACPSessionsStore((s) =>
    s.activeSessionId ? s.getSession(s.activeSessionId) : undefined
  )

  const capabilities = activeSession?.capabilities as {
    fs?: { readTextFile?: boolean; writeTextFile?: boolean }
    terminal?: boolean
    tools?: string[]
  } | undefined

  // Group tools by category
  const groupedTools = React.useMemo(() => {
    const tools = capabilities?.tools || Object.keys(TOOL_TIERS)
    const groups: Record<string, string[]> = {
      filesystem: [],
      search: [],
      git: [],
      execution: [],
      other: [],
    }

    for (const tool of tools) {
      const toolLower = tool.toLowerCase()
      if (toolLower.startsWith("fs.") || toolLower.includes("file")) {
        groups.filesystem.push(tool)
      } else if (toolLower.startsWith("search.") || toolLower.includes("grep") || toolLower.includes("glob")) {
        groups.search.push(tool)
      } else if (toolLower.startsWith("git.")) {
        groups.git.push(tool)
      } else if (toolLower.startsWith("exec.") || toolLower.includes("terminal") || toolLower.includes("bash")) {
        groups.execution.push(tool)
      } else {
        groups.other.push(tool)
      }
    }

    return groups
  }, [capabilities?.tools])

  const getTierColor = (tier: ACPPermissionTier) => {
    switch (tier) {
      case "auto":
        return "success"
      case "batch":
        return "warning"
      case "individual":
        return "error"
      default:
        return "default"
    }
  }

  const getTierIcon = (tier: ACPPermissionTier) => {
    switch (tier) {
      case "auto":
        return <CheckCircle className="h-3 w-3" />
      case "batch":
        return <AlertTriangle className="h-3 w-3" />
      case "individual":
        return <XCircle className="h-3 w-3" />
      default:
        return null
    }
  }

  const getGroupIcon = (group: string) => {
    switch (group) {
      case "filesystem":
        return <FolderOpen className="h-4 w-4" />
      case "search":
        return <Search className="h-4 w-4" />
      case "git":
        return <GitBranch className="h-4 w-4" />
      case "execution":
        return <Terminal className="h-4 w-4" />
      default:
        return <Wrench className="h-4 w-4" />
    }
  }

  const getGroupLabel = (group: string) => {
    switch (group) {
      case "filesystem":
        return t("playground:acp.toolGroups.filesystem", "File System")
      case "search":
        return t("playground:acp.toolGroups.search", "Search")
      case "git":
        return t("playground:acp.toolGroups.git", "Git")
      case "execution":
        return t("playground:acp.toolGroups.execution", "Execution")
      default:
        return t("playground:acp.toolGroups.other", "Other")
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border p-3">
        <h2 className="text-sm font-semibold text-text">
          {t("playground:acp.toolsCapabilities", "Tools & Capabilities")}
        </h2>
        {onHide && (
          <Tooltip title={t("common:close", "Close")}>
            <Button
              type="text"
              size="small"
              icon={<X className="h-4 w-4" />}
              onClick={onHide}
            />
          </Tooltip>
        )}
      </div>

      {/* Content */}
      <div className="custom-scrollbar flex-1 overflow-y-auto">
        {!activeSession ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={t("playground:acp.selectSession", "Select a session to view capabilities")}
            className="py-8"
          />
        ) : (
          <div className="p-3 space-y-4">
            {/* Capabilities summary */}
            <div className="rounded-lg bg-surface2 p-3">
              <div className="mb-2 text-xs font-medium text-text-muted uppercase">
                {t("playground:acp.capabilities", "Capabilities")}
              </div>
              <div className="flex flex-wrap gap-2">
                <CapabilityBadge
                  icon={<FileText className="h-3 w-3" />}
                  label={t("playground:acp.fsRead", "Read Files")}
                  enabled={capabilities?.fs?.readTextFile !== false}
                />
                <CapabilityBadge
                  icon={<FileText className="h-3 w-3" />}
                  label={t("playground:acp.fsWrite", "Write Files")}
                  enabled={capabilities?.fs?.writeTextFile !== false}
                />
                <CapabilityBadge
                  icon={<Terminal className="h-3 w-3" />}
                  label={t("playground:acp.terminal", "Terminal")}
                  enabled={capabilities?.terminal !== false}
                />
              </div>
            </div>

            {/* Permission tiers legend */}
            <div className="rounded-lg bg-surface2 p-3">
              <div className="mb-2 text-xs font-medium text-text-muted uppercase">
                {t("playground:acp.permissionTiers", "Permission Tiers")}
              </div>
              <div className="space-y-2">
                <TierLegendItem
                  tier="auto"
                  label={UI_CONFIG.TIER_LABELS.auto}
                  description={UI_CONFIG.TIER_DESCRIPTIONS.auto}
                />
                <TierLegendItem
                  tier="batch"
                  label={UI_CONFIG.TIER_LABELS.batch}
                  description={UI_CONFIG.TIER_DESCRIPTIONS.batch}
                />
                <TierLegendItem
                  tier="individual"
                  label={UI_CONFIG.TIER_LABELS.individual}
                  description={UI_CONFIG.TIER_DESCRIPTIONS.individual}
                />
              </div>
            </div>

            {/* Tools by group */}
            <div>
              <div className="mb-2 text-xs font-medium text-text-muted uppercase">
                {t("playground:acp.availableTools", "Available Tools")}
              </div>
              <Collapse
                ghost
                defaultActiveKey={["filesystem"]}
                items={Object.entries(groupedTools)
                  .filter(([, tools]) => tools.length > 0)
                  .map(([group, tools]) => ({
                    key: group,
                    label: (
                      <div className="flex items-center gap-2">
                        {getGroupIcon(group)}
                        <span>{getGroupLabel(group)}</span>
                        <span className="text-xs text-text-muted">({tools.length})</span>
                      </div>
                    ),
                    children: (
                      <div className="space-y-1">
                        {tools.map((tool) => {
                          const tier = (TOOL_TIERS[tool] || "batch") as ACPPermissionTier
                          return (
                            <div
                              key={tool}
                              className="flex items-center justify-between rounded px-2 py-1 hover:bg-surface2"
                            >
                              <span className="text-sm text-text">{tool}</span>
                              <Tag color={getTierColor(tier)} className="flex items-center gap-1">
                                {getTierIcon(tier)}
                                <span className="text-xs">{tier}</span>
                              </Tag>
                            </div>
                          )
                        })}
                      </div>
                    ),
                  }))}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

interface CapabilityBadgeProps {
  icon: React.ReactNode
  label: string
  enabled: boolean
}

const CapabilityBadge: React.FC<CapabilityBadgeProps> = ({ icon, label, enabled }) => (
  <div
    className={`flex items-center gap-1.5 rounded-full px-2 py-1 text-xs ${
      enabled
        ? "bg-success/10 text-success"
        : "bg-text-muted/10 text-text-muted"
    }`}
  >
    {icon}
    <span>{label}</span>
    {enabled ? (
      <CheckCircle className="h-3 w-3" />
    ) : (
      <XCircle className="h-3 w-3" />
    )}
  </div>
)

interface TierLegendItemProps {
  tier: ACPPermissionTier
  label: string
  description: string
}

const TierLegendItem: React.FC<TierLegendItemProps> = ({ tier, label, description }) => {
  const getColor = () => {
    switch (tier) {
      case "auto":
        return "text-success"
      case "batch":
        return "text-warning"
      case "individual":
        return "text-error"
      default:
        return "text-text-muted"
    }
  }

  const getIcon = () => {
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

  return (
    <div className="flex items-start gap-2">
      <div className={`shrink-0 ${getColor()}`}>{getIcon()}</div>
      <div className="min-w-0">
        <div className={`text-sm font-medium ${getColor()}`}>{label}</div>
        <div className="text-xs text-text-muted">{description}</div>
      </div>
    </div>
  )
}
