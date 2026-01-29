import OptionLayout from "~/components/Layouts/Layout"
import { PageShell } from "@/components/Common/PageShell"
import { KnowledgeQA } from "@/components/Option/KnowledgeQA"

const OptionKnowledgeWorkspace = () => {
  return (
    <OptionLayout>
      <PageShell className="flex-1 min-h-0" maxWidthClassName="max-w-full">
        <KnowledgeQA />
      </PageShell>
    </OptionLayout>
  )
}

export default OptionKnowledgeWorkspace
