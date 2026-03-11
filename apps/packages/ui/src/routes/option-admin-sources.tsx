import OptionLayout from "@/components/Layouts/Layout"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import { SourcesWorkspacePage } from "@/components/Option/Sources/SourcesWorkspacePage"

export default function OptionAdminSources() {
  return (
    <RouteErrorBoundary routeId="admin-sources" routeLabel="Sources">
      <OptionLayout>
        <SourcesWorkspacePage mode="admin" />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}
