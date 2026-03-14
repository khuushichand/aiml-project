import React from "react"
import { useNavigate } from "react-router-dom"

import { ProjectWorkspace } from "./ProjectWorkspace"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { useServerOnline } from "@/hooks/useServerOnline"
import { usePresentationStudioStore } from "@/store/presentation-studio"

type PresentationStudioPageProps = {
  mode?: "index" | "new" | "detail"
  projectId?: string | null
}

const formatEtag = (version: number | null | undefined): string | null =>
  typeof version === "number" && Number.isFinite(version) ? `W/"v${version}"` : null

const toErrorMessage = (error: unknown): string =>
  error instanceof Error ? error.message || "Failed to load presentation." : "Failed to load presentation."

const createBlankSlideId = (): string =>
  globalThis.crypto?.randomUUID?.() ||
  `slide-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`

export const PresentationStudioPage: React.FC<PresentationStudioPageProps> = ({
  mode = "index",
  projectId = null
}) => {
  const navigate = useNavigate()
  const isOnline = useServerOnline()
  const { capabilities, loading } = useServerCapabilities()
  const loadProject = usePresentationStudioStore((state) => state.loadProject)
  const title = usePresentationStudioStore((state) => state.title)
  const slides = usePresentationStudioStore((state) => state.slides)
  const currentProjectId = usePresentationStudioStore((state) => state.projectId)
  const [isProjectLoading, setIsProjectLoading] = React.useState(mode === "new")
  const [loadError, setLoadError] = React.useState<string | null>(null)
  const newProjectStartedRef = React.useRef(false)

  React.useEffect(() => {
    if (mode !== "new") {
      return
    }
    if (newProjectStartedRef.current) {
      return
    }
    newProjectStartedRef.current = true
    let active = true
    setIsProjectLoading(true)
    setLoadError(null)
    const blankSlideId = createBlankSlideId()

    void tldwClient
      .createPresentation({
        title: "Untitled Presentation",
        description: null,
        theme: "black",
        studio_data: {
          origin: "blank",
          entry_surface: "webui_new"
        },
        slides: [
          {
            order: 0,
            layout: "title",
            title: "Title slide",
            content: "",
            speaker_notes: "",
            metadata: {
              studio: {
                slideId: blankSlideId,
                audio: { status: "missing" },
                image: { status: "missing" }
              }
            }
          }
        ]
      })
      .then((project) => {
        if (!active) {
          return
        }
        loadProject(project, {
          etag: formatEtag(project.version)
        })
        navigate(`/presentation-studio/${project.id}`, {
          replace: true
        })
      })
      .catch((error) => {
        if (!active) {
          return
        }
        setLoadError(toErrorMessage(error))
      })
      .finally(() => {
        if (active) {
          setIsProjectLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [loadProject, mode, navigate])

  React.useEffect(() => {
    if (mode !== "detail" || !projectId) {
      return
    }
    if (currentProjectId === projectId) {
      return
    }
    let active = true
    setIsProjectLoading(true)
    setLoadError(null)
    void tldwClient
      .getPresentation(projectId)
      .then((project) => {
        if (!active) {
          return
        }
        loadProject(project, {
          etag: formatEtag(project.version)
        })
      })
      .catch((error) => {
        if (!active) {
          return
        }
        setLoadError(toErrorMessage(error))
      })
      .finally(() => {
        if (active) {
          setIsProjectLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [currentProjectId, loadProject, mode, projectId])

  if (!isOnline) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h1 className="text-2xl font-semibold text-slate-900">Presentation Studio</h1>
        <p className="mt-2 text-sm text-slate-600">
          Server is offline. Connect to use Presentation Studio.
        </p>
      </section>
    )
  }

  if (!loading && capabilities && !capabilities.hasPresentationStudio) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h1 className="text-2xl font-semibold text-slate-900">Presentation Studio</h1>
        <p className="mt-2 text-sm text-slate-600">
          Presentation Studio is not available on this server.
        </p>
      </section>
    )
  }

  if (mode === "index") {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h1 className="text-2xl font-semibold text-slate-900">Presentation Studio</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">
          Create structured narrated slide decks, stage media per slide, and publish a
          rendered presentation video when the server advertises render support.
        </p>
      </section>
    )
  }

  if (isProjectLoading) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <p className="text-sm text-slate-600">
          {mode === "new" ? "Creating presentation…" : "Loading presentation…"}
        </p>
      </section>
    )
  }

  if (loadError) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h1 className="text-2xl font-semibold text-slate-900">Presentation Studio</h1>
        <p className="mt-2 text-sm text-rose-600">{loadError}</p>
      </section>
    )
  }

  return (
    <section className="space-y-4">
      <header className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Presentation Studio</h1>
            <p className="mt-1 text-sm text-slate-600">
              {title || "Untitled Presentation"} · {slides.length} slide
              {slides.length === 1 ? "" : "s"}
            </p>
          </div>
        </div>
      </header>

      <ProjectWorkspace canRender={Boolean(capabilities?.hasPresentationRender)} />
    </section>
  )
}
