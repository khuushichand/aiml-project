import OptionLayout from "@/components/Layouts/Layout"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import { ExtensionStartPanel } from "@/components/Option/PresentationStudio/ExtensionStartPanel"

export default function OptionPresentationStudioStart() {
  return (
    <RouteErrorBoundary routeId="presentation-studio-start" routeLabel="Presentation Studio">
      <OptionLayout>
        <ExtensionStartPanel />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}
