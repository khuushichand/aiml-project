import OptionLayout from "~/components/Layouts/Layout"
import { DictionariesWorkspace } from "~/components/Option/Dictionaries/DictionariesWorkspace"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionDictionariesWorkspaceRoute = () => {
  return (
    <RouteErrorBoundary routeId="dictionaries" routeLabel="Dictionaries">
      <OptionLayout>
        <DictionariesWorkspace />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionDictionariesWorkspaceRoute
