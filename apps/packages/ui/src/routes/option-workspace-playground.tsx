import OptionLayout from "~/components/Layouts/Layout"
import { WorkspacePlayground } from "@/components/Option/WorkspacePlayground"

const OptionWorkspacePlayground = () => {
  return (
    <OptionLayout>
      <div className="h-full w-full overflow-hidden">
        <WorkspacePlayground />
      </div>
    </OptionLayout>
  )
}

export default OptionWorkspacePlayground
