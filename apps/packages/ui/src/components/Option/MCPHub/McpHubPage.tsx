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
import {
  persistMcpHubExplainerDismissed,
  readMcpHubExplainerDismissed
} from "@/utils/ftux-storage"

export const McpHubPage = () => {
  const [activeTab, setActiveTab] = useState<McpHubGovernanceAuditTabKey>("tool-catalogs")
  const [explainerDismissed, setExplainerDismissed] = useState(
    () => readMcpHubExplainerDismissed()
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
    persistMcpHubExplainerDismissed()
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
            key: "tool-catalogs",
            label: <span data-testid="mcp-hub-tab-tool-catalogs">Tool Catalog</span>,
            children: <ToolCatalogsTab />
          },
          {
            key: "credentials",
            label: <span data-testid="mcp-hub-tab-credentials">Servers & Credentials</span>,
            children: (
              <ExternalServersTab
                drillTarget={drillTarget}
                onDrillHandled={handleDrillHandled}
              />
            )
          },
          {
            key: "profiles",
            label: <span data-testid="mcp-hub-tab-profiles">Profiles</span>,
            children: <PermissionProfilesTab />
          },
          {
            key: "assignments",
            label: <span data-testid="mcp-hub-tab-assignments">Assignments</span>,
            children: (
              <PolicyAssignmentsTab
                drillTarget={drillTarget}
                onDrillHandled={handleDrillHandled}
              />
            )
          },
          {
            key: "approvals",
            label: <span data-testid="mcp-hub-tab-approvals">Approvals</span>,
            children: <ApprovalPoliciesTab />
          },
          {
            key: "path-scopes",
            label: <span data-testid="mcp-hub-tab-path-scopes">Path Scopes</span>,
            children: <PathScopesTab />
          },
          {
            key: "capability-mappings",
            label: <span data-testid="mcp-hub-tab-capability-mappings">Capability Mappings</span>,
            children: <CapabilityMappingsTab />
          },
          {
            key: "workspace-sets",
            label: <span data-testid="mcp-hub-tab-workspace-sets">Workspace Sets</span>,
            children: (
              <WorkspaceSetsTab
                drillTarget={drillTarget}
                onDrillHandled={handleDrillHandled}
              />
            )
          },
          {
            key: "shared-workspaces",
            label: <span data-testid="mcp-hub-tab-shared-workspaces">Shared Workspaces</span>,
            children: (
              <SharedWorkspacesTab
                drillTarget={drillTarget}
                onDrillHandled={handleDrillHandled}
              />
            )
          },
          {
            key: "governance-packs",
            label: <span data-testid="mcp-hub-tab-governance-packs">Governance Packs</span>,
            children: <GovernancePacksTab />
          },
          {
            key: "audit",
            label: <span data-testid="mcp-hub-tab-audit">Audit</span>,
            children: <GovernanceAuditTab onOpen={handleOpen} />
          }
        ]}
      />
    </div>
  )
}
