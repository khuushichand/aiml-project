import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import OptionLayout from "@/components/Layouts/Layout"
import { CompanionPage } from "@/components/Option/Companion"

export default function OptionCompanion() {
  return (
    <RouteErrorBoundary routeId="companion" routeLabel="Companion">
      <OptionLayout>
        <CompanionPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}
