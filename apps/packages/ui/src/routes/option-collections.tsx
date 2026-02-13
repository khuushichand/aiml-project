import { CollectionsPlaygroundPage } from "@/components/Option/Collections"
import OptionLayout from "@/components/Layouts/Layout"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

export default function OptionCollections() {
  return (
    <RouteErrorBoundary routeId="collections" routeLabel="Collections">
      <OptionLayout>
        <CollectionsPlaygroundPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}
