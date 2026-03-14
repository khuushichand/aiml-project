import OptionLayout from "@/components/Layouts/Layout"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import { PresentationStudioPage } from "@/components/Option/PresentationStudio/PresentationStudioPage"

export default function OptionPresentationStudioNew() {
  return (
    <RouteErrorBoundary routeId="presentation-studio-new" routeLabel="Presentation Studio">
      <OptionLayout>
        <PresentationStudioPage mode="new" />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}
