import OptionLayout from "~/components/Layouts/Layout"
import { PageShell } from "@/components/Common/PageShell"
import { AgentRegistryPage } from "@/components/Option/AgentRegistry"

const OptionAgents = () => {
  return (
    <OptionLayout>
      <PageShell className="py-6">
        <AgentRegistryPage />
      </PageShell>
    </OptionLayout>
  )
}

export default OptionAgents
