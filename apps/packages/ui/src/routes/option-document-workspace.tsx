import OptionLayout from "~/components/Layouts/Layout"
import { DocumentWorkspacePage } from "@/components/DocumentWorkspace"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionDocumentWorkspace = () => {
  return (
    <RouteErrorBoundary routeId="document-workspace" routeLabel="Document Workspace">
      <OptionLayout>
        <div className="h-full min-h-0 w-full overflow-hidden">
          <DocumentWorkspacePage />
        </div>
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionDocumentWorkspace
