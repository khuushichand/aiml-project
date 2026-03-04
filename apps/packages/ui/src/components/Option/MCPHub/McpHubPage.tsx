import { useState } from "react"
import { Tabs, Typography } from "antd"

import { AcpProfilesTab } from "./AcpProfilesTab"
import { ToolCatalogsTab } from "./ToolCatalogsTab"
import { ExternalServersTab } from "./ExternalServersTab"

export const McpHubPage = () => {
  const [activeTab, setActiveTab] = useState("acp-profiles")

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
            key: "acp-profiles",
            label: "ACP Profiles",
            children: <AcpProfilesTab />
          },
          {
            key: "tool-catalogs",
            label: "Tool Catalogs",
            children: <ToolCatalogsTab />
          },
          {
            key: "external-servers",
            label: "External Servers",
            children: <ExternalServersTab />
          }
        ]}
      />
    </div>
  )
}
