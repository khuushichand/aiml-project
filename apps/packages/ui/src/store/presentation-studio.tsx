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

export type PresentationStudioPatchPayload = {
  title: string
  description: string | null
  theme: string
  studio_data: Record<string, any> | null
  slides: PresentationStudioSlide[]
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
    options?: { etag?: string | null; preserveDirty?: boolean }
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

const buildPatchPayloadFromSlides = (input: {
  title: string
  description?: string | null
  theme: string
  studio_data?: Record<string, any> | null
  slides: Array<PresentationStudioSlide | PresentationStudioEditorSlide>
}): PresentationStudioPatchPayload => ({
  title: input.title,
  description: input.description || null,
  theme: input.theme,
  studio_data: input.studio_data ?? null,
  slides: input.slides.map((slide, index) => ({
    order: index,
    layout: slide.layout,
    title: slide.title ?? "",
    content: slide.content,
    speaker_notes: slide.speaker_notes ?? "",
    metadata: slide.metadata
  }))
})

const mergeSlideMetadata = (
  remoteMetadata: Record<string, any> | undefined,
  localMetadata: Record<string, any> | undefined
): Record<string, any> => {
  const remote = remoteMetadata && typeof remoteMetadata === "object" ? remoteMetadata : {}
  const local = localMetadata && typeof localMetadata === "object" ? localMetadata : {}
  const remoteStudio =
    remote.studio && typeof remote.studio === "object" && !Array.isArray(remote.studio)
      ? remote.studio
      : {}
  const localStudio =
    local.studio && typeof local.studio === "object" && !Array.isArray(local.studio)
      ? local.studio
      : {}
  const remoteAudio =
    remoteStudio.audio && typeof remoteStudio.audio === "object" && !Array.isArray(remoteStudio.audio)
      ? remoteStudio.audio
      : {}
  const localAudio =
    localStudio.audio && typeof localStudio.audio === "object" && !Array.isArray(localStudio.audio)
      ? localStudio.audio
      : {}
  const remoteImage =
    remoteStudio.image && typeof remoteStudio.image === "object" && !Array.isArray(remoteStudio.image)
      ? remoteStudio.image
      : {}
  const localImage =
    localStudio.image && typeof localStudio.image === "object" && !Array.isArray(localStudio.image)
      ? localStudio.image
      : {}

  return {
    ...remote,
    ...local,
    images:
      Object.prototype.hasOwnProperty.call(local, "images") && Array.isArray(local.images)
        ? local.images
        : remote.images,
    studio: {
      ...remoteStudio,
      ...localStudio,
      slideId:
        typeof localStudio.slideId === "string" && localStudio.slideId.trim().length > 0
          ? localStudio.slideId
          : typeof remoteStudio.slideId === "string" && remoteStudio.slideId.trim().length > 0
            ? remoteStudio.slideId
            : createSlideId(),
      audio: {
        ...remoteAudio,
        ...localAudio,
        status: normalizeAssetStatus(
          localAudio.status ?? remoteAudio.status,
          localAudio.asset_ref || remoteAudio.asset_ref ? "ready" : "missing"
        )
      },
      image: {
        ...remoteImage,
        ...localImage,
        status: normalizeAssetStatus(
          localImage.status ?? remoteImage.status,
          localImage.asset_ref || remoteImage.asset_ref ? "ready" : "missing"
        )
      }
    }
  }
}

export const buildPresentationStudioPatchPayloadFromRecord = (
  project: Pick<PresentationStudioRecord, "title" | "description" | "theme" | "studio_data" | "slides">
): PresentationStudioPatchPayload =>
  buildPatchPayloadFromSlides({
    title: project.title,
    description: project.description,
    theme: project.theme,
    studio_data: project.studio_data ?? null,
    slides: project.slides
  })

export const mergePresentationStudioDraftWithRemote = (
  latest: PresentationStudioRecord,
  localDraft: PresentationStudioPatchPayload
): PresentationStudioRecord => {
  const remoteSlides = (latest.slides || []).map((slide, index) => normalizeSlide(slide, index))
  const localSlides = (localDraft.slides || []).map((slide, index) => normalizeSlide(slide, index))
  const remoteBySlideId = new Map(
    remoteSlides.map((slide) => [slide.metadata.studio.slideId, slide] as const)
  )

  const mergedSlides: PresentationStudioSlide[] = []
  for (const localSlide of localSlides) {
    const slideId = localSlide.metadata.studio.slideId
    const remoteSlide = remoteBySlideId.get(slideId)
    if (remoteSlide) {
      remoteBySlideId.delete(slideId)
    }
    mergedSlides.push({
      order: mergedSlides.length,
      layout: localSlide.layout,
      title: localSlide.title ?? remoteSlide?.title ?? "",
      content: localSlide.content ?? remoteSlide?.content ?? "",
      speaker_notes: localSlide.speaker_notes ?? remoteSlide?.speaker_notes ?? "",
      metadata: mergeSlideMetadata(remoteSlide?.metadata, localSlide.metadata)
    })
  }

  for (const remoteSlide of remoteSlides) {
    if (!remoteBySlideId.has(remoteSlide.metadata.studio.slideId)) {
      continue
    }
    mergedSlides.push({
      order: mergedSlides.length,
      layout: remoteSlide.layout,
      title: remoteSlide.title ?? "",
      content: remoteSlide.content,
      speaker_notes: remoteSlide.speaker_notes ?? "",
      metadata: remoteSlide.metadata
    })
  }

  return {
    ...latest,
    title: localDraft.title,
    description: localDraft.description,
    theme: localDraft.theme,
    studio_data: localDraft.studio_data,
    slides: mergedSlides
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

    loadProject: (project, options) =>
      set((state) => {
      const slides = (project.slides || []).map((slide, index) => normalizeSlide(slide, index))
      const previousSelected = state.selectedSlideId
      const selectedSlideId =
        slides.find((slide) => slide.metadata.studio.slideId === previousSelected)?.metadata.studio.slideId ||
        slides[0]?.metadata.studio.slideId ||
        null
      return {
        projectId: project.id,
        title: project.title || "Untitled Presentation",
        description: project.description || "",
        theme: project.theme || "black",
        studioData:
          project.studio_data && typeof project.studio_data === "object"
            ? { ...project.studio_data }
            : null,
        slides,
        selectedSlideId,
        etag: options?.etag ?? `W/"v${project.version}"`,
        isDirty: Boolean(options?.preserveDirty),
        autosaveState: options?.preserveDirty ? state.autosaveState : "idle",
        autosaveError: options?.preserveDirty ? state.autosaveError : null
      }
    }),

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
      return buildPatchPayloadFromSlides({
        title: state.title,
        description: state.description,
        theme: state.theme,
        studio_data: state.studioData,
        slides: state.slides
      })
    }
  })
)
