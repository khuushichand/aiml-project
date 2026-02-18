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
  SavedWorkspace,
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
  workspaceChatReferenceId: string
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

interface WorkspaceListState {
  savedWorkspaces: SavedWorkspace[]
  archivedWorkspaces: SavedWorkspace[]
}

interface WorkspaceSnapshot {
  workspaceId: string
  workspaceName: string
  workspaceTag: string
  workspaceCreatedAt: Date | null
  workspaceChatReferenceId: string
  sources: WorkspaceSource[]
  selectedSourceIds: string[]
  generatedArtifacts: GeneratedArtifact[]
  notes: string
  currentNote: WorkspaceNote
  leftPaneCollapsed: boolean
  rightPaneCollapsed: boolean
  audioSettings: AudioGenerationSettings
}

interface WorkspaceSnapshotsState {
  workspaceSnapshots: Record<string, WorkspaceSnapshot>
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

interface WorkspaceListActions {
  /** Save current workspace state to the saved workspaces list */
  saveCurrentWorkspace: () => void
  /** Switch to a different workspace by ID */
  switchWorkspace: (id: string) => void
  /** Create a new workspace (optionally with a name), saving current first */
  createNewWorkspace: (name?: string) => void
  /** Duplicate a workspace (defaults to current) and switch to the duplicate */
  duplicateWorkspace: (id?: string) => string | null
  /** Archive a workspace from active saved list */
  archiveWorkspace: (id: string) => void
  /** Restore a workspace from archive back into saved list */
  restoreArchivedWorkspace: (id: string) => void
  /** Delete a workspace from the saved list */
  deleteWorkspace: (id: string) => void
  /** Get the list of saved workspaces sorted by last accessed */
  getSavedWorkspaces: () => SavedWorkspace[]
  /** Get archived workspaces sorted by last accessed */
  getArchivedWorkspaces: () => SavedWorkspace[]
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
  WorkspaceListState &
  WorkspaceSnapshotsState &
  WorkspaceIdentityActions &
  SourcesActions &
  StudioActions &
  UIActions &
  AudioSettingsActions &
  WorkspaceListActions &
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
  workspaceCreatedAt: null,
  workspaceChatReferenceId: ""
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

const initialWorkspaceListState: WorkspaceListState = {
  savedWorkspaces: [],
  archivedWorkspaces: []
}

const initialWorkspaceSnapshotsState: WorkspaceSnapshotsState = {
  workspaceSnapshots: {}
}

const initialState = {
  ...initialIdentityState,
  ...initialSourcesState,
  ...initialStudioState,
  ...initialUIState,
  ...initialAudioSettingsState,
  ...initialWorkspaceListState,
  ...initialWorkspaceSnapshotsState
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
  workspaceChatReferenceId: string

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

  // Saved workspaces list
  savedWorkspaces: SavedWorkspace[]
  archivedWorkspaces: SavedWorkspace[]

  // Workspace snapshots keyed by workspace ID
  workspaceSnapshots: Record<string, WorkspaceSnapshot>
}

const MAX_SAVED_WORKSPACES = 10
const MAX_ARCHIVED_WORKSPACES = 50

const sanitizeArtifactsForPersistence = (
  artifacts: GeneratedArtifact[]
): GeneratedArtifact[] =>
  artifacts.map((artifact) => ({
    ...artifact,
    audioUrl: undefined
  }))

const reviveDateOrNull = (value: Date | string | null | undefined): Date | null => {
  if (!value) return null
  if (value instanceof Date) return value
  if (typeof value === "string") {
    const parsed = new Date(value)
    return Number.isNaN(parsed.getTime()) ? null : parsed
  }
  return null
}

const reviveDateOrUndefined = (
  value: Date | string | null | undefined
): Date | undefined => {
  const revived = reviveDateOrNull(value)
  return revived ?? undefined
}

const reviveSources = (sources: WorkspaceSource[]): WorkspaceSource[] =>
  sources.map((source) => ({
    ...source,
    addedAt: reviveDateOrNull(source.addedAt) || new Date()
  }))

const reviveArtifacts = (artifacts: GeneratedArtifact[]): GeneratedArtifact[] =>
  artifacts.map((artifact) => ({
    ...artifact,
    createdAt: reviveDateOrNull(artifact.createdAt) || new Date(),
    completedAt: reviveDateOrUndefined(artifact.completedAt)
  }))

const reviveSavedWorkspace = (workspace: SavedWorkspace): SavedWorkspace => ({
  ...workspace,
  createdAt: reviveDateOrNull(workspace.createdAt) || new Date(),
  lastAccessedAt: reviveDateOrNull(workspace.lastAccessedAt) || new Date()
})

const reviveWorkspaceSnapshot = (
  workspaceId: string,
  snapshot: WorkspaceSnapshot
): WorkspaceSnapshot => {
  const createdAt = reviveDateOrNull(snapshot.workspaceCreatedAt)
  return {
    ...snapshot,
    workspaceId: snapshot.workspaceId || workspaceId,
    workspaceCreatedAt: createdAt,
    workspaceChatReferenceId:
      snapshot.workspaceChatReferenceId ||
      snapshot.workspaceId ||
      workspaceId,
    sources: reviveSources(snapshot.sources || []),
    selectedSourceIds: snapshot.selectedSourceIds || [],
    generatedArtifacts: reviveArtifacts(snapshot.generatedArtifacts || []),
    currentNote: snapshot.currentNote || { ...DEFAULT_WORKSPACE_NOTE },
    audioSettings: snapshot.audioSettings || { ...DEFAULT_AUDIO_SETTINGS }
  }
}

const createEmptyWorkspaceSnapshot = ({
  id,
  name,
  tag,
  createdAt
}: {
  id: string
  name: string
  tag: string
  createdAt: Date
}): WorkspaceSnapshot => ({
  workspaceId: id,
  workspaceName: name,
  workspaceTag: tag,
  workspaceCreatedAt: createdAt,
  workspaceChatReferenceId: id,
  sources: [],
  selectedSourceIds: [],
  generatedArtifacts: [],
  notes: "",
  currentNote: { ...DEFAULT_WORKSPACE_NOTE },
  leftPaneCollapsed: false,
  rightPaneCollapsed: false,
  audioSettings: { ...DEFAULT_AUDIO_SETTINGS }
})

const applyWorkspaceSnapshot = (
  snapshot: WorkspaceSnapshot
): Pick<
  WorkspaceState,
  | "workspaceId"
  | "workspaceName"
  | "workspaceTag"
  | "workspaceCreatedAt"
  | "workspaceChatReferenceId"
  | "sources"
  | "selectedSourceIds"
  | "generatedArtifacts"
  | "notes"
  | "currentNote"
  | "leftPaneCollapsed"
  | "rightPaneCollapsed"
  | "audioSettings"
> => ({
  workspaceId: snapshot.workspaceId,
  workspaceName: snapshot.workspaceName,
  workspaceTag: snapshot.workspaceTag,
  workspaceCreatedAt: snapshot.workspaceCreatedAt,
  workspaceChatReferenceId: snapshot.workspaceChatReferenceId,
  sources: snapshot.sources.map((source) => ({ ...source })),
  selectedSourceIds: [...snapshot.selectedSourceIds],
  generatedArtifacts: snapshot.generatedArtifacts.map((artifact) => ({
    ...artifact
  })),
  notes: snapshot.notes,
  currentNote: { ...snapshot.currentNote },
  leftPaneCollapsed: snapshot.leftPaneCollapsed,
  rightPaneCollapsed: snapshot.rightPaneCollapsed,
  audioSettings: { ...snapshot.audioSettings }
})

const buildWorkspaceSnapshot = (state: WorkspaceState): WorkspaceSnapshot => ({
  workspaceId: state.workspaceId,
  workspaceName: state.workspaceName || "Untitled Workspace",
  workspaceTag: state.workspaceTag,
  workspaceCreatedAt: state.workspaceCreatedAt,
  workspaceChatReferenceId: state.workspaceChatReferenceId || state.workspaceId,
  sources: state.sources.map((source) => ({ ...source })),
  selectedSourceIds: [...state.selectedSourceIds],
  generatedArtifacts: state.generatedArtifacts.map((artifact) => ({
    ...artifact
  })),
  notes: state.notes,
  currentNote: { ...state.currentNote },
  leftPaneCollapsed: state.leftPaneCollapsed,
  rightPaneCollapsed: state.rightPaneCollapsed,
  audioSettings: { ...state.audioSettings }
})

const createSavedWorkspaceEntry = (
  snapshot: WorkspaceSnapshot,
  lastAccessedAt: Date = new Date()
): SavedWorkspace => ({
  id: snapshot.workspaceId,
  name: snapshot.workspaceName || "Untitled Workspace",
  tag: snapshot.workspaceTag,
  createdAt: snapshot.workspaceCreatedAt || new Date(),
  lastAccessedAt,
  sourceCount: snapshot.sources.length
})

const upsertSavedWorkspace = (
  workspaces: SavedWorkspace[],
  workspace: SavedWorkspace
): SavedWorkspace[] =>
  [workspace, ...workspaces.filter((w) => w.id !== workspace.id)].slice(
    0,
    MAX_SAVED_WORKSPACES
  )

const upsertArchivedWorkspace = (
  workspaces: SavedWorkspace[],
  workspace: SavedWorkspace
): SavedWorkspace[] =>
  [workspace, ...workspaces.filter((w) => w.id !== workspace.id)].slice(
    0,
    MAX_ARCHIVED_WORKSPACES
  )

const sortByLastAccessedDesc = (workspaces: SavedWorkspace[]): SavedWorkspace[] =>
  [...workspaces].sort(
    (a, b) =>
      new Date(b.lastAccessedAt).getTime() - new Date(a.lastAccessedAt).getTime()
  )

const createFallbackWorkspaceSnapshot = (): WorkspaceSnapshot => {
  const replacementId = generateWorkspaceId()
  const replacementName = "New Research"
  const replacementTag = `workspace:${createSlug(replacementName) || replacementId.slice(0, 8)}`
  return createEmptyWorkspaceSnapshot({
    id: replacementId,
    name: replacementName,
    tag: replacementTag,
    createdAt: new Date()
  })
}

const duplicateWorkspaceSnapshot = (
  snapshot: WorkspaceSnapshot
): WorkspaceSnapshot => {
  const duplicateId = generateWorkspaceId()
  const duplicateName = `${snapshot.workspaceName} (Copy)`
  const duplicateTag = `workspace:${createSlug(duplicateName) || duplicateId.slice(0, 8)}`
  const sourceIdMap = new Map<string, string>()

  const duplicatedSources = snapshot.sources.map((source) => {
    const nextSourceId = generateWorkspaceId()
    sourceIdMap.set(source.id, nextSourceId)
    return {
      ...source,
      id: nextSourceId,
      addedAt: reviveDateOrNull(source.addedAt) || new Date()
    }
  })

  const duplicatedSelectedSourceIds = snapshot.selectedSourceIds
    .map((sourceId) => sourceIdMap.get(sourceId))
    .filter((sourceId): sourceId is string => Boolean(sourceId))

  const duplicatedArtifacts = snapshot.generatedArtifacts.map((artifact) => ({
    ...artifact,
    id: generateWorkspaceId(),
    createdAt: reviveDateOrNull(artifact.createdAt) || new Date(),
    completedAt: reviveDateOrUndefined(artifact.completedAt)
  }))

  return {
    workspaceId: duplicateId,
    workspaceName: duplicateName,
    workspaceTag: duplicateTag,
    workspaceCreatedAt: new Date(),
    workspaceChatReferenceId: duplicateId,
    sources: duplicatedSources,
    selectedSourceIds: duplicatedSelectedSourceIds,
    generatedArtifacts: duplicatedArtifacts,
    notes: snapshot.notes,
    currentNote: {
      ...snapshot.currentNote,
      id: undefined,
      version: undefined,
      isDirty: false
    },
    leftPaneCollapsed: snapshot.leftPaneCollapsed,
    rightPaneCollapsed: snapshot.rightPaneCollapsed,
    audioSettings: { ...snapshot.audioSettings }
  }
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
      const createdAt = new Date()
      const tag = `workspace:${slug}`
      const snapshot = createEmptyWorkspaceSnapshot({
        id,
        name,
        tag,
        createdAt
      })

      set((state) => ({
        ...applyWorkspaceSnapshot(snapshot),
        savedWorkspaces: upsertSavedWorkspace(
          state.savedWorkspaces,
          createSavedWorkspaceEntry(snapshot, createdAt)
        ),
        archivedWorkspaces: state.archivedWorkspaces.filter(
          (workspace) => workspace.id !== id
        ),
        workspaceSnapshots: {
          ...state.workspaceSnapshots,
          [id]: snapshot
        }
      }))
    },

