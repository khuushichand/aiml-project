import { beforeEach, describe, expect, it } from "vitest"
import {
  DEFAULT_AUDIO_SETTINGS,
  DEFAULT_WORKSPACE_NOTE
} from "@/types/workspace"
import {
  WORKSPACE_STORAGE_KEY,
  WORKSPACE_STORAGE_QUOTA_EVENT,
  type WorkspaceStorageQuotaEventDetail
} from "@/store/workspace-events"
import {
  createWorkspaceStorage,
  estimateWorkspacePersistenceMetrics,
  useWorkspaceStore
} from "../workspace"

const STORAGE_KEY = WORKSPACE_STORAGE_KEY

const resetWorkspaceStore = () => {
  localStorage.removeItem(STORAGE_KEY)
  delete window.__tldwWorkspacePersistenceMetrics
  useWorkspaceStore.setState({
    workspaceId: "",
    workspaceName: "",
    workspaceTag: "",
    workspaceCreatedAt: null,
    workspaceChatReferenceId: "",
    sources: [],
    selectedSourceIds: [],
    sourceSearchQuery: "",
    sourceFocusTarget: null,
    sourcesLoading: false,
    sourcesError: null,
    generatedArtifacts: [],
    notes: "",
    currentNote: { ...DEFAULT_WORKSPACE_NOTE },
    isGeneratingOutput: false,
    generatingOutputType: null,
    storeHydrated: false,
    leftPaneCollapsed: false,
    rightPaneCollapsed: false,
    addSourceModalOpen: false,
    addSourceModalTab: "upload",
    addSourceProcessing: false,
    addSourceError: null,
    chatFocusTarget: null,
    noteFocusTarget: null,
    audioSettings: { ...DEFAULT_AUDIO_SETTINGS },
    savedWorkspaces: [],
    archivedWorkspaces: [],
    workspaceSnapshots: {},
    workspaceChatSessions: {}
  })
}

