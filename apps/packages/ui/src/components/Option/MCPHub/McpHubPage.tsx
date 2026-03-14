import { useRef, useState } from "react"
import { Tabs, Typography } from "antd"

import { ApprovalPoliciesTab } from "./ApprovalPoliciesTab"
import { GovernanceAuditTab } from "./GovernanceAuditTab"
import { GovernancePacksTab } from "./GovernancePacksTab"
import { PathScopesTab } from "./PathScopesTab"
import { PermissionProfilesTab } from "./PermissionProfilesTab"
import { PolicyAssignmentsTab } from "./PolicyAssignmentsTab"
import { SharedWorkspacesTab } from "./SharedWorkspacesTab"
import { ToolCatalogsTab } from "./ToolCatalogsTab"
import { ExternalServersTab } from "./ExternalServersTab"
import { WorkspaceSetsTab } from "./WorkspaceSetsTab"
import type {
  McpHubDrillAction,
  McpHubDrillTarget,
  McpHubGovernanceAuditNavigateTarget,
  McpHubGovernanceAuditTabKey
} from "@/services/tldw/mcp-hub"

export const McpHubPage = () => {
  const [activeTab, setActiveTab] = useState<McpHubGovernanceAuditTabKey>("profiles")
  const [drillTarget, setDrillTarget] = useState<McpHubDrillTarget | null>(null)
  const requestIdRef = useRef(0)

  const _deriveDrillAction = (
    target: McpHubGovernanceAuditNavigateTarget
  ): McpHubDrillAction => {
    if (
      target.tab === "assignments" ||
      target.tab === "workspace-sets" ||
      target.tab === "shared-workspaces" ||
      target.tab === "credentials"
    ) {
      return "edit"
    }
    return "focus"
  }

  const handleOpen = (target: McpHubGovernanceAuditNavigateTarget) => {
    requestIdRef.current += 1
    setDrillTarget({
      ...target,
      action: _deriveDrillAction(target),
      request_id: requestIdRef.current
    })
    setActiveTab(target.tab)
  }

  const handleDrillHandled = (requestId: number) => {
    setDrillTarget((current) => (current?.request_id === requestId ? null : current))
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 p-4">
      <Typography.Title level={3} style={{ margin: 0 }}>
        MCP Hub
      </Typography.Title>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: "profiles",
            label: "Profiles",
            children: <PermissionProfilesTab />
          },
          {
            key: "assignments",
            label: "Assignments",
            children: (
              <PolicyAssignmentsTab
                drillTarget={drillTarget}
                onDrillHandled={handleDrillHandled}
              />
            )
          },
          {
            key: "path-scopes",
            label: "Path Scopes",
            children: <PathScopesTab />
          },
          {
            key: "workspace-sets",
            label: "Workspace Sets",
            children: (
              <WorkspaceSetsTab
                drillTarget={drillTarget}
                onDrillHandled={handleDrillHandled}
              />
            )
          },
          {
            key: "shared-workspaces",
            label: "Shared Workspaces",
            children: (
              <SharedWorkspacesTab
                drillTarget={drillTarget}
                onDrillHandled={handleDrillHandled}
              />
            )
          },
          {
            key: "audit",
            label: "Audit",
            children: <GovernanceAuditTab onOpen={handleOpen} />
          },
          {
            key: "governance-packs",
            label: "Governance Packs",
            children: <GovernancePacksTab />
          },
          {
            key: "approvals",
            label: "Approvals",
            children: <ApprovalPoliciesTab />
          },
          {
            key: "tool-catalogs",
            label: "Catalog",
            children: <ToolCatalogsTab />
          },
          {
            key: "credentials",
            label: "Credentials",
            children: (
              <ExternalServersTab
                drillTarget={drillTarget}
                onDrillHandled={handleDrillHandled}
              />
            )
          }
        ]}
      />
    </div>
  )
}
