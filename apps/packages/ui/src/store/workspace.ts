/**
 * Workspace Zustand Store
 * Manages state for the NotebookLM-style three-pane research interface
 */

import { createWithEqualityFn } from "zustand/traditional"
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware"
import type {
  AddSourceModalState,
  AddSourceTab,
  ArtifactStatus,
  ArtifactType,
  AudioGenerationSettings,
  GeneratedArtifact,
  WorkspaceConfig,
  WorkspaceNote,
  WorkspaceSource,
  WorkspaceSourceType
} from "@/types/workspace"
import { DEFAULT_AUDIO_SETTINGS, DEFAULT_WORKSPACE_NOTE } from "@/types/workspace"

// ─────────────────────────────────────────────────────────────────────────────
// Storage Configuration
// ─────────────────────────────────────────────────────────────────────────────

const STORAGE_KEY = "tldw-workspace"
const generateWorkspaceId = (): string => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID()
  }
  return Math.random().toString(36).slice(2)
}

/**
 * Creates a memory storage fallback for SSR environments
 */
const createMemoryStorage = (): StateStorage => ({
  getItem: () => null,
  setItem: () => {},
  removeItem: () => {}
})

/**
 * Date fields that need to be revived from ISO strings
 */
const DATE_FIELDS = new Set([
  "workspaceCreatedAt",
  "addedAt",
  "createdAt",
  "completedAt"
])

/**
 * Custom JSON parse reviver that converts ISO date strings back to Date objects
 */
const dateReviver = (key: string, value: unknown): unknown => {
  if (DATE_FIELDS.has(key) && typeof value === "string") {
    const date = new Date(value)
    return isNaN(date.getTime()) ? value : date
  }
  return value
}

/**
 * Custom storage that handles Date serialization/deserialization
 */
