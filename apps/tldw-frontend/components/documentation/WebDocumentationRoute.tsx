import React from "react"

import { PageShell } from "@/components/Common/PageShell"
import DocumentationPage, {
  type DocumentationDocEntry,
  type DocumentationDocsBySource,
  type DocumentationSource,
} from "@/components/Option/Documentation/DocumentationPage"
import OptionLayout from "@web/components/layout/WebLayout"

type ManifestEntry = {
  id: string
  title: string
  source: DocumentationSource
  relativePath: string
  fullPath: string
}

type DocumentationManifestResponse = {
  docsBySource?: Partial<Record<DocumentationSource, ManifestEntry[]>>
}

const normalizeDocsBySource = (
  docsBySource?: Partial<Record<DocumentationSource, ManifestEntry[]>>
): Partial<DocumentationDocsBySource> => ({
  extension: docsBySource?.extension?.map((doc) => ({
    ...doc,
    isFallback: false,
  })),
  server: docsBySource?.server?.map((doc) => ({
    ...doc,
    isFallback: false,
  })),
})

const WebDocumentationRoute: React.FC = () => {
  const [docsBySource, setDocsBySource] = React.useState<
    Partial<DocumentationDocsBySource> | null
  >(null)

  React.useEffect(() => {
    const controller = new AbortController()

    const loadManifest = async () => {
      try {
        const response = await fetch("/api/documentation/manifest", {
          signal: controller.signal,
        })
        if (!response.ok) {
          throw new Error(`Documentation manifest request failed (${response.status}).`)
        }
        const payload = (await response.json()) as DocumentationManifestResponse
        setDocsBySource(normalizeDocsBySource(payload.docsBySource))
      } catch (error) {
        if ((error as Error).name === "AbortError") return
        setDocsBySource({})
      }
    }

    void loadManifest()
    return () => controller.abort()
  }, [])

  const loadDocContent = React.useCallback(
    async (doc: DocumentationDocEntry) => {
      const query = new URLSearchParams({
        source: doc.source,
        relativePath: doc.relativePath,
      })
      const response = await fetch(`/api/documentation/content?${query.toString()}`)
      if (!response.ok) {
        throw new Error(`Documentation content request failed (${response.status}).`)
      }
      const payload = (await response.json()) as { content?: string }
      return payload.content ?? ""
    },
    []
  )

  return (
    <OptionLayout>
      {docsBySource ? (
        <DocumentationPage
          docsBySource={docsBySource}
          loadDocContent={loadDocContent}
        />
      ) : (
        <PageShell className="py-6" maxWidthClassName="max-w-6xl">
          <div className="flex min-h-[40vh] items-center justify-center text-sm text-text-muted">
            Loading documentation...
          </div>
        </PageShell>
      )}
    </OptionLayout>
  )
}

export default WebDocumentationRoute
