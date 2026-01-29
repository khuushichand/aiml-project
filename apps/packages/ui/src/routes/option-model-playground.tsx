import OptionLayout from "~/components/Layouts/Layout"
import { PageShell } from "@/components/Common/PageShell"
import { ModelPlayground } from "@/components/Option/ModelPlayground"

const OptionModelPlayground = () => {
  return (
    <OptionLayout>
      <PageShell className="py-6 flex-1 min-h-0" maxWidthClassName="max-w-7xl">
        <ModelPlayground />
      </PageShell>
    </OptionLayout>
  )
}

export default OptionModelPlayground