const createWorkspaceStorage = (): StateStorage => {
  if (typeof window === "undefined") {
    return createMemoryStorage()
  }

  return {
    getItem: (name: string): string | null => {
      const value = localStorage.getItem(name)
      if (!value) return null
      try {
        // Parse with date reviver
        const parsed = JSON.parse(value, dateReviver)
        return JSON.stringify(parsed)
      } catch {
        return value
      }
    },
    setItem: (name: string, value: string): void => {
      localStorage.setItem(name, value)
    },
    removeItem: (name: string): void => {
      localStorage.removeItem(name)
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// State Types
// ─────────────────────────────────────────────────────────────────────────────

interface WorkspaceIdentityState {
  workspaceId: string
  workspaceName: string
  workspaceTag: string // Format: "workspace:<slug>"
  workspaceCreatedAt: Date | null
}

interface SourcesState {
  sources: WorkspaceSource[]
  selectedSourceIds: string[]
  sourceSearchQuery: string
  sourcesLoading: boolean
  sourcesError: string | null
}

interface StudioState {
  generatedArtifacts: GeneratedArtifact[]
  notes: string // Legacy simple notes field
  currentNote: WorkspaceNote // Full note with title, keywords, versioning
  isGeneratingOutput: boolean
  generatingOutputType: ArtifactType | null
}

interface UIState {
  leftPaneCollapsed: boolean
  rightPaneCollapsed: boolean
  addSourceModalOpen: boolean
  addSourceModalTab: AddSourceTab
  addSourceProcessing: boolean
  addSourceError: string | null
}

interface AudioSettingsState {
  audioSettings: AudioGenerationSettings
}

// ─────────────────────────────────────────────────────────────────────────────
// Action Types
// ─────────────────────────────────────────────────────────────────────────────

interface WorkspaceIdentityActions {
  initializeWorkspace: (name?: string) => void
  setWorkspaceName: (name: string) => void
  loadWorkspace: (config: WorkspaceConfig) => void
}

interface SourcesActions {
  addSource: (
    source: Omit<WorkspaceSource, "id" | "addedAt">
  ) => WorkspaceSource
  addSources: (
    sources: Omit<WorkspaceSource, "id" | "addedAt">[]
  ) => WorkspaceSource[]
  removeSource: (id: string) => void
  removeSources: (ids: string[]) => void
  toggleSourceSelection: (id: string) => void
  selectAllSources: () => void
  deselectAllSources: () => void
  setSelectedSourceIds: (ids: string[]) => void
  setSourceSearchQuery: (query: string) => void
  setSourcesLoading: (loading: boolean) => void
  setSourcesError: (error: string | null) => void
  getSelectedSources: () => WorkspaceSource[]
  getSelectedMediaIds: () => number[]
}

interface StudioActions {
  addArtifact: (
    artifact: Omit<GeneratedArtifact, "id" | "createdAt">
  ) => GeneratedArtifact
  updateArtifactStatus: (
    id: string,
    status: ArtifactStatus,
    updates?: Partial<GeneratedArtifact>
  ) => void
  removeArtifact: (id: string) => void
  clearArtifacts: () => void
  setNotes: (notes: string) => void
  setIsGeneratingOutput: (
    isGenerating: boolean,
    outputType?: ArtifactType | null
  ) => void
  // Note management actions
  setCurrentNote: (note: WorkspaceNote | null) => void
  updateNoteContent: (content: string) => void
  updateNoteTitle: (title: string) => void
  updateNoteKeywords: (keywords: string[]) => void
  clearCurrentNote: () => void
  loadNote: (note: { id: number; title: string; content: string; keywords?: string[]; version?: number }) => void
}

interface UIActions {
  toggleLeftPane: () => void
  toggleRightPane: () => void
  setLeftPaneCollapsed: (collapsed: boolean) => void
  setRightPaneCollapsed: (collapsed: boolean) => void
  openAddSourceModal: (tab?: AddSourceTab) => void
  closeAddSourceModal: () => void
  setAddSourceModalTab: (tab: AddSourceTab) => void
  setAddSourceProcessing: (processing: boolean) => void
  setAddSourceError: (error: string | null) => void
}

interface AudioSettingsActions {
  setAudioSettings: (settings: Partial<AudioGenerationSettings>) => void
  resetAudioSettings: () => void
}

interface ResetActions {
  reset: () => void
  resetSources: () => void
  resetStudio: () => void
}

// ─────────────────────────────────────────────────────────────────────────────
// Combined State & Actions
// ─────────────────────────────────────────────────────────────────────────────

export type WorkspaceState = WorkspaceIdentityState &
  SourcesState &
  StudioState &
  UIState &
  AudioSettingsState &
  WorkspaceIdentityActions &
  SourcesActions &
  StudioActions &
  UIActions &
  AudioSettingsActions &
  ResetActions

// ─────────────────────────────────────────────────────────────────────────────
// Initial State
// ─────────────────────────────────────────────────────────────────────────────

const createSlug = (name: string): string => {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 32)
}

const initialIdentityState: WorkspaceIdentityState = {
  workspaceId: "",
  workspaceName: "",
  workspaceTag: "",
  workspaceCreatedAt: null
}

const initialSourcesState: SourcesState = {
  sources: [],
  selectedSourceIds: [],
  sourceSearchQuery: "",
  sourcesLoading: false,
  sourcesError: null
}

const initialStudioState: StudioState = {
  generatedArtifacts: [],
  notes: "",
  currentNote: { ...DEFAULT_WORKSPACE_NOTE },
  isGeneratingOutput: false,
  generatingOutputType: null
}

const initialUIState: UIState = {
  leftPaneCollapsed: false,
  rightPaneCollapsed: false,
  addSourceModalOpen: false,
  addSourceModalTab: "upload",
  addSourceProcessing: false,
  addSourceError: null
}

const initialAudioSettingsState: AudioSettingsState = {
  audioSettings: { ...DEFAULT_AUDIO_SETTINGS }
}

const initialState = {
  ...initialIdentityState,
  ...initialSourcesState,
  ...initialStudioState,
  ...initialUIState,
  ...initialAudioSettingsState
}

// ─────────────────────────────────────────────────────────────────────────────
// Persisted State Type (subset of state that gets saved)
// ─────────────────────────────────────────────────────────────────────────────

interface PersistedWorkspaceState {
  // Workspace identity
  workspaceId: string
  workspaceName: string
  workspaceTag: string
  workspaceCreatedAt: Date | null

  // Sources (without transient state)
  sources: WorkspaceSource[]
  selectedSourceIds: string[]

  // Studio outputs (generated artifacts persist, but audioUrl blobs don't survive reload)
  generatedArtifacts: GeneratedArtifact[]
  notes: string
  currentNote: WorkspaceNote

  // Pane visibility preferences
  leftPaneCollapsed: boolean
  rightPaneCollapsed: boolean

  // Audio generation settings
  audioSettings: AudioGenerationSettings
}

// ─────────────────────────────────────────────────────────────────────────────
// Store
// ─────────────────────────────────────────────────────────────────────────────

export const useWorkspaceStore = createWithEqualityFn<WorkspaceState>()(
  persist<WorkspaceState, [], [], PersistedWorkspaceState>(
    (set, get) => ({
      ...initialState,

    // ─────────────────────────────────────────────────────────────────────────
    // Workspace Identity Actions
    // ─────────────────────────────────────────────────────────────────────────

    initializeWorkspace: (name = "New Research") => {
      const id = generateWorkspaceId()
      const slug = createSlug(name) || id.slice(0, 8)
      set({
        workspaceId: id,
        workspaceName: name,
        workspaceTag: `workspace:${slug}`,
        workspaceCreatedAt: new Date()
      })
    },

    setWorkspaceName: (name) => {
      const slug = createSlug(name) || get().workspaceId.slice(0, 8)
      set({
        workspaceName: name,
        workspaceTag: `workspace:${slug}`
      })
    },

    loadWorkspace: (config) => {
      set({
        workspaceId: config.id,
        workspaceName: config.name,
        workspaceTag: config.tag,
        workspaceCreatedAt: config.createdAt
      })
    },

    // ─────────────────────────────────────────────────────────────────────────
    // Sources Actions
    // ─────────────────────────────────────────────────────────────────────────

    addSource: (sourceData) => {
      const source: WorkspaceSource = {
        ...sourceData,
        id: generateWorkspaceId(),
        addedAt: new Date()
      }
      set((state) => {
        // Prevent duplicates by mediaId
        if (state.sources.some((s) => s.mediaId === source.mediaId)) {
          return state
        }
        return { sources: [...state.sources, source] }
      })
      return source
    },

    addSources: (sourcesData) => {
      const newSources: WorkspaceSource[] = sourcesData.map((s) => ({
        ...s,
        id: generateWorkspaceId(),
        addedAt: new Date()
      }))
      set((state) => {
        // Filter out duplicates by mediaId
        const existingMediaIds = new Set(state.sources.map((s) => s.mediaId))
        const uniqueNewSources = newSources.filter(
          (s) => !existingMediaIds.has(s.mediaId)
        )
        return { sources: [...state.sources, ...uniqueNewSources] }
      })
      return newSources
    },

    removeSource: (id) =>
      set((state) => ({
        sources: state.sources.filter((s) => s.id !== id),
        selectedSourceIds: state.selectedSourceIds.filter((sid) => sid !== id)
      })),

    removeSources: (ids) =>
      set((state) => {
        const idsSet = new Set(ids)
        return {
          sources: state.sources.filter((s) => !idsSet.has(s.id)),
          selectedSourceIds: state.selectedSourceIds.filter(
            (sid) => !idsSet.has(sid)
          )
        }
      }),

    toggleSourceSelection: (id) =>
      set((state) => {
        const isSelected = state.selectedSourceIds.includes(id)
        return {
          selectedSourceIds: isSelected
            ? state.selectedSourceIds.filter((sid) => sid !== id)
            : [...state.selectedSourceIds, id]
        }
      }),

    selectAllSources: () =>
      set((state) => ({
        selectedSourceIds: state.sources.map((s) => s.id)
      })),

    deselectAllSources: () => set({ selectedSourceIds: [] }),

    setSelectedSourceIds: (ids) => set({ selectedSourceIds: ids }),

    setSourceSearchQuery: (query) => set({ sourceSearchQuery: query }),

    setSourcesLoading: (loading) => set({ sourcesLoading: loading }),

    setSourcesError: (error) => set({ sourcesError: error }),

    getSelectedSources: () => {
      const state = get()
      const selectedSet = new Set(state.selectedSourceIds)
      return state.sources.filter((s) => selectedSet.has(s.id))
    },

    getSelectedMediaIds: () => {
      const state = get()
      const selectedSet = new Set(state.selectedSourceIds)
      return state.sources
        .filter((s) => selectedSet.has(s.id))
        .map((s) => s.mediaId)
    },

    // ─────────────────────────────────────────────────────────────────────────
    // Studio Actions
    // ─────────────────────────────────────────────────────────────────────────

    addArtifact: (artifactData) => {
      const artifact: GeneratedArtifact = {
        ...artifactData,
        id: generateWorkspaceId(),
        createdAt: new Date()
      }
      set((state) => ({
        generatedArtifacts: [artifact, ...state.generatedArtifacts]
      }))
      return artifact
    },

    updateArtifactStatus: (id, status, updates = {}) =>
      set((state) => ({
        generatedArtifacts: state.generatedArtifacts.map((a) =>
          a.id === id
            ? {
                ...a,
                status,
                ...updates,
                ...(status === "completed" ? { completedAt: new Date() } : {})
              }
            : a
        )
      })),

    removeArtifact: (id) =>
      set((state) => ({
        generatedArtifacts: state.generatedArtifacts.filter((a) => a.id !== id)
      })),

    clearArtifacts: () => set({ generatedArtifacts: [] }),

    setNotes: (notes) => set({ notes }),

    setIsGeneratingOutput: (isGenerating, outputType = null) =>
      set({
        isGeneratingOutput: isGenerating,
        generatingOutputType: isGenerating ? outputType : null
      }),

    // Note management actions
    setCurrentNote: (note) =>
      set({ currentNote: note || { ...DEFAULT_WORKSPACE_NOTE } }),

    updateNoteContent: (content) =>
      set((state) => ({
        currentNote: { ...state.currentNote, content, isDirty: true }
      })),

    updateNoteTitle: (title) =>
      set((state) => ({
        currentNote: { ...state.currentNote, title, isDirty: true }
      })),

    updateNoteKeywords: (keywords) =>
      set((state) => ({
        currentNote: { ...state.currentNote, keywords, isDirty: true }
      })),

    clearCurrentNote: () =>
      set({ currentNote: { ...DEFAULT_WORKSPACE_NOTE } }),

    loadNote: (note) =>
      set({
        currentNote: {
          id: note.id,
          title: note.title,
          content: note.content,
          keywords: note.keywords || [],
          version: note.version,
          isDirty: false
        }
      }),

    // ─────────────────────────────────────────────────────────────────────────
    // UI Actions
    // ─────────────────────────────────────────────────────────────────────────

    toggleLeftPane: () =>
      set((state) => ({ leftPaneCollapsed: !state.leftPaneCollapsed })),

    toggleRightPane: () =>
      set((state) => ({ rightPaneCollapsed: !state.rightPaneCollapsed })),

    setLeftPaneCollapsed: (collapsed) => set({ leftPaneCollapsed: collapsed }),

    setRightPaneCollapsed: (collapsed) =>
      set({ rightPaneCollapsed: collapsed }),

    openAddSourceModal: (tab = "upload") =>
      set({
        addSourceModalOpen: true,
        addSourceModalTab: tab,
        addSourceError: null
      }),

    closeAddSourceModal: () =>
      set({
        addSourceModalOpen: false,
        addSourceProcessing: false,
        addSourceError: null
      }),

    setAddSourceModalTab: (tab) => set({ addSourceModalTab: tab }),

    setAddSourceProcessing: (processing) =>
      set({ addSourceProcessing: processing }),

    setAddSourceError: (error) => set({ addSourceError: error }),

    // ─────────────────────────────────────────────────────────────────────────
    // Audio Settings Actions
    // ─────────────────────────────────────────────────────────────────────────

    setAudioSettings: (settings) =>
      set((state) => ({
        audioSettings: { ...state.audioSettings, ...settings }
      })),

    resetAudioSettings: () =>
      set({ audioSettings: { ...DEFAULT_AUDIO_SETTINGS } }),

    // ─────────────────────────────────────────────────────────────────────────
    // Reset Actions
    // ─────────────────────────────────────────────────────────────────────────

    reset: () => set(initialState),

    resetSources: () =>
      set({
        ...initialSourcesState
      }),

    resetStudio: () =>
      set({
        ...initialStudioState
      })
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => createWorkspaceStorage()),
      // Only persist essential state, not transient UI state
      partialize: (state): PersistedWorkspaceState => ({
        // Workspace identity
        workspaceId: state.workspaceId,
        workspaceName: state.workspaceName,
        workspaceTag: state.workspaceTag,
        workspaceCreatedAt: state.workspaceCreatedAt,

        // Sources
        sources: state.sources,
        selectedSourceIds: state.selectedSourceIds,

        // Studio outputs (note: audioUrl blobs won't survive reload, but text content will)
        generatedArtifacts: state.generatedArtifacts.map((artifact) => ({
          ...artifact,
          // Clear audioUrl since blob URLs don't persist across sessions
          audioUrl: undefined
        })),
        notes: state.notes,
        currentNote: state.currentNote,

        // Pane preferences
        leftPaneCollapsed: state.leftPaneCollapsed,
        rightPaneCollapsed: state.rightPaneCollapsed,

        // Audio generation settings
        audioSettings: state.audioSettings
      }),
      // Rehydrate dates properly and handle migration
      onRehydrateStorage: () => (state) => {
        if (state) {
          // Ensure dates are Date objects after rehydration
          if (state.workspaceCreatedAt && typeof state.workspaceCreatedAt === "string") {
            state.workspaceCreatedAt = new Date(state.workspaceCreatedAt)
          }
          state.sources = state.sources.map((source) => ({
            ...source,
            addedAt:
              typeof source.addedAt === "string"
                ? new Date(source.addedAt)
                : source.addedAt
          }))
          state.generatedArtifacts = state.generatedArtifacts.map((artifact) => ({
            ...artifact,
            createdAt:
              typeof artifact.createdAt === "string"
                ? new Date(artifact.createdAt)
                : artifact.createdAt,
            completedAt:
              artifact.completedAt && typeof artifact.completedAt === "string"
                ? new Date(artifact.completedAt)
                : artifact.completedAt
          }))
          // Migration: ensure audioSettings exists (for users with older persisted state)
          if (!state.audioSettings) {
            state.audioSettings = { ...DEFAULT_AUDIO_SETTINGS }
          }
          // Migration: ensure currentNote exists (for users with older persisted state)
          if (!state.currentNote) {
            state.currentNote = { ...DEFAULT_WORKSPACE_NOTE }
          }
        }
      }
    }
  )
)

// Expose for debugging
if (typeof window !== "undefined") {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(window as any).__tldw_useWorkspaceStore = useWorkspaceStore
}
