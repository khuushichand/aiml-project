import { useParams } from "react-router-dom"

import OptionLayout from "@/components/Layouts/Layout"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import { PresentationStudioPage } from "@/components/Option/PresentationStudio/PresentationStudioPage"

export default function OptionPresentationStudioDetail() {
  const { projectId } = useParams<{ projectId: string }>()

  return (
    <RouteErrorBoundary routeId="presentation-studio-detail" routeLabel="Presentation Studio">
      <OptionLayout>
        <PresentationStudioPage mode="detail" projectId={projectId || null} />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}
