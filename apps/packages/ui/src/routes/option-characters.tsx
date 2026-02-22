import OptionLayout from "~/components/Layouts/Layout"
import { CharactersWorkspace } from "~/components/Option/Characters/CharactersWorkspace"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionCharactersWorkspaceRoute = () => {
  return (
    <RouteErrorBoundary routeId="characters" routeLabel="Characters">
      <OptionLayout>
        <CharactersWorkspace />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionCharactersWorkspaceRoute
