import { createWithEqualityFn } from "zustand/traditional"

import type {
  PresentationStudioRecord,
  PresentationStudioSlide
} from "@/services/tldw/TldwApiClient"

export type PresentationStudioAssetStatus =
  | "missing"
  | "ready"
  | "stale"
  | "generating"
  | "failed"

export type PresentationStudioSlideStudioMeta = {
  slideId: string
  audio: {
    status: PresentationStudioAssetStatus
    asset_ref?: string | null
    duration_ms?: number | null
  }
  image: {
    status: PresentationStudioAssetStatus
    asset_ref?: string | null
  }
  [key: string]: any
}

export type PresentationStudioEditorSlide = Omit<PresentationStudioSlide, "metadata"> & {
  metadata: Record<string, any> & {
    studio: PresentationStudioSlideStudioMeta
  }
}

type AutosaveState = "idle" | "saving" | "error"

type PresentationStudioStore = {
  projectId: string | null
  title: string
  description: string
  theme: string
  studioData: Record<string, any> | null
  slides: PresentationStudioEditorSlide[]
  selectedSlideId: string | null
  etag: string | null
  isDirty: boolean
  autosaveState: AutosaveState
  autosaveError: string | null
  reset: () => void
  initializeBlankProject: () => void
  loadProject: (
    project: PresentationStudioRecord,
    options?: { etag?: string | null }
  ) => void
  updateProjectMeta: (updates: {
    title?: string
    description?: string
    theme?: string
    studioData?: Record<string, any> | null
  }) => void
  selectSlide: (slideId: string) => void
  addSlide: () => void
  updateSlide: (
    slideId: string,
    updates: Partial<PresentationStudioEditorSlide>
  ) => void
  setAutosaveState: (state: AutosaveState, error?: string | null) => void
  markPersisted: (etag?: string | null, project?: PresentationStudioRecord) => void
  buildPatchPayload: () => {
    title: string
    description: string | null
    theme: string
    studio_data: Record<string, any> | null
    slides: PresentationStudioSlide[]
  }
}

const createSlideId = (): string =>
  globalThis.crypto?.randomUUID?.() ||
  `slide-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`

const normalizeAssetStatus = (
  candidate: unknown,
  fallback: PresentationStudioAssetStatus
): PresentationStudioAssetStatus => {
  const normalized = String(candidate || "").trim().toLowerCase()
  return ["missing", "ready", "stale", "generating", "failed"].includes(normalized)
    ? (normalized as PresentationStudioAssetStatus)
    : fallback
}

const normalizeSlide = (
  slide: Partial<PresentationStudioSlide> & { metadata?: Record<string, any> },
  order: number
): PresentationStudioEditorSlide => {
  const metadata =
    slide.metadata && typeof slide.metadata === "object" && !Array.isArray(slide.metadata)
      ? { ...slide.metadata }
      : {}
  const studio =
    metadata.studio && typeof metadata.studio === "object" && !Array.isArray(metadata.studio)
      ? { ...metadata.studio }
      : {}
  const audioState =
    studio.audio && typeof studio.audio === "object" && !Array.isArray(studio.audio)
      ? { ...studio.audio }
      : {}
  const imageState =
    studio.image && typeof studio.image === "object" && !Array.isArray(studio.image)
      ? { ...studio.image }
      : {}
  const slideId =
    typeof studio.slideId === "string" && studio.slideId.trim().length > 0
      ? studio.slideId
      : createSlideId()

  return {
    order,
    layout: String(slide.layout || "content"),
    title: slide.title ?? "",
    content: slide.content ?? "",
    speaker_notes: slide.speaker_notes ?? "",
    metadata: {
      ...metadata,
      studio: {
        ...studio,
        slideId,
        audio: {
          ...audioState,
          status: normalizeAssetStatus(
            audioState.status,
            audioState.asset_ref ? "ready" : "missing"
          )
        },
        image: {
          ...imageState,
          status: normalizeAssetStatus(
            imageState.status,
            imageState.asset_ref ? "ready" : "missing"
          )
        }
      }
    }
  }
}

