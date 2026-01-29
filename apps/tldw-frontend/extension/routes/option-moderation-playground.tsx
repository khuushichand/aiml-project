import OptionLayout from "@web/components/layout/WebLayout"
import { PageShell } from "@/components/Common/PageShell"
import { ModerationPlayground } from "@/components/Option/ModerationPlayground"

const OptionModerationPlayground = () => {
  return (
    <OptionLayout>
      <PageShell className="py-6" maxWidthClassName="max-w-7xl">
        <ModerationPlayground />
      </PageShell>
    </OptionLayout>
  )
}

export default OptionModerationPlayground
