import OptionLayout from "~/components/Layouts/Layout"
import { PageShell } from "@/components/Common/PageShell"
import { McpHubPage } from "@/components/Option/MCPHub"

const OptionMcpHub = () => {
  return (
    <OptionLayout>
      <PageShell className="flex-1 min-h-0" maxWidthClassName="max-w-full">
        <McpHubPage />
      </PageShell>
    </OptionLayout>
  )
}

export default OptionMcpHub
