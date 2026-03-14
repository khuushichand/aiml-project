import OptionLayout from "@/components/Layouts/Layout"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import { PresentationStudioPage } from "@/components/Option/PresentationStudio/PresentationStudioPage"

export default function OptionPresentationStudio() {
  return (
    <RouteErrorBoundary routeId="presentation-studio" routeLabel="Presentation Studio">
      <OptionLayout>
        <PresentationStudioPage mode="index" />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}