    setWorkspaceName: (name) => {
      set((state) => {
        const fallbackId = state.workspaceId || ""
        const slug = createSlug(name) || fallbackId.slice(0, 8)
        const nextTag = `workspace:${slug}`

        if (!state.workspaceId) {
          return {
            workspaceName: name,
            workspaceTag: nextTag
          }
        }

        const updatedSnapshot: WorkspaceSnapshot = {
          ...buildWorkspaceSnapshot(state),
          workspaceName: name,
          workspaceTag: nextTag
        }

        return {
          workspaceName: name,
          workspaceTag: nextTag,
          savedWorkspaces: state.savedWorkspaces.map((workspace) =>
            workspace.id === state.workspaceId
              ? { ...workspace, name, tag: nextTag }
              : workspace
          ),
          workspaceSnapshots: {
            ...state.workspaceSnapshots,
            [state.workspaceId]: updatedSnapshot
          }
        }
      })
    },

    loadWorkspace: (config) => {
      set((state) => {
        const existing = state.workspaceSnapshots[config.id]
        const snapshot =
          existing ??
          createEmptyWorkspaceSnapshot({
            id: config.id,
            name: config.name,
            tag: config.tag,
            createdAt: config.createdAt
          })

        const hydratedSnapshot: WorkspaceSnapshot = {
          ...snapshot,
          workspaceId: config.id,
          workspaceName: config.name,
          workspaceTag: config.tag,
          workspaceCreatedAt: config.createdAt,
          workspaceChatReferenceId:
            snapshot.workspaceChatReferenceId || config.id
        }

        return {
          ...applyWorkspaceSnapshot(hydratedSnapshot),
          savedWorkspaces: upsertSavedWorkspace(
            state.savedWorkspaces,
            createSavedWorkspaceEntry(hydratedSnapshot)
          ),
          archivedWorkspaces: state.archivedWorkspaces.filter(
            (workspace) => workspace.id !== config.id
          ),
          workspaceSnapshots: {
            ...state.workspaceSnapshots,
            [config.id]: hydratedSnapshot
          }
        }
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
    // Workspace List Actions
    // ─────────────────────────────────────────────────────────────────────────

    saveCurrentWorkspace: () => {
      const state = get()
      // Don't save if workspace has no ID (uninitialized)
      if (!state.workspaceId) return

      const snapshot = buildWorkspaceSnapshot(state)
      const savedWorkspace = createSavedWorkspaceEntry(snapshot)

      set((s) => {
        return {
          savedWorkspaces: upsertSavedWorkspace(
            s.savedWorkspaces,
            savedWorkspace
          ),
          archivedWorkspaces: s.archivedWorkspaces.filter(
            (workspace) => workspace.id !== savedWorkspace.id
          ),
          workspaceSnapshots: {
            ...s.workspaceSnapshots,
            [snapshot.workspaceId]: snapshot
          }
        }
      })
    },

    switchWorkspace: (id) => {
      const state = get()
      const targetWorkspace =
        state.savedWorkspaces.find((workspace) => workspace.id === id) || null
      const targetSnapshotFromState = state.workspaceSnapshots[id]
      if (!targetWorkspace && !targetSnapshotFromState) return

      const now = new Date()
      const currentSnapshot = state.workspaceId
        ? buildWorkspaceSnapshot(state)
        : null
      const targetSnapshot =
        targetSnapshotFromState ||
        createEmptyWorkspaceSnapshot({
          id,
          name: targetWorkspace?.name || "Untitled Workspace",
          tag: targetWorkspace?.tag || `workspace:${id.slice(0, 8)}`,
          createdAt: targetWorkspace?.createdAt || now
        })

      const nextSnapshots: Record<string, WorkspaceSnapshot> = {
        ...state.workspaceSnapshots,
        [targetSnapshot.workspaceId]: targetSnapshot
      }

      let nextSavedWorkspaces = state.savedWorkspaces
      if (currentSnapshot?.workspaceId) {
        nextSnapshots[currentSnapshot.workspaceId] = currentSnapshot
        nextSavedWorkspaces = upsertSavedWorkspace(
          nextSavedWorkspaces,
          createSavedWorkspaceEntry(currentSnapshot, now)
        )
      }

      nextSavedWorkspaces = upsertSavedWorkspace(
        nextSavedWorkspaces,
        createSavedWorkspaceEntry(targetSnapshot, now)
      )

      set({
        ...applyWorkspaceSnapshot(targetSnapshot),
        savedWorkspaces: nextSavedWorkspaces,
        archivedWorkspaces: state.archivedWorkspaces.filter(
          (workspace) => workspace.id !== targetSnapshot.workspaceId
        ),
        workspaceSnapshots: nextSnapshots
      })
    },

    createNewWorkspace: (name = "New Research") => {
      const state = get()
      const newId = generateWorkspaceId()
      const slug = createSlug(name) || newId.slice(0, 8)
      const createdAt = new Date()
      const tag = `workspace:${slug}`

      const newWorkspaceSnapshot = createEmptyWorkspaceSnapshot({
        id: newId,
        name,
        tag,
        createdAt
      })
      const currentSnapshot = state.workspaceId
        ? buildWorkspaceSnapshot(state)
        : null

      const nextSnapshots: Record<string, WorkspaceSnapshot> = {
        ...state.workspaceSnapshots,
        [newId]: newWorkspaceSnapshot
      }
      let nextSavedWorkspaces = state.savedWorkspaces

      if (currentSnapshot?.workspaceId) {
        nextSnapshots[currentSnapshot.workspaceId] = currentSnapshot
        nextSavedWorkspaces = upsertSavedWorkspace(
          nextSavedWorkspaces,
          createSavedWorkspaceEntry(currentSnapshot, createdAt)
        )
      }

      nextSavedWorkspaces = upsertSavedWorkspace(
        nextSavedWorkspaces,
        createSavedWorkspaceEntry(newWorkspaceSnapshot, createdAt)
      )

      set({
        ...applyWorkspaceSnapshot(newWorkspaceSnapshot),
        ...initialSourcesState,
        ...initialStudioState,
        savedWorkspaces: nextSavedWorkspaces,
        archivedWorkspaces: state.archivedWorkspaces.filter(
          (workspace) => workspace.id !== newWorkspaceSnapshot.workspaceId
        ),
        workspaceSnapshots: nextSnapshots
      })
    },

    duplicateWorkspace: (id) => {
      const state = get()
      const sourceWorkspaceId = id || state.workspaceId
      if (!sourceWorkspaceId) return null

      const currentSnapshot = state.workspaceId
        ? buildWorkspaceSnapshot(state)
        : null
      const sourceSnapshot =
        sourceWorkspaceId === state.workspaceId
          ? currentSnapshot
          : state.workspaceSnapshots[sourceWorkspaceId]
      if (!sourceSnapshot) return null

      const duplicatedSnapshot = duplicateWorkspaceSnapshot(sourceSnapshot)
      const now = new Date()
      const nextSnapshots: Record<string, WorkspaceSnapshot> = {
        ...state.workspaceSnapshots,
        [duplicatedSnapshot.workspaceId]: duplicatedSnapshot
      }
      let nextSavedWorkspaces = state.savedWorkspaces

      if (currentSnapshot?.workspaceId) {
        nextSnapshots[currentSnapshot.workspaceId] = currentSnapshot
        nextSavedWorkspaces = upsertSavedWorkspace(
          nextSavedWorkspaces,
          createSavedWorkspaceEntry(currentSnapshot, now)
        )
      }

      nextSavedWorkspaces = upsertSavedWorkspace(
        nextSavedWorkspaces,
        createSavedWorkspaceEntry(duplicatedSnapshot, now)
      )

      set({
        ...applyWorkspaceSnapshot(duplicatedSnapshot),
        savedWorkspaces: nextSavedWorkspaces,
        archivedWorkspaces: state.archivedWorkspaces.filter(
          (workspace) => workspace.id !== duplicatedSnapshot.workspaceId
        ),
        workspaceSnapshots: nextSnapshots
      })

      return duplicatedSnapshot.workspaceId
    },

    archiveWorkspace: (id) => {
      set((state) => {
        const now = new Date()
        const currentSnapshot = state.workspaceId
          ? buildWorkspaceSnapshot(state)
          : null
        const snapshotToArchive =
          id === state.workspaceId
            ? currentSnapshot
            : state.workspaceSnapshots[id]
        const savedEntry =
          state.savedWorkspaces.find((workspace) => workspace.id === id) ||
          state.archivedWorkspaces.find((workspace) => workspace.id === id) ||
          (snapshotToArchive
            ? createSavedWorkspaceEntry(snapshotToArchive, now)
            : null)

        if (!savedEntry) {
          return state
        }

        const nextSnapshots = { ...state.workspaceSnapshots }
        if (snapshotToArchive) {
          nextSnapshots[id] = snapshotToArchive
        }

        const nextSavedWorkspaces = state.savedWorkspaces.filter(
          (workspace) => workspace.id !== id
        )
        const nextArchivedWorkspaces = upsertArchivedWorkspace(
          state.archivedWorkspaces,
          {
            ...savedEntry,
            lastAccessedAt: now,
            sourceCount: snapshotToArchive
              ? snapshotToArchive.sources.length
              : savedEntry.sourceCount
          }
        )

        if (state.workspaceId !== id) {
          return {
            savedWorkspaces: nextSavedWorkspaces,
            archivedWorkspaces: nextArchivedWorkspaces,
            workspaceSnapshots: nextSnapshots
          }
        }

        if (nextSavedWorkspaces.length > 0) {
          const fallbackWorkspace = nextSavedWorkspaces[0]
          const fallbackSnapshot =
            nextSnapshots[fallbackWorkspace.id] ||
            createEmptyWorkspaceSnapshot({
              id: fallbackWorkspace.id,
              name: fallbackWorkspace.name,
              tag: fallbackWorkspace.tag,
              createdAt: fallbackWorkspace.createdAt
            })

          return {
            ...applyWorkspaceSnapshot(fallbackSnapshot),
            savedWorkspaces: upsertSavedWorkspace(
              nextSavedWorkspaces,
              createSavedWorkspaceEntry(fallbackSnapshot, now)
            ),
            archivedWorkspaces: nextArchivedWorkspaces,
            workspaceSnapshots: {
              ...nextSnapshots,
              [fallbackSnapshot.workspaceId]: fallbackSnapshot
            }
          }
        }

        const replacementSnapshot = createFallbackWorkspaceSnapshot()
        return {
          ...applyWorkspaceSnapshot(replacementSnapshot),
          savedWorkspaces: [createSavedWorkspaceEntry(replacementSnapshot, now)],
          archivedWorkspaces: nextArchivedWorkspaces,
          workspaceSnapshots: {
            ...nextSnapshots,
            [replacementSnapshot.workspaceId]: replacementSnapshot
          }
        }
      })
    },

    restoreArchivedWorkspace: (id) => {
      set((state) => {
        const archivedWorkspace = state.archivedWorkspaces.find(
          (workspace) => workspace.id === id
        )
        if (!archivedWorkspace) {
          return state
        }

        const snapshot =
          state.workspaceSnapshots[id] ||
          createEmptyWorkspaceSnapshot({
            id: archivedWorkspace.id,
            name: archivedWorkspace.name,
            tag: archivedWorkspace.tag,
            createdAt: archivedWorkspace.createdAt
          })
        const now = new Date()

        return {
          savedWorkspaces: upsertSavedWorkspace(
            state.savedWorkspaces,
            createSavedWorkspaceEntry(snapshot, now)
          ),
          archivedWorkspaces: state.archivedWorkspaces.filter(
            (workspace) => workspace.id !== id
          ),
          workspaceSnapshots: {
            ...state.workspaceSnapshots,
            [snapshot.workspaceId]: snapshot
          }
        }
      })
    },

    deleteWorkspace: (id) => {
      set((state) => {
        const nextSavedWorkspaces = state.savedWorkspaces.filter(
          (workspace) => workspace.id !== id
        )
        const nextArchivedWorkspaces = state.archivedWorkspaces.filter(
          (workspace) => workspace.id !== id
        )
        const { [id]: _removedWorkspace, ...remainingSnapshots } =
          state.workspaceSnapshots

        if (state.workspaceId !== id) {
          return {
            savedWorkspaces: nextSavedWorkspaces,
            archivedWorkspaces: nextArchivedWorkspaces,
            workspaceSnapshots: remainingSnapshots
          }
        }

        if (nextSavedWorkspaces.length > 0) {
          const fallbackWorkspace = nextSavedWorkspaces[0]
          const fallbackSnapshot =
            remainingSnapshots[fallbackWorkspace.id] ||
            createEmptyWorkspaceSnapshot({
              id: fallbackWorkspace.id,
              name: fallbackWorkspace.name,
              tag: fallbackWorkspace.tag,
              createdAt: fallbackWorkspace.createdAt
            })

          return {
            ...applyWorkspaceSnapshot(fallbackSnapshot),
            savedWorkspaces: upsertSavedWorkspace(
              nextSavedWorkspaces,
              createSavedWorkspaceEntry(fallbackSnapshot, new Date())
            ),
            archivedWorkspaces: nextArchivedWorkspaces,
            workspaceSnapshots: {
              ...remainingSnapshots,
              [fallbackSnapshot.workspaceId]: fallbackSnapshot
            }
          }
        }

        const replacementSnapshot = createFallbackWorkspaceSnapshot()

        return {
          ...applyWorkspaceSnapshot(replacementSnapshot),
          savedWorkspaces: [createSavedWorkspaceEntry(replacementSnapshot)],
          archivedWorkspaces: nextArchivedWorkspaces,
          workspaceSnapshots: {
            ...remainingSnapshots,
            [replacementSnapshot.workspaceId]: replacementSnapshot
          }
        }
      })
    },

    getSavedWorkspaces: () => {
      const state = get()
      return sortByLastAccessedDesc(state.savedWorkspaces)
    },

    getArchivedWorkspaces: () => {
      const state = get()
      return sortByLastAccessedDesc(state.archivedWorkspaces)
    },

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
      partialize: (state): PersistedWorkspaceState => {
        const nextSnapshots = { ...state.workspaceSnapshots }
        if (state.workspaceId) {
          nextSnapshots[state.workspaceId] = buildWorkspaceSnapshot(state)
        }

        const persistedSnapshots: Record<string, WorkspaceSnapshot> = {}
        for (const [workspaceId, snapshot] of Object.entries(nextSnapshots)) {
          persistedSnapshots[workspaceId] = {
            ...snapshot,
            generatedArtifacts: sanitizeArtifactsForPersistence(
              snapshot.generatedArtifacts
            )
          }
        }

        return {
          // Workspace identity
          workspaceId: state.workspaceId,
          workspaceName: state.workspaceName,
          workspaceTag: state.workspaceTag,
          workspaceCreatedAt: state.workspaceCreatedAt,
          workspaceChatReferenceId:
            state.workspaceChatReferenceId || state.workspaceId,

          // Sources
          sources: state.sources,
          selectedSourceIds: state.selectedSourceIds,

          // Studio outputs (note: audioUrl blobs won't survive reload, but text content will)
          generatedArtifacts: sanitizeArtifactsForPersistence(
            state.generatedArtifacts
          ),
          notes: state.notes,
          currentNote: state.currentNote,

          // Pane preferences
          leftPaneCollapsed: state.leftPaneCollapsed,
          rightPaneCollapsed: state.rightPaneCollapsed,

          // Audio generation settings
          audioSettings: state.audioSettings,

          // Saved workspaces list
          savedWorkspaces: state.savedWorkspaces,
          archivedWorkspaces: state.archivedWorkspaces,

          // Workspace snapshots
          workspaceSnapshots: persistedSnapshots
        }
      },
      // Rehydrate dates properly and handle migration
      onRehydrateStorage: () => (state) => {
        if (state) {
          // Ensure dates are Date objects after rehydration
          state.workspaceCreatedAt = reviveDateOrNull(state.workspaceCreatedAt)
          state.sources = reviveSources(state.sources || [])
          state.generatedArtifacts = reviveArtifacts(state.generatedArtifacts || [])

          // Migration: ensure optional fields exist
          if (!state.audioSettings) {
            state.audioSettings = { ...DEFAULT_AUDIO_SETTINGS }
          }
          if (!state.currentNote) {
            state.currentNote = { ...DEFAULT_WORKSPACE_NOTE }
          }
          if (!state.workspaceChatReferenceId) {
            state.workspaceChatReferenceId = state.workspaceId || ""
          }

          // Migration: ensure savedWorkspaces exists and dates are properly converted
          state.savedWorkspaces = (state.savedWorkspaces || []).map(
            reviveSavedWorkspace
          )
          state.archivedWorkspaces = (state.archivedWorkspaces || []).map(
            reviveSavedWorkspace
          )

          // Migration: ensure workspace snapshots exist and are hydrated
          const rawSnapshots = state.workspaceSnapshots || {}
          const hydratedSnapshots: Record<string, WorkspaceSnapshot> = {}
          for (const [workspaceId, snapshot] of Object.entries(rawSnapshots)) {
            hydratedSnapshots[workspaceId] = reviveWorkspaceSnapshot(
              workspaceId,
              snapshot
            )
          }
          state.workspaceSnapshots = hydratedSnapshots

          // Ensure active workspace snapshot exists and use it as canonical source
          if (state.workspaceId) {
            const activeSnapshot =
              state.workspaceSnapshots[state.workspaceId] ||
              createEmptyWorkspaceSnapshot({
                id: state.workspaceId,
                name: state.workspaceName || "Untitled Workspace",
                tag:
                  state.workspaceTag ||
                  `workspace:${state.workspaceId.slice(0, 8)}`,
                createdAt: state.workspaceCreatedAt || new Date()
              })

            state.workspaceSnapshots[state.workspaceId] = activeSnapshot
            Object.assign(state, applyWorkspaceSnapshot(activeSnapshot))

            state.savedWorkspaces = upsertSavedWorkspace(
              state.savedWorkspaces,
              createSavedWorkspaceEntry(activeSnapshot)
            )
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
