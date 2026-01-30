import OptionLayout from "~/components/Layouts/Layout"
import { PageShell } from "@/components/Common/PageShell"
import { ACPPlayground } from "@/components/Option/ACPPlayground"

const OptionACPPlayground = () => {
  return (
    <OptionLayout>
      <PageShell className="flex-1 min-h-0" maxWidthClassName="max-w-full">
        <ACPPlayground />
      </PageShell>
    </OptionLayout>
  )
}

export default OptionACPPlayground
