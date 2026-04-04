import { useRef, useState } from "react"
import { Alert, Tabs, Typography } from "antd"

import { ApprovalPoliciesTab } from "./ApprovalPoliciesTab"
import { CapabilityMappingsTab } from "./CapabilityMappingsTab"
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

const EXPLAINER_DISMISSED_KEY = "tldw_mcp_hub_explainer_dismissed"

export const McpHubPage = () => {
  const [activeTab, setActiveTab] = useState<McpHubGovernanceAuditTabKey>("tool-catalogs")
  const [explainerDismissed, setExplainerDismissed] = useState(
    () => localStorage.getItem(EXPLAINER_DISMISSED_KEY) === "true"
  )
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

  const handleExplainerClose = () => {
    setExplainerDismissed(true)
    localStorage.setItem(EXPLAINER_DISMISSED_KEY, "true")
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 p-4" data-testid="mcp-hub-shell">
      <Typography.Title level={3} style={{ margin: 0 }}>
        MCP Hub
      </Typography.Title>
      <Typography.Text type="secondary">
        Manage external tool servers and governance policies for the Model Context Protocol (MCP).
      </Typography.Text>
      {!explainerDismissed && (
        <Alert
          data-testid="mcp-hub-explainer"
          type="info"
          showIcon
          closable
          onClose={handleExplainerClose}
          title="Getting Started with MCP Hub"
          description="MCP Hub lets you connect external tool servers, manage permissions, and govern how AI models interact with outside services. Start by browsing the Tool Catalog to discover available tools, then set up Profiles and Credentials to configure access."
        />
      )}
      <Tabs
        data-testid="mcp-hub-tabs"
        activeKey={activeTab}
        onChange={(activeKey) =>
          setActiveTab(activeKey as McpHubGovernanceAuditTabKey)
        }
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
            key: "capability-mappings",
            label: "Capability Mappings",
            children: <CapabilityMappingsTab />
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