describe("workspace store snapshot persistence", () => {
  beforeEach(async () => {
    resetWorkspaceStore()
    if (useWorkspaceStore.persist?.clearStorage) {
      await useWorkspaceStore.persist.clearStorage()
    }
  })

  it("saves and restores workspace-specific state when switching", () => {
    useWorkspaceStore.getState().initializeWorkspace("Workspace Alpha")
    const alphaId = useWorkspaceStore.getState().workspaceId
    const alphaChatReferenceId = useWorkspaceStore.getState().workspaceChatReferenceId

    useWorkspaceStore
      .getState()
      .addSource({ mediaId: 101, title: "Alpha Source", type: "pdf" })
    useWorkspaceStore
      .getState()
      .addArtifact({
        type: "summary",
        title: "Alpha Summary",
        status: "completed",
        content: "Alpha content"
      })
    useWorkspaceStore.setState({
      notes: "Alpha notes",
      currentNote: {
        id: 1,
        title: "Alpha Note",
        content: "Alpha note content",
        keywords: ["alpha"],
        version: 2,
        isDirty: false
      },
      leftPaneCollapsed: true,
      rightPaneCollapsed: false
    })
    useWorkspaceStore.getState().saveCurrentWorkspace()

    useWorkspaceStore.getState().createNewWorkspace("Workspace Beta")
    const betaId = useWorkspaceStore.getState().workspaceId
    const betaChatReferenceId = useWorkspaceStore.getState().workspaceChatReferenceId

    useWorkspaceStore
      .getState()
      .addSource({ mediaId: 202, title: "Beta Source", type: "video" })
    useWorkspaceStore
      .getState()
      .addArtifact({
        type: "report",
        title: "Beta Report",
        status: "completed",
        content: "Beta content"
      })
    useWorkspaceStore.setState({
      notes: "Beta notes",
      currentNote: {
        id: 2,
        title: "Beta Note",
        content: "Beta note content",
        keywords: ["beta"],
        version: 1,
        isDirty: false
      },
      leftPaneCollapsed: false,
      rightPaneCollapsed: true
    })
    useWorkspaceStore.getState().saveCurrentWorkspace()

    useWorkspaceStore.getState().createNewWorkspace("Workspace Gamma")
    const gammaId = useWorkspaceStore.getState().workspaceId

    useWorkspaceStore
      .getState()
      .addSource({ mediaId: 303, title: "Gamma Source", type: "audio" })
    useWorkspaceStore.setState({
      notes: "Gamma notes",
      leftPaneCollapsed: true,
      rightPaneCollapsed: true
    })
    useWorkspaceStore.getState().saveCurrentWorkspace()

    useWorkspaceStore.getState().switchWorkspace(alphaId)
    let state = useWorkspaceStore.getState()
    expect(state.workspaceName).toBe("Workspace Alpha")
    expect(state.workspaceChatReferenceId).toBe(alphaChatReferenceId)
    expect(state.sources).toHaveLength(1)
    expect(state.sources[0]?.title).toBe("Alpha Source")
    expect(state.generatedArtifacts[0]?.title).toBe("Alpha Summary")
    expect(state.notes).toBe("Alpha notes")
    expect(state.leftPaneCollapsed).toBe(true)
    expect(state.rightPaneCollapsed).toBe(false)

    useWorkspaceStore.getState().switchWorkspace(betaId)
    state = useWorkspaceStore.getState()
    expect(state.workspaceName).toBe("Workspace Beta")
    expect(state.workspaceChatReferenceId).toBe(betaChatReferenceId)
    expect(state.sources).toHaveLength(1)
    expect(state.sources[0]?.title).toBe("Beta Source")
    expect(state.generatedArtifacts[0]?.title).toBe("Beta Report")
    expect(state.notes).toBe("Beta notes")
    expect(state.leftPaneCollapsed).toBe(false)
    expect(state.rightPaneCollapsed).toBe(true)

    useWorkspaceStore.getState().switchWorkspace(gammaId)
    state = useWorkspaceStore.getState()
    expect(state.workspaceName).toBe("Workspace Gamma")
    expect(state.sources).toHaveLength(1)
    expect(state.sources[0]?.title).toBe("Gamma Source")
    expect(state.notes).toBe("Gamma notes")
    expect(state.leftPaneCollapsed).toBe(true)
    expect(state.rightPaneCollapsed).toBe(true)

    expect(Object.keys(state.workspaceSnapshots)).toEqual(
      expect.arrayContaining([alphaId, betaId, gammaId])
    )
  })

  it("creates isolated snapshots for new workspaces", () => {
    useWorkspaceStore.getState().initializeWorkspace("Workspace One")
    const workspaceOneId = useWorkspaceStore.getState().workspaceId

    useWorkspaceStore
      .getState()
      .addSource({ mediaId: 404, title: "Workspace One Source", type: "document" })
    useWorkspaceStore.setState({ notes: "Workspace One Notes" })

    useWorkspaceStore.getState().createNewWorkspace("Workspace Two")
    const state = useWorkspaceStore.getState()
    const workspaceTwoId = state.workspaceId

    expect(state.sources).toHaveLength(0)
    expect(state.notes).toBe("")
    expect(state.workspaceSnapshots[workspaceOneId]?.sources).toHaveLength(1)
    expect(state.workspaceSnapshots[workspaceOneId]?.notes).toBe(
      "Workspace One Notes"
    )
    expect(state.workspaceSnapshots[workspaceTwoId]?.sources).toHaveLength(0)
  })

  it("rehydrates from active workspace snapshot and restores pane state", async () => {
    resetWorkspaceStore()

    const persistedState = {
      state: {
        workspaceId: "workspace-rehydrate",
        workspaceName: "Top Level Name",
        workspaceTag: "workspace:top-level",
        workspaceCreatedAt: "2026-02-01T00:00:00.000Z",
        workspaceChatReferenceId: "top-level-chat-ref",
        sources: [],
        selectedSourceIds: [],
        generatedArtifacts: [],
        notes: "",
        currentNote: { ...DEFAULT_WORKSPACE_NOTE },
        leftPaneCollapsed: false,
        rightPaneCollapsed: false,
        audioSettings: { ...DEFAULT_AUDIO_SETTINGS },
        savedWorkspaces: [],
        archivedWorkspaces: [],
        workspaceSnapshots: {
          "workspace-rehydrate": {
            workspaceId: "workspace-rehydrate",
            workspaceName: "Snapshot Name",
            workspaceTag: "workspace:snapshot-name",
            workspaceCreatedAt: "2026-02-02T00:00:00.000Z",
            workspaceChatReferenceId: "snapshot-chat-ref",
            sources: [
              {
                id: "source-snapshot-1",
                mediaId: 9001,
                title: "Snapshot Source",
                type: "pdf",
                addedAt: "2026-02-03T00:00:00.000Z"
              }
            ],
            selectedSourceIds: ["source-snapshot-1"],
            generatedArtifacts: [
              {
                id: "artifact-snapshot-1",
                type: "summary",
                title: "Snapshot Artifact",
                status: "completed",
                content: "Snapshot content",
                createdAt: "2026-02-04T00:00:00.000Z"
              }
            ],
            notes: "Snapshot Notes",
            currentNote: {
              id: 99,
              title: "Snapshot Note",
              content: "Snapshot note content",
              keywords: ["snapshot"],
              version: 3,
              isDirty: false
            },
            leftPaneCollapsed: true,
            rightPaneCollapsed: true,
            audioSettings: {
              ...DEFAULT_AUDIO_SETTINGS,
              speed: 1.25
            }
          }
        },
        workspaceChatSessions: {
          "workspace-rehydrate": {
            messages: [
              {
                isBot: false,
                name: "You",
                message: "Saved workspace message",
                sources: []
              }
            ],
            history: [{ role: "user", content: "Saved workspace message" }],
            historyId: "history-123",
            serverChatId: "server-chat-123"
          }
        }
      },
      version: 0
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(persistedState))
    await useWorkspaceStore.persist.rehydrate()

    const state = useWorkspaceStore.getState()
    expect(state.workspaceId).toBe("workspace-rehydrate")
    expect(state.workspaceName).toBe("Snapshot Name")
    expect(state.workspaceTag).toBe("workspace:snapshot-name")
    expect(state.workspaceChatReferenceId).toBe("snapshot-chat-ref")
    expect(state.workspaceCreatedAt).toBeInstanceOf(Date)
    expect(state.sources[0]?.addedAt).toBeInstanceOf(Date)
    expect(state.generatedArtifacts[0]?.createdAt).toBeInstanceOf(Date)
    expect(state.leftPaneCollapsed).toBe(true)
    expect(state.rightPaneCollapsed).toBe(true)
    expect(state.sources).toHaveLength(1)
    expect(state.sources[0]?.title).toBe("Snapshot Source")
    expect(state.generatedArtifacts).toHaveLength(1)
    expect(state.generatedArtifacts[0]?.title).toBe("Snapshot Artifact")
    expect(state.notes).toBe("Snapshot Notes")
    expect(state.savedWorkspaces.some((workspace) => workspace.id === state.workspaceId)).toBe(
      true
    )
    expect(state.workspaceChatSessions["workspace-rehydrate"]?.historyId).toBe(
      "history-123"
    )
    expect(state.storeHydrated).toBe(true)
  })

  it("marks interrupted generating artifacts as failed during rehydration", async () => {
    resetWorkspaceStore()

    const persistedState = {
      state: {
        workspaceId: "workspace-interrupted",
        workspaceName: "Interrupted Workspace",
        workspaceTag: "workspace:interrupted",
        workspaceCreatedAt: "2026-02-10T00:00:00.000Z",
        workspaceChatReferenceId: "workspace-interrupted",
        sources: [],
        selectedSourceIds: [],
        generatedArtifacts: [
          {
            id: "top-level-generating",
            type: "summary",
            title: "Top-level generation",
            status: "generating",
            content: "Pending...",
            createdAt: "2026-02-10T01:00:00.000Z"
          }
        ],
        notes: "",
        currentNote: { ...DEFAULT_WORKSPACE_NOTE },
        leftPaneCollapsed: false,
        rightPaneCollapsed: false,
        audioSettings: { ...DEFAULT_AUDIO_SETTINGS },
        savedWorkspaces: [],
        archivedWorkspaces: [],
        workspaceSnapshots: {
          "workspace-interrupted": {
            workspaceId: "workspace-interrupted",
            workspaceName: "Interrupted Workspace",
            workspaceTag: "workspace:interrupted",
            workspaceCreatedAt: "2026-02-10T00:00:00.000Z",
            workspaceChatReferenceId: "workspace-interrupted",
            sources: [],
            selectedSourceIds: [],
            generatedArtifacts: [
              {
                id: "snapshot-generating",
                type: "report",
                title: "Snapshot generation",
                status: "generating",
                content: "Pending...",
                createdAt: "2026-02-10T02:00:00.000Z"
              }
            ],
            notes: "",
            currentNote: { ...DEFAULT_WORKSPACE_NOTE },
            leftPaneCollapsed: false,
            rightPaneCollapsed: false,
            audioSettings: { ...DEFAULT_AUDIO_SETTINGS }
          }
        },
        workspaceChatSessions: {}
      },
      version: 0
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(persistedState))
    await useWorkspaceStore.persist.rehydrate()

    const state = useWorkspaceStore.getState()
    expect(state.generatedArtifacts[0]?.status).toBe("failed")
    expect(state.generatedArtifacts[0]?.errorMessage).toContain(
      "Generation was interrupted"
    )
    expect(
      state.workspaceSnapshots["workspace-interrupted"]?.generatedArtifacts[0]
        ?.status
    ).toBe("failed")
  })

  it("uses a raw localStorage adapter without parse/stringify in getItem", () => {
    const storage = createWorkspaceStorage()
    const testKey = "workspace-storage-adapter-test"
    const rawPayload = '{"state":{"workspaceCreatedAt":"2026-02-01T00:00:00.000Z"}}'

    storage.setItem(testKey, rawPayload)
    expect(storage.getItem(testKey)).toBe(rawPayload)

    storage.removeItem(testKey)
    expect(storage.getItem(testKey)).toBeNull()
  })

  it("estimates persistence payload section sizes", () => {
    const metrics = estimateWorkspacePersistenceMetrics({
      state: {
        workspaceId: "workspace-metrics",
        workspaceName: "Metrics Workspace",
        workspaceTag: "workspace:metrics",
        workspaceCreatedAt: "2026-02-10T00:00:00.000Z",
        workspaceChatReferenceId: "workspace-metrics",
        sources: [
          {
            id: "source-1",
            mediaId: 1,
            title: "Source One",
            type: "pdf",
            addedAt: "2026-02-10T00:00:00.000Z"
          }
        ],
        selectedSourceIds: ["source-1"],
        generatedArtifacts: [
          {
            id: "artifact-1",
            type: "summary",
            title: "Artifact One",
            status: "completed",
            content: "summary",
            createdAt: "2026-02-10T00:00:00.000Z"
          }
        ],
        notes: "workspace notes",
        currentNote: { ...DEFAULT_WORKSPACE_NOTE },
        leftPaneCollapsed: false,
        rightPaneCollapsed: false,
        audioSettings: { ...DEFAULT_AUDIO_SETTINGS },
        savedWorkspaces: [],
        archivedWorkspaces: [],
        workspaceSnapshots: {
          "workspace-metrics": {
            workspaceId: "workspace-metrics",
            workspaceName: "Metrics Workspace",
            workspaceTag: "workspace:metrics",
            workspaceCreatedAt: "2026-02-10T00:00:00.000Z",
            workspaceChatReferenceId: "workspace-metrics",
            sources: [],
            selectedSourceIds: [],
            generatedArtifacts: [],
            notes: "",
            currentNote: { ...DEFAULT_WORKSPACE_NOTE },
            leftPaneCollapsed: false,
            rightPaneCollapsed: false,
            audioSettings: { ...DEFAULT_AUDIO_SETTINGS }
          }
        },
        workspaceChatSessions: {
          "workspace-metrics": {
            messages: [
              {
                isBot: false,
                name: "You",
                message: "hello",
                sources: []
              }
            ],
            history: [{ role: "user", content: "hello" }],
            historyId: "history-1",
            serverChatId: null
          }
        }
      },
      version: 0
    })

    expect(metrics.totalBytes).toBeGreaterThan(0)
    expect(metrics.sections.workspaceSnapshots).toBeGreaterThan(0)
    expect(metrics.sections.workspaceChatSessions).toBeGreaterThan(0)
    expect(metrics.sections.generatedArtifacts).toBeGreaterThan(0)
    expect(metrics.sections.notes).toBeGreaterThan(0)
    expect(metrics.sections.sources).toBeGreaterThan(0)
    expect(metrics.sections.selectedSourceIds).toBeGreaterThan(0)
    expect(metrics.sections.other).toBeGreaterThanOrEqual(0)
  })

  it("records workspace persistence diagnostics on persisted writes", () => {
    const previousWriteCount =
      window.__tldwWorkspacePersistenceMetrics?.writeCount ?? 0

    useWorkspaceStore.getState().initializeWorkspace("Diagnostics Workspace")
    useWorkspaceStore.getState().setNotes("Diagnostics notes")

    const diagnostics = window.__tldwWorkspacePersistenceMetrics
    expect(diagnostics?.key).toBe(STORAGE_KEY)
    expect((diagnostics?.writeCount ?? 0) - previousWriteCount).toBeGreaterThan(0)
    expect(diagnostics?.totalBytes ?? 0).toBeGreaterThan(0)
    expect(diagnostics?.maxTotalBytes ?? 0).toBeGreaterThan(0)
    expect(diagnostics?.sections.workspaceSnapshots ?? 0).toBeGreaterThan(0)
    expect(diagnostics?.updatedAt ?? 0).toBeGreaterThan(0)
  })

  it("rehydrates array-shaped legacy snapshots and chat sessions safely", async () => {
    resetWorkspaceStore()

    const persistedState = {
      state: {
        workspaceId: "workspace-legacy",
        workspaceName: "Legacy Top Level Name",
        workspaceTag: "workspace:legacy-top",
        workspaceCreatedAt: "2026-02-01T00:00:00.000Z",
        workspaceChatReferenceId: "workspace-legacy",
        sources: { invalid: true },
        selectedSourceIds: "invalid",
        generatedArtifacts: "invalid",
        notes: "",
        currentNote: null,
        leftPaneCollapsed: false,
        rightPaneCollapsed: false,
        audioSettings: null,
        savedWorkspaces: "invalid",
        archivedWorkspaces: null,
        workspaceSnapshots: [
          {
            id: "workspace-legacy",
            workspaceName: "Legacy Snapshot Name",
            workspaceTag: "workspace:legacy",
            workspaceCreatedAt: "2026-02-02T00:00:00.000Z",
            workspaceChatReferenceId: "legacy-chat-ref",
            sources: [
              {
                id: "source-legacy-1",
                mediaId: 999,
                title: "Legacy Source",
                type: "pdf",
                addedAt: "2026-02-03T00:00:00.000Z"
              }
            ],
            selectedSourceIds: ["source-legacy-1"],
            generatedArtifacts: [],
            notes: "Legacy snapshot note",
            currentNote: { ...DEFAULT_WORKSPACE_NOTE },
            leftPaneCollapsed: true,
            rightPaneCollapsed: false,
            audioSettings: { ...DEFAULT_AUDIO_SETTINGS }
          }
        ],
        workspaceChatSessions: [
          {
            workspaceId: "workspace-legacy",
            session: {
              messages: [
                {
                  isBot: false,
                  name: "You",
                  message: "Legacy hello",
                  sources: []
                }
              ],
              history: "invalid-history",
              historyId: "legacy-history",
              serverChatId: null
            }
          },
          {
            workspaceId: "workspace-empty-session",
            session: {
              messages: [],
              history: [],
              historyId: null,
              serverChatId: null
            }
          }
        ]
      },
      version: 0
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(persistedState))
    await useWorkspaceStore.persist.rehydrate()

    const state = useWorkspaceStore.getState()
    expect(state.workspaceId).toBe("workspace-legacy")
    expect(state.workspaceName).toBe("Legacy Snapshot Name")
    expect(state.workspaceTag).toBe("workspace:legacy")
    expect(state.workspaceChatReferenceId).toBe("legacy-chat-ref")
    expect(state.sources).toHaveLength(1)
    expect(state.sources[0]?.title).toBe("Legacy Source")
    expect(state.selectedSourceIds).toEqual(["source-legacy-1"])
    expect(state.notes).toBe("Legacy snapshot note")
    expect(state.leftPaneCollapsed).toBe(true)
    expect(state.rightPaneCollapsed).toBe(false)
    expect(state.workspaceSnapshots["workspace-legacy"]).toBeDefined()
    expect(state.workspaceSnapshots["workspace-legacy"]?.workspaceName).toBe(
      "Legacy Snapshot Name"
    )
    expect(
      state.workspaceChatSessions["workspace-legacy"]?.history[0]?.content
    ).toBe("Legacy hello")
    expect(
      state.workspaceChatSessions["workspace-empty-session"]
    ).toBeUndefined()
  })

  it("persists snapshot-first schema with messages-only chat sessions", () => {
    useWorkspaceStore.getState().initializeWorkspace("Snapshot Canonical Workspace")
    const workspaceId = useWorkspaceStore.getState().workspaceId

    const source = useWorkspaceStore
      .getState()
      .addSource({ mediaId: 5001, title: "Canonical Source", type: "pdf" })
    useWorkspaceStore.getState().setSelectedSourceIds([source.id])
    useWorkspaceStore
      .getState()
      .addArtifact({
        type: "summary",
        title: "Canonical Artifact",
        status: "completed",
        content: "Canonical content"
      })
    useWorkspaceStore.setState({
      notes: "Canonical notes",
      currentNote: {
        ...DEFAULT_WORKSPACE_NOTE,
        title: "Canonical note title",
        content: "Canonical note content"
      }
    })
    useWorkspaceStore.getState().saveWorkspaceChatSession(workspaceId, {
      messages: [
        {
          isBot: false,
          name: "You",
          message: "Persist canonical",
          sources: []
        }
      ],
      history: [{ role: "user", content: "Persist canonical" }],
      historyId: "canonical-history",
      serverChatId: "canonical-chat"
    })

    const splitIndexRaw = localStorage.getItem(STORAGE_KEY)
    expect(splitIndexRaw).toBeTruthy()

    const splitIndex = splitIndexRaw ? JSON.parse(splitIndexRaw) : null
    expect(splitIndex?.schema).toBe("workspace_split_v1")
    expect(Array.isArray(splitIndex?.state?.workspaceIds)).toBe(true)
    expect(splitIndex?.state?.workspaceIds).toContain(workspaceId)
    expect(splitIndex?.state?.workspaceName).toBeUndefined()
    expect(splitIndex?.state?.sources).toBeUndefined()
    expect(splitIndex?.state?.selectedSourceIds).toBeUndefined()
    expect(splitIndex?.state?.generatedArtifacts).toBeUndefined()
    expect(splitIndex?.state?.notes).toBeUndefined()
    expect(splitIndex?.state?.currentNote).toBeUndefined()
    expect(splitIndex?.state?.audioSettings).toBeUndefined()

    const reconstructedRaw = createWorkspaceStorage().getItem(STORAGE_KEY)
    const reconstructed = reconstructedRaw ? JSON.parse(reconstructedRaw) : null
    const persistedState = reconstructed?.state as Record<string, unknown>
    expect(persistedState.workspaceId).toBe(workspaceId)
    expect(persistedState.workspaceSnapshots).toBeDefined()
    expect(persistedState.workspaceChatSessions).toBeDefined()

    const persistedSnapshot = (persistedState.workspaceSnapshots as Record<string, any>)[
      workspaceId
    ]
    expect(persistedSnapshot?.sources?.[0]?.title).toBe("Canonical Source")
    expect(persistedSnapshot?.selectedSourceIds).toEqual([source.id])
    expect(persistedSnapshot?.generatedArtifacts?.[0]?.title).toBe(
      "Canonical Artifact"
    )
    expect(persistedSnapshot?.notes).toBe("Canonical notes")
    expect(persistedSnapshot?.currentNote?.title).toBe("Canonical note title")

    const persistedSession = (
      persistedState.workspaceChatSessions as Record<string, any>
    )[workspaceId]
    expect(persistedSession?.messages?.[0]?.message).toBe("Persist canonical")
    expect(persistedSession?.historyId).toBe("canonical-history")
    expect(persistedSession?.serverChatId).toBe("canonical-chat")
    expect(persistedSession?.history).toBeUndefined()
  })

  it("rehydrates messages-only chat sessions and derives history", async () => {
    resetWorkspaceStore()

    const persistedState = {
      state: {
        workspaceId: "workspace-messages-only",
        savedWorkspaces: [],
        archivedWorkspaces: [],
        workspaceSnapshots: {
          "workspace-messages-only": {
            workspaceId: "workspace-messages-only",
            workspaceName: "Messages Only Workspace",
            workspaceTag: "workspace:messages-only",
            workspaceCreatedAt: "2026-02-16T00:00:00.000Z",
            workspaceChatReferenceId: "workspace-messages-only",
            sources: [],
            selectedSourceIds: [],
            generatedArtifacts: [],
            notes: "",
            currentNote: { ...DEFAULT_WORKSPACE_NOTE },
            leftPaneCollapsed: false,
            rightPaneCollapsed: false,
            audioSettings: { ...DEFAULT_AUDIO_SETTINGS }
          }
        },
        workspaceChatSessions: {
          "workspace-messages-only": {
            messages: [
              {
                isBot: false,
                name: "You",
                message: "Hello from messages-only session",
                sources: []
              }
            ],
            historyId: "messages-only-history",
            serverChatId: "messages-only-chat"
          }
        }
      },
      version: 1
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(persistedState))
    await useWorkspaceStore.persist.rehydrate()

    const session = useWorkspaceStore
      .getState()
      .getWorkspaceChatSession("workspace-messages-only")
    expect(session?.messages[0]?.message).toBe("Hello from messages-only session")
    expect(session?.history[0]?.content).toBe("Hello from messages-only session")
    expect(session?.history[0]?.role).toBe("user")
    expect(session?.historyId).toBe("messages-only-history")
    expect(session?.serverChatId).toBe("messages-only-chat")
  })

  it("migrates legacy top-level persisted state without snapshots", async () => {
    resetWorkspaceStore()

    const persistedState = {
      state: {
        workspaceId: "workspace-legacy-top-level",
        workspaceName: "Legacy Top-Level Workspace",
        workspaceTag: "workspace:legacy-top-level",
        workspaceCreatedAt: "2026-02-18T00:00:00.000Z",
        workspaceChatReferenceId: "legacy-top-level-chat",
        sources: [
          {
            id: "legacy-source-1",
            mediaId: 4321,
            title: "Legacy Top-Level Source",
            type: "pdf",
            addedAt: "2026-02-18T00:01:00.000Z"
          }
        ],
        selectedSourceIds: ["legacy-source-1"],
        generatedArtifacts: [
          {
            id: "legacy-artifact-1",
            type: "summary",
            title: "Legacy Top-Level Artifact",
            status: "completed",
            content: "Legacy artifact content",
            createdAt: "2026-02-18T00:02:00.000Z"
          }
        ],
        notes: "Legacy top-level notes",
        currentNote: {
          id: 7,
          title: "Legacy note",
          content: "Legacy note content",
          keywords: ["legacy"],
          version: 1,
          isDirty: false
        },
        leftPaneCollapsed: true,
        rightPaneCollapsed: false,
        audioSettings: { ...DEFAULT_AUDIO_SETTINGS, speed: 1.1 },
        savedWorkspaces: [],
        archivedWorkspaces: [],
        workspaceChatSessions: {
          "workspace-legacy-top-level": {
            messages: [
              {
                isBot: false,
                name: "You",
                message: "Legacy session message",
                sources: []
              }
            ],
            history: [{ role: "user", content: "Legacy session message" }],
            historyId: "legacy-top-history",
            serverChatId: null
          }
        }
      },
      version: 0
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(persistedState))
    await useWorkspaceStore.persist.rehydrate()

    const state = useWorkspaceStore.getState()
    expect(state.workspaceId).toBe("workspace-legacy-top-level")
    expect(state.workspaceName).toBe("Legacy Top-Level Workspace")
    expect(state.workspaceTag).toBe("workspace:legacy-top-level")
    expect(state.workspaceChatReferenceId).toBe("legacy-top-level-chat")
    expect(state.sources[0]?.title).toBe("Legacy Top-Level Source")
    expect(state.selectedSourceIds).toEqual(["legacy-source-1"])
    expect(state.generatedArtifacts[0]?.title).toBe("Legacy Top-Level Artifact")
    expect(state.notes).toBe("Legacy top-level notes")
    expect(state.currentNote.title).toBe("Legacy note")
    expect(state.leftPaneCollapsed).toBe(true)
    expect(state.rightPaneCollapsed).toBe(false)
    expect(state.workspaceSnapshots["workspace-legacy-top-level"]).toBeDefined()
    expect(
      state.workspaceChatSessions["workspace-legacy-top-level"]?.history[0]?.content
    ).toBe("Legacy session message")
  })

  it("dispatches a quota warning event when localStorage is full", () => {
    const storage = createWorkspaceStorage()
    const originalSetItem = Storage.prototype.setItem
    const quotaError =
      typeof DOMException !== "undefined"
        ? new DOMException("Quota exceeded", "QuotaExceededError")
        : Object.assign(new Error("Quota exceeded"), {
            name: "QuotaExceededError",
            code: 22
          })
    const quotaEvents: Array<CustomEvent<WorkspaceStorageQuotaEventDetail>> = []

    const onQuotaExceeded = (event: Event) => {
      quotaEvents.push(
        event as CustomEvent<WorkspaceStorageQuotaEventDetail>
      )
    }

    Storage.prototype.setItem = () => {
      throw quotaError
    }
    window.addEventListener(
      WORKSPACE_STORAGE_QUOTA_EVENT,
      onQuotaExceeded as EventListener
    )

    expect(() => {
      storage.setItem(STORAGE_KEY, '{"state":{"workspaceName":"Overflow"}}')
    }).not.toThrow()

    expect(quotaEvents).toHaveLength(1)
    expect(quotaEvents[0]?.detail.key).toBe(STORAGE_KEY)

    window.removeEventListener(
      WORKSPACE_STORAGE_QUOTA_EVENT,
      onQuotaExceeded as EventListener
    )
    Storage.prototype.setItem = originalSetItem
  })

  it("duplicates workspace data with new derived IDs and isolated snapshot state", () => {
    useWorkspaceStore.getState().initializeWorkspace("Original Workspace")
    const originalId = useWorkspaceStore.getState().workspaceId

    const originalSource = useWorkspaceStore
      .getState()
      .addSource({ mediaId: 7001, title: "Original Source", type: "pdf" })
    useWorkspaceStore.getState().setSelectedSourceIds([originalSource.id])
    useWorkspaceStore
      .getState()
      .addArtifact({
        type: "summary",
        title: "Original Artifact",
        status: "completed",
        content: "Original artifact content"
      })
    useWorkspaceStore.setState({
      notes: "Original notes",
      currentNote: {
        id: 10,
        title: "Original note",
        content: "Original note content",
        keywords: ["original"],
        version: 1,
        isDirty: false
      },
      leftPaneCollapsed: true
    })
    useWorkspaceStore.getState().saveCurrentWorkspace()

    const originalSnapshot = useWorkspaceStore.getState().workspaceSnapshots[originalId]
    expect(originalSnapshot).toBeDefined()

    const duplicateId = useWorkspaceStore.getState().duplicateWorkspace(originalId)
    expect(duplicateId).not.toBeNull()

    const stateAfterDuplicate = useWorkspaceStore.getState()
    expect(stateAfterDuplicate.workspaceId).toBe(duplicateId)
    expect(stateAfterDuplicate.workspaceName).toContain("(Copy)")
    expect(stateAfterDuplicate.sources).toHaveLength(1)
    expect(stateAfterDuplicate.generatedArtifacts).toHaveLength(1)
    expect(stateAfterDuplicate.notes).toBe("Original notes")
    expect(stateAfterDuplicate.leftPaneCollapsed).toBe(true)

    const duplicateSnapshot =
      stateAfterDuplicate.workspaceSnapshots[duplicateId as string]
    expect(duplicateSnapshot.sources[0]?.id).not.toBe(
      originalSnapshot?.sources[0]?.id
    )
    expect(duplicateSnapshot.generatedArtifacts[0]?.id).not.toBe(
      originalSnapshot?.generatedArtifacts[0]?.id
    )
    expect(duplicateSnapshot.selectedSourceIds[0]).toBe(
      duplicateSnapshot.sources[0]?.id
    )

    const duplicateSourceId = stateAfterDuplicate.sources[0]?.id
    if (duplicateSourceId) {
      useWorkspaceStore.getState().removeSource(duplicateSourceId)
    }
    useWorkspaceStore.getState().setNotes("Duplicate notes")

    useWorkspaceStore.getState().switchWorkspace(originalId)
    const originalStateAfterMutation = useWorkspaceStore.getState()
    expect(originalStateAfterMutation.workspaceId).toBe(originalId)
    expect(originalStateAfterMutation.sources).toHaveLength(1)
    expect(originalStateAfterMutation.sources[0]?.title).toBe("Original Source")
    expect(originalStateAfterMutation.notes).toBe("Original notes")
  })

  it("archives and restores workspaces without losing snapshot data", () => {
    useWorkspaceStore.getState().initializeWorkspace("Workspace A")
    const workspaceAId = useWorkspaceStore.getState().workspaceId
    useWorkspaceStore
      .getState()
      .addSource({ mediaId: 8101, title: "Workspace A Source", type: "video" })
    useWorkspaceStore.getState().setNotes("Workspace A notes")
    useWorkspaceStore.getState().saveCurrentWorkspace()

    useWorkspaceStore.getState().createNewWorkspace("Workspace B")
    const workspaceBId = useWorkspaceStore.getState().workspaceId
    useWorkspaceStore
      .getState()
      .addSource({ mediaId: 8201, title: "Workspace B Source", type: "audio" })
    useWorkspaceStore.getState().saveCurrentWorkspace()

    useWorkspaceStore.getState().archiveWorkspace(workspaceAId)
    let state = useWorkspaceStore.getState()
    expect(state.savedWorkspaces.some((workspace) => workspace.id === workspaceAId)).toBe(
      false
    )
    expect(state.archivedWorkspaces.some((workspace) => workspace.id === workspaceAId)).toBe(
      true
    )
    expect(state.workspaceId).toBe(workspaceBId)

    useWorkspaceStore.getState().restoreArchivedWorkspace(workspaceAId)
    state = useWorkspaceStore.getState()
    expect(state.savedWorkspaces.some((workspace) => workspace.id === workspaceAId)).toBe(
      true
    )
    expect(state.archivedWorkspaces.some((workspace) => workspace.id === workspaceAId)).toBe(
      false
    )

    useWorkspaceStore.getState().switchWorkspace(workspaceAId)
    state = useWorkspaceStore.getState()
    expect(state.workspaceId).toBe(workspaceAId)
    expect(state.sources).toHaveLength(1)
    expect(state.sources[0]?.title).toBe("Workspace A Source")
    expect(state.notes).toBe("Workspace A notes")

    useWorkspaceStore.getState().archiveWorkspace(workspaceAId)
    state = useWorkspaceStore.getState()
    expect(state.workspaceId).toBe(workspaceBId)
    expect(state.archivedWorkspaces.some((workspace) => workspace.id === workspaceAId)).toBe(
      true
    )
  })

  it("stores independent chat sessions per workspace", () => {
    useWorkspaceStore.getState().initializeWorkspace("Chat Workspace A")
    const workspaceAId = useWorkspaceStore.getState().workspaceId

    useWorkspaceStore.getState().saveWorkspaceChatSession(workspaceAId, {
      messages: [
        {
          isBot: false,
          name: "You",
          message: "Workspace A message",
          sources: []
        }
      ],
      history: [{ role: "user", content: "Workspace A message" }],
      historyId: "history-a",
      serverChatId: null
    })

    useWorkspaceStore.getState().createNewWorkspace("Chat Workspace B")
    const workspaceBId = useWorkspaceStore.getState().workspaceId
    useWorkspaceStore.getState().saveWorkspaceChatSession(workspaceBId, {
      messages: [
        {
          isBot: true,
          name: "Assistant",
          message: "Workspace B reply",
          sources: []
        }
      ],
      history: [{ role: "assistant", content: "Workspace B reply" }],
      historyId: "history-b",
      serverChatId: "server-chat-b"
    })

    const sessionA = useWorkspaceStore.getState().getWorkspaceChatSession(workspaceAId)
    const sessionB = useWorkspaceStore.getState().getWorkspaceChatSession(workspaceBId)

    expect(sessionA?.historyId).toBe("history-a")
    expect(sessionA?.messages[0]?.message).toBe("Workspace A message")
    expect(sessionB?.historyId).toBe("history-b")
    expect(sessionB?.messages[0]?.message).toBe("Workspace B reply")

    useWorkspaceStore.getState().clearWorkspaceChatSession(workspaceAId)
    expect(useWorkspaceStore.getState().getWorkspaceChatSession(workspaceAId)).toBeNull()
    expect(useWorkspaceStore.getState().getWorkspaceChatSession(workspaceBId)?.historyId).toBe(
      "history-b"
    )
  })

  it("focuses sources by media id and source id for cross-pane navigation", () => {
    useWorkspaceStore.getState().initializeWorkspace("Citation Workspace")
    const addedSource = useWorkspaceStore
      .getState()
      .addSource({ mediaId: 901, title: "Focused Source", type: "pdf" })

    const focusedByMedia = useWorkspaceStore.getState().focusSourceByMediaId(901)
    expect(focusedByMedia).toBe(true)
    expect(useWorkspaceStore.getState().sourceFocusTarget?.sourceId).toBe(
      addedSource.id
    )

    const previousToken = useWorkspaceStore.getState().sourceFocusTarget?.token
    const focusedById = useWorkspaceStore.getState().focusSourceById(addedSource.id)
    expect(focusedById).toBe(true)
    expect(useWorkspaceStore.getState().sourceFocusTarget?.sourceId).toBe(
      addedSource.id
    )
    expect(useWorkspaceStore.getState().sourceFocusTarget?.token).toBeGreaterThan(
      previousToken ?? 0
    )

    useWorkspaceStore.getState().clearSourceFocusTarget()
    expect(useWorkspaceStore.getState().sourceFocusTarget).toBeNull()
    expect(useWorkspaceStore.getState().focusSourceByMediaId(99999)).toBe(false)
    expect(useWorkspaceStore.getState().focusSourceById("missing-id")).toBe(false)
  })

  it("captures external content into current note in append mode with title proposal", () => {
    useWorkspaceStore.getState().initializeWorkspace("Notes Workspace")

    useWorkspaceStore.getState().captureToCurrentNote({
      title: "Assistant: Key findings",
      content: "Primary finding one.\nPrimary finding two.",
      mode: "append"
    })

    let state = useWorkspaceStore.getState()
    expect(state.currentNote.title).toBe("Assistant: Key findings")
    expect(state.currentNote.content).toContain("## Assistant: Key findings")
    expect(state.currentNote.content).toContain("Primary finding one.")
    expect(state.currentNote.isDirty).toBe(true)

    useWorkspaceStore.getState().captureToCurrentNote({
      title: "Artifact: Summary",
      content: "Additional supporting context.",
      mode: "append"
    })

    state = useWorkspaceStore.getState()
    expect(state.currentNote.content).toContain("## Assistant: Key findings")
    expect(state.currentNote.content).toContain("## Artifact: Summary")
    expect(state.currentNote.content).toContain("---")
    expect(state.currentNote.title).toBe("Assistant: Key findings")
  })

  it("captures external content into current note in replace mode", () => {
    useWorkspaceStore.getState().initializeWorkspace("Replace Notes Workspace")

    useWorkspaceStore.getState().captureToCurrentNote({
      title: "Initial",
      content: "Initial content",
      mode: "append"
    })

    useWorkspaceStore.getState().captureToCurrentNote({
      title: "Studio output",
      content: "Replacement content",
      mode: "replace"
    })

    const state = useWorkspaceStore.getState()
    expect(state.currentNote.content).toBe("## Studio output\n\nReplacement content")
    expect(state.currentNote.title).toBe("Initial")
    expect(state.currentNote.isDirty).toBe(true)
  })

  it("keeps RAG selection limited to ready sources and updates selection on status changes", () => {
    useWorkspaceStore.getState().initializeWorkspace("Source Status Workspace")

    const readySource = useWorkspaceStore
      .getState()
      .addSource({
        mediaId: 111,
        title: "Ready Source",
        type: "pdf",
        status: "ready"
      })
    const processingSource = useWorkspaceStore
      .getState()
      .addSource({
        mediaId: 222,
        title: "Processing Source",
        type: "video",
        status: "processing"
      })

    useWorkspaceStore
      .getState()
      .setSelectedSourceIds([readySource.id, processingSource.id])

    let state = useWorkspaceStore.getState()
    expect(state.selectedSourceIds).toEqual([readySource.id])
    expect(state.getSelectedMediaIds()).toEqual([111])

    useWorkspaceStore.getState().setSourceStatusByMediaId(222, "ready")
    useWorkspaceStore
      .getState()
      .setSelectedSourceIds([readySource.id, processingSource.id])

    state = useWorkspaceStore.getState()
    expect(state.getSelectedMediaIds().sort((a, b) => a - b)).toEqual([111, 222])

    useWorkspaceStore.getState().setSourceStatusByMediaId(222, "error", "Failed")
    state = useWorkspaceStore.getState()
    expect(state.selectedSourceIds).toEqual([readySource.id])
    expect(state.getSelectedMediaIds()).toEqual([111])

    useWorkspaceStore.getState().selectAllSources()
    state = useWorkspaceStore.getState()
    expect(state.selectedSourceIds).toEqual([readySource.id])
  })

  it("reorders sources and restores that order after rehydration", async () => {
    useWorkspaceStore.getState().initializeWorkspace("Reorder Workspace")

    const sourceA = useWorkspaceStore
      .getState()
      .addSource({ mediaId: 6101, title: "Source A", type: "pdf" })
    const sourceB = useWorkspaceStore
      .getState()
      .addSource({ mediaId: 6102, title: "Source B", type: "pdf" })
    const sourceC = useWorkspaceStore
      .getState()
      .addSource({ mediaId: 6103, title: "Source C", type: "pdf" })

    useWorkspaceStore.getState().reorderSource(sourceC.id, 0)
    useWorkspaceStore.getState().reorderSource(sourceA.id, 2)

    expect(useWorkspaceStore.getState().sources.map((source) => source.title)).toEqual([
      "Source C",
      "Source B",
      "Source A"
    ])

    const persisted = localStorage.getItem(STORAGE_KEY)
    expect(persisted).toBeTruthy()

    resetWorkspaceStore()
    if (persisted) {
      localStorage.setItem(STORAGE_KEY, persisted)
    }
    await useWorkspaceStore.persist.rehydrate()

    expect(useWorkspaceStore.getState().sources.map((source) => source.title)).toEqual([
      "Source C",
      "Source B",
      "Source A"
    ])
    expect(useWorkspaceStore.getState().sources[0]?.mediaId).toBe(6103)
    expect(useWorkspaceStore.getState().sources[1]?.mediaId).toBe(6102)
    expect(useWorkspaceStore.getState().sources[2]?.mediaId).toBe(6101)
  })

  it("restores soft-deleted sources and artifacts at prior positions", () => {
    useWorkspaceStore.getState().initializeWorkspace("Undoable Workspace")

    const sourceA = useWorkspaceStore
      .getState()
      .addSource({ mediaId: 9011, title: "Source A", type: "pdf" })
    const sourceB = useWorkspaceStore
      .getState()
      .addSource({ mediaId: 9012, title: "Source B", type: "video" })
    useWorkspaceStore.getState().setSelectedSourceIds([sourceA.id, sourceB.id])

    const artifactA = useWorkspaceStore
      .getState()
      .addArtifact({
        type: "summary",
        title: "Artifact A",
        status: "completed",
        content: "A"
      })
    const artifactB = useWorkspaceStore
      .getState()
      .addArtifact({
        type: "report",
        title: "Artifact B",
        status: "completed",
        content: "B"
      })

    useWorkspaceStore.getState().removeSource(sourceA.id)
    useWorkspaceStore
      .getState()
      .restoreSource(sourceA, { index: 0, select: true })

    let state = useWorkspaceStore.getState()
    expect(state.sources.map((source) => source.id)).toEqual([
      sourceA.id,
      sourceB.id
    ])
    expect(state.selectedSourceIds).toContain(sourceA.id)

    useWorkspaceStore.getState().removeArtifact(artifactA.id)
    useWorkspaceStore
      .getState()
      .restoreArtifact(artifactA, { index: 1 })

    state = useWorkspaceStore.getState()
    expect(state.generatedArtifacts.map((artifact) => artifact.id)).toEqual([
      artifactB.id,
      artifactA.id
    ])
  })

  it("exports and imports workspace bundles with full snapshot fidelity", () => {
    useWorkspaceStore.getState().initializeWorkspace("Exportable Workspace")
    const originalWorkspaceId = useWorkspaceStore.getState().workspaceId
    const originalChatReferenceId =
      useWorkspaceStore.getState().workspaceChatReferenceId

    const source = useWorkspaceStore
      .getState()
      .addSource({ mediaId: 9301, title: "Export source", type: "pdf" })
    useWorkspaceStore.getState().setSelectedSourceIds([source.id])

    const baseArtifact = useWorkspaceStore
      .getState()
      .addArtifact({
        type: "summary",
        title: "Version 1 summary",
        status: "completed",
        content: "Summary v1"
      })

    useWorkspaceStore
      .getState()
      .addArtifact({
        type: "summary",
        title: "Version 2 summary",
        status: "completed",
        previousVersionId: baseArtifact.id,
        content: "Summary v2"
      })

    useWorkspaceStore.setState({
      notes: "Workspace export notes",
      currentNote: {
        id: 42,
        title: "Workspace note",
        content: "Workspace note content",
        keywords: ["export", "workspace"],
        version: 7,
        isDirty: false
      },
      leftPaneCollapsed: true,
      rightPaneCollapsed: true,
      audioSettings: {
        provider: "openai",
        model: "tts-1",
        voice: "alloy",
        speed: 1.2,
        format: "wav"
      }
    })

    useWorkspaceStore.getState().saveWorkspaceChatSession(originalWorkspaceId, {
      messages: [
        {
          isBot: false,
          name: "You",
          message: "Export this workspace",
          sources: []
        }
      ],
      history: [{ role: "user", content: "Export this workspace" }],
      historyId: "history-export",
      serverChatId: "chat-export"
    })

    const bundle = useWorkspaceStore
      .getState()
      .exportWorkspaceBundle(originalWorkspaceId)
    expect(bundle).not.toBeNull()
    expect(bundle?.workspace.snapshot.sources[0]?.title).toBe("Export source")
    expect(bundle?.workspace.chatSession?.historyId).toBe("history-export")
    expect(bundle?.workspace.snapshot.generatedArtifacts[0]?.previousVersionId).toBe(
      baseArtifact.id
    )
    expect(bundle?.workspace.snapshot.workspaceTag).toContain("workspace:")
    expect(bundle?.workspace.snapshot.workspaceCreatedAt).toBeTruthy()

    const importedWorkspaceId = useWorkspaceStore
      .getState()
      .importWorkspaceBundle(bundle!)
    expect(importedWorkspaceId).toBeTruthy()
    expect(importedWorkspaceId).not.toBe(originalWorkspaceId)

    const importedState = useWorkspaceStore.getState()
    expect(importedState.workspaceId).toBe(importedWorkspaceId)
    expect(importedState.workspaceName).toBe("Exportable Workspace (Imported)")
    expect(importedState.workspaceChatReferenceId).toBe(importedWorkspaceId)
    expect(importedState.workspaceChatReferenceId).not.toBe(
      originalChatReferenceId
    )
    expect(importedState.sources).toHaveLength(1)
    expect(importedState.sources[0]?.title).toBe("Export source")
    expect(importedState.selectedSourceIds).toEqual([source.id])
    expect(importedState.generatedArtifacts).toHaveLength(2)
    expect(importedState.generatedArtifacts[0]?.previousVersionId).toBe(
      baseArtifact.id
    )
    expect(importedState.notes).toBe("Workspace export notes")
    expect(importedState.currentNote.title).toBe("Workspace note")
    expect(importedState.leftPaneCollapsed).toBe(true)
    expect(importedState.rightPaneCollapsed).toBe(true)
    expect(importedState.audioSettings.model).toBe("tts-1")

    const importedSession = useWorkspaceStore
      .getState()
      .getWorkspaceChatSession(importedWorkspaceId as string)
    expect(importedSession?.historyId).toBe("history-export")
    expect(importedSession?.messages[0]?.message).toBe("Export this workspace")
  })

  it("captures and restores workspace state snapshot for destructive undo", () => {
    useWorkspaceStore.getState().initializeWorkspace("Snapshot Workspace")
    const originalWorkspaceId = useWorkspaceStore.getState().workspaceId
    useWorkspaceStore
      .getState()
      .addSource({ mediaId: 9201, title: "Saved source", type: "pdf" })
    useWorkspaceStore
      .getState()
      .addArtifact({
        type: "summary",
        title: "Saved artifact",
        status: "completed",
        content: "Saved content"
      })
    useWorkspaceStore.setState({
      notes: "Saved notes",
      leftPaneCollapsed: true
    })
    useWorkspaceStore.getState().saveCurrentWorkspace()

    const undoSnapshot = useWorkspaceStore.getState().captureUndoSnapshot()
    useWorkspaceStore.getState().deleteWorkspace(originalWorkspaceId)

    let state = useWorkspaceStore.getState()
    expect(state.workspaceId).not.toBe(originalWorkspaceId)
    expect(state.sources.some((source) => source.mediaId === 9201)).toBe(false)

    useWorkspaceStore.getState().restoreUndoSnapshot(undoSnapshot)
    state = useWorkspaceStore.getState()
    expect(state.workspaceId).toBe(originalWorkspaceId)
    expect(state.sources.some((source) => source.mediaId === 9201)).toBe(true)
    expect(
      state.generatedArtifacts.some(
        (artifact) => artifact.title === "Saved artifact"
      )
    ).toBe(true)
    expect(state.notes).toBe("Saved notes")
    expect(state.leftPaneCollapsed).toBe(true)
  })
})
