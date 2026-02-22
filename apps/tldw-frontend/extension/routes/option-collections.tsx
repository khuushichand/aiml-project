import { CollectionsPlaygroundPage } from "@/components/Option/Collections"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

export default function OptionCollections() {
  return (
    <RouteErrorBoundary routeId="collections" routeLabel="Collections">
      <CollectionsPlaygroundPage />
    </RouteErrorBoundary>
  )
}
