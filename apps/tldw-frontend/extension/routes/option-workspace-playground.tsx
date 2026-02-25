import OptionLayout from "@web/components/layout/WebLayout"
import { PageShell } from "@/components/Common/PageShell"
import { WorkspacePlayground } from "@/components/Option/WorkspacePlayground"

const OptionWorkspacePlayground = () => {
  return (
    <OptionLayout>
      <PageShell className="flex-1 min-h-0" maxWidthClassName="max-w-full">
        <WorkspacePlayground />
      </PageShell>
    </OptionLayout>
  )
}

export default OptionWorkspacePlayground
