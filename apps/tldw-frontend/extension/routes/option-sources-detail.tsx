import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import { SourceDetailPage } from "@/components/Option/Sources/SourceDetailPage"
import { SourcesAvailabilityGate } from "@/components/Option/Sources/SourcesAvailabilityGate"
import { useParams } from "react-router-dom"

export default function OptionSourcesDetail() {
  const { sourceId } = useParams()

  return (
    <RouteErrorBoundary routeId="sources-detail" routeLabel="Sources">
      <SourcesAvailabilityGate>
        <SourceDetailPage sourceId={sourceId || ""} />
      </SourcesAvailabilityGate>
    </RouteErrorBoundary>
  )
}
