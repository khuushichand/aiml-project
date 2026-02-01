import OptionLayout from "~/components/Layouts/Layout"
import { DocumentWorkspacePage } from "@/components/DocumentWorkspace"

const OptionDocumentWorkspace = () => {
  return (
    <OptionLayout>
      <div className="h-full w-full overflow-hidden">
        <DocumentWorkspacePage />
      </div>
    </OptionLayout>
  )
}

export default OptionDocumentWorkspace