const createBlankSlide = (order: number): PresentationStudioEditorSlide =>
  normalizeSlide(
    {
      order,
      layout: order === 0 ? "title" : "content",
      title: order === 0 ? "Title slide" : `Slide ${order + 1}`,
      content: "",
      speaker_notes: "",
      metadata: {}
    },
    order
  )

const createInitialState = () => ({
  projectId: null,
  title: "Untitled Presentation",
  description: "",
  theme: "black",
  studioData: { origin: "blank" } as Record<string, any> | null,
  slides: [] as PresentationStudioEditorSlide[],
  selectedSlideId: null as string | null,
  etag: null as string | null,
  isDirty: false,
  autosaveState: "idle" as AutosaveState,
  autosaveError: null as string | null
})

export const usePresentationStudioStore = createWithEqualityFn<PresentationStudioStore>(
  (set, get) => ({
    ...createInitialState(),

    reset: () => set(createInitialState()),

    initializeBlankProject: () => {
      const firstSlide = createBlankSlide(0)
      set({
        ...createInitialState(),
        slides: [firstSlide],
        selectedSlideId: firstSlide.metadata.studio.slideId
      })
    },

    loadProject: (project, options) => {
      const slides = (project.slides || []).map((slide, index) => normalizeSlide(slide, index))
      set({
        projectId: project.id,
        title: project.title || "Untitled Presentation",
        description: project.description || "",
        theme: project.theme || "black",
        studioData:
          project.studio_data && typeof project.studio_data === "object"
            ? { ...project.studio_data }
            : null,
        slides,
        selectedSlideId: slides[0]?.metadata.studio.slideId || null,
        etag: options?.etag ?? `W/"v${project.version}"`,
        isDirty: false,
        autosaveState: "idle",
        autosaveError: null
      })
    },

    updateProjectMeta: (updates) =>
      set((state) => ({
        title: updates.title ?? state.title,
        description: updates.description ?? state.description,
        theme: updates.theme ?? state.theme,
        studioData: updates.studioData ?? state.studioData,
        isDirty: true
      })),

    selectSlide: (slideId) => set({ selectedSlideId: slideId }),

    addSlide: () =>
      set((state) => {
        const slide = createBlankSlide(state.slides.length)
        return {
          slides: [...state.slides, slide],
          selectedSlideId: slide.metadata.studio.slideId,
          isDirty: true
        }
      }),

    updateSlide: (slideId, updates) =>
      set((state) => {
        const slides = state.slides.map((slide, index) => {
          if (slide.metadata.studio.slideId !== slideId) {
            return slide
          }
          const nextMetadata =
            updates.metadata && typeof updates.metadata === "object"
              ? {
                  ...slide.metadata,
                  ...updates.metadata,
                  studio: {
                    ...slide.metadata.studio,
                    ...(updates.metadata.studio || {})
                  }
                }
              : slide.metadata
          const nextSlide: PresentationStudioEditorSlide = {
            ...slide,
            ...updates,
            order: index,
            metadata: nextMetadata
          }
          if (
            Object.prototype.hasOwnProperty.call(updates, "speaker_notes") &&
            updates.speaker_notes !== slide.speaker_notes
          ) {
            nextSlide.metadata = {
              ...nextSlide.metadata,
              studio: {
                ...nextSlide.metadata.studio,
                audio: {
                  ...nextSlide.metadata.studio.audio,
                  status: "stale"
                }
              }
            }
          }
          return nextSlide
        })
        return {
          slides,
          isDirty: true
        }
      }),

    setAutosaveState: (autosaveState, autosaveError = null) =>
      set({ autosaveState, autosaveError }),

    markPersisted: (etag, project) => {
      if (project) {
        get().loadProject(project, {
          etag: etag ?? `W/"v${project.version}"`
        })
        return
      }
      set({
        etag: etag ?? get().etag,
        isDirty: false,
        autosaveState: "idle",
        autosaveError: null
      })
    },

    buildPatchPayload: () => {
      const state = get()
      return {
        title: state.title,
        description: state.description || null,
        theme: state.theme,
        studio_data: state.studioData,
        slides: state.slides.map((slide, index) => ({
          order: index,
          layout: slide.layout,
          title: slide.title ?? "",
          content: slide.content,
          speaker_notes: slide.speaker_notes ?? "",
          metadata: slide.metadata
        }))
      }
    }
  })
)
