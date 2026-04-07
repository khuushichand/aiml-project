import { PageShell } from "@/components/Common/PageShell"
import { McpHubPage } from "@/components/Option/MCPHub"

import { SettingsRoute } from "./settings-route"

export const OptionSettingsMcpHub = () => (
  <SettingsRoute>
    <PageShell className="flex-1 min-h-0" maxWidthClassName="max-w-full">
      <McpHubPage />
    </PageShell>
  </SettingsRoute>
)

export default OptionSettingsMcpHub
