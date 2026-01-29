import OptionLayout from "@web/components/layout/WebLayout"
import { PageShell } from "@/components/Common/PageShell"
import { KanbanPlayground } from "@/components/Option/KanbanPlayground"

const OptionKanbanPlayground = () => {
  return (
    <OptionLayout>
      <PageShell className="py-6" maxWidthClassName="max-w-7xl">
        <KanbanPlayground />
      </PageShell>
    </OptionLayout>
  )
}

export default OptionKanbanPlayground
