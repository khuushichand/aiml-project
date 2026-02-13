import OptionLayout from "@web/components/layout/WebLayout"
import { WorldBooksWorkspace } from "~/components/Option/WorldBooks/WorldBooksWorkspace"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionWorldBooksWorkspaceRoute = () => {
  return (
    <RouteErrorBoundary routeId="world-books" routeLabel="World Books">
      <OptionLayout>
        <WorldBooksWorkspace />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionWorldBooksWorkspaceRoute
