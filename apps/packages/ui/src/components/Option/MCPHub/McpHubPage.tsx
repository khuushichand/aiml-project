import { useState } from "react"
import { Tabs, Typography } from "antd"

import { ApprovalPoliciesTab } from "./ApprovalPoliciesTab"
import { PermissionProfilesTab } from "./PermissionProfilesTab"
import { PolicyAssignmentsTab } from "./PolicyAssignmentsTab"
import { ToolCatalogsTab } from "./ToolCatalogsTab"
import { ExternalServersTab } from "./ExternalServersTab"

export const McpHubPage = () => {
  const [activeTab, setActiveTab] = useState("profiles")

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
            children: <PolicyAssignmentsTab />
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
            children: <ExternalServersTab />
          }
        ]}
      />
    </div>
  )
}
