import { beforeEach, describe, expect, it } from "vitest"
import {
  DEFAULT_AUDIO_SETTINGS,
  DEFAULT_WORKSPACE_NOTE
} from "@/types/workspace"
import { createWorkspaceStorage, useWorkspaceStore } from "../workspace"

const STORAGE_KEY = "tldw-workspace"

const resetWorkspaceStore = () => {
  localStorage.removeItem(STORAGE_KEY)
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

  it("uses a raw localStorage adapter without parse/stringify in getItem", () => {
    const storage = createWorkspaceStorage()
    const testKey = "workspace-storage-adapter-test"
    const rawPayload = '{"state":{"workspaceCreatedAt":"2026-02-01T00:00:00.000Z"}}'

    storage.setItem(testKey, rawPayload)
    expect(storage.getItem(testKey)).toBe(rawPayload)

    storage.removeItem(testKey)
    expect(storage.getItem(testKey)).toBeNull()
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
})
