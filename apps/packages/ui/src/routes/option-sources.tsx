import OptionLayout from "@/components/Layouts/Layout"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import { SourcesWorkspacePage } from "@/components/Option/Sources/SourcesWorkspacePage"

export default function OptionSources() {
  return (
    <RouteErrorBoundary routeId="sources" routeLabel="Sources">
      <OptionLayout>
        <SourcesWorkspacePage mode="user" />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}
