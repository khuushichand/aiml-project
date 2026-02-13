import OptionLayout from "@web/components/layout/WebLayout"
import { PageShell } from "@/components/Common/PageShell"
import { ChunkingPlayground } from "@/components/Option/ChunkingPlayground"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionChunkingPlayground = () => {
  return (
    <RouteErrorBoundary routeId="chunking-playground" routeLabel="Chunking Playground">
      <OptionLayout>
        <PageShell className="py-6" maxWidthClassName="max-w-4xl">
          <ChunkingPlayground />
        </PageShell>
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionChunkingPlayground
