import OptionLayout from "~/components/Layouts/Layout"
import { WorkspacePlayground } from "@/components/Option/WorkspacePlayground"

const OptionWorkspacePlayground = () => {
  return (
    <OptionLayout>
      <div className="w-full">
        <WorkspacePlayground />
      </div>
    </OptionLayout>
  )
}

export default OptionWorkspacePlayground
