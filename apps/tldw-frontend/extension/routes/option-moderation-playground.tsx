import OptionLayout from "@web/components/layout/WebLayout"
import { PageShell } from "@/components/Common/PageShell"
import { ModerationPlayground } from "@/components/Option/ModerationPlayground"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionModerationPlayground = () => {
  return (
    <RouteErrorBoundary routeId="moderation-playground" routeLabel="Moderation Playground">
      <OptionLayout>
        <PageShell className="py-6" maxWidthClassName="max-w-7xl">
          <ModerationPlayground />
        </PageShell>
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionModerationPlayground
