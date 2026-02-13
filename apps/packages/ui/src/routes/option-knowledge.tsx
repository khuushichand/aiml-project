import OptionLayout from "~/components/Layouts/Layout"
import { PageShell } from "@/components/Common/PageShell"
import { KnowledgeQA } from "@/components/Option/KnowledgeQA"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionKnowledgeWorkspace = () => {
  return (
    <OptionLayout>
      <RouteErrorBoundary routeId="knowledge" routeLabel="Knowledge QA">
        <PageShell className="flex-1 min-h-0" maxWidthClassName="max-w-full">
          <KnowledgeQA />
        </PageShell>
      </RouteErrorBoundary>
    </OptionLayout>
  )
}

export default OptionKnowledgeWorkspace
