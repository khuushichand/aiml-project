import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import { PageShell } from "@/components/Common/PageShell"
import { SourceForm } from "@/components/Option/Sources/SourceForm"
import { SourcesAvailabilityGate } from "@/components/Option/Sources/SourcesAvailabilityGate"

export default function OptionSourcesNew() {
  return (
    <RouteErrorBoundary routeId="sources-new" routeLabel="Sources">
      <SourcesAvailabilityGate maxWidthClassName="max-w-4xl">
        <PageShell className="py-6" maxWidthClassName="max-w-4xl">
          <SourceForm mode="create" />
        </PageShell>
      </SourcesAvailabilityGate>
    </RouteErrorBoundary>
  )
}
