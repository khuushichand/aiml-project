import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import OptionLayout from "@/components/Layouts/Layout"
import { CompanionHomeShell } from "@/components/Option/CompanionHome"

export default function OptionCompanion() {
  return (
    <RouteErrorBoundary routeId="companion" routeLabel="Companion">
      <OptionLayout>
        <CompanionHomeShell surface="options" />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}
