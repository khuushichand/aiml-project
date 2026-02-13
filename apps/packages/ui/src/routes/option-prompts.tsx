import OptionLayout from "~/components/Layouts/Layout"
import { PromptsWorkspace } from "~/components/Option/Prompt/PromptsWorkspace"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionPromptsWorkspaceRoute = () => {
  return (
    <OptionLayout>
      <RouteErrorBoundary routeId="prompts" routeLabel="Prompts">
        <PromptsWorkspace />
      </RouteErrorBoundary>
    </OptionLayout>
  )
}

export default OptionPromptsWorkspaceRoute
