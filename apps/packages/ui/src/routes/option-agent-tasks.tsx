import OptionLayout from "~/components/Layouts/Layout"
import { PageShell } from "@/components/Common/PageShell"
import { AgentTasksPage } from "@/components/Option/AgentTasks"

const OptionAgentTasks = () => {
  return (
    <OptionLayout>
      <PageShell className="py-6" maxWidthClassName="max-w-7xl">
        <AgentTasksPage />
      </PageShell>
    </OptionLayout>
  )
}

export default OptionAgentTasks
