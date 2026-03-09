import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import { SourceDetailPage } from "@/components/Option/Sources/SourceDetailPage"
import { useParams } from "react-router-dom"

export default function OptionSourcesDetail() {
  const { sourceId } = useParams()

  return (
    <RouteErrorBoundary routeId="sources-detail" routeLabel="Sources">
      <SourceDetailPage sourceId={sourceId || ""} />
    </RouteErrorBoundary>
  )
}
