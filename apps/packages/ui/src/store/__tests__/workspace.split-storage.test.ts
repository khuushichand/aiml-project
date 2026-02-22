import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { WORKSPACE_STORAGE_KEY } from "@/store/workspace-events"
import { createWorkspaceStorage } from "../workspace"

const STORAGE_KEY = WORKSPACE_STORAGE_KEY

const snapshotKey = (workspaceId: string) =>
  `${STORAGE_KEY}:workspace:${encodeURIComponent(workspaceId)}:snapshot`
const chatKey = (workspaceId: string) =>
  `${STORAGE_KEY}:workspace:${encodeURIComponent(workspaceId)}:chat`

const buildEnvelope = (state: Record<string, unknown>, version = 1) =>
  JSON.stringify({
    state,
    version
  })

describe("workspace split-key persistence storage adapter", () => {
  let originalSetItem: typeof Storage.prototype.setItem

  beforeEach(() => {
    originalSetItem = Storage.prototype.setItem
    localStorage.clear()
  })

  afterEach(() => {
    Storage.prototype.setItem = originalSetItem
    localStorage.clear()
  })

  it("writes split index and only updates changed workspace keys", () => {
    const storage = createWorkspaceStorage()
    const writes: string[] = []

    Storage.prototype.setItem = ((name: string, value: string) => {
      writes.push(name)
      originalSetItem.call(localStorage, name, value)
    }) as typeof Storage.prototype.setItem

    const baseState = {
      workspaceId: "workspace-a",
      savedWorkspaces: [
        {
          id: "workspace-a",
          name: "Workspace A",
          tag: "workspace:a",
          createdAt: "2026-02-22T00:00:00.000Z",
          lastAccessedAt: "2026-02-22T00:00:00.000Z",
          sourceCount: 0
        },
        {
          id: "workspace-b",
          name: "Workspace B",
          tag: "workspace:b",
          createdAt: "2026-02-20T00:00:00.000Z",
          lastAccessedAt: "2026-02-21T00:00:00.000Z",
          sourceCount: 0
        }
      ],
      archivedWorkspaces: [],
      workspaceSnapshots: {
        "workspace-a": {
          workspaceId: "workspace-a",
          workspaceName: "Workspace A",
          workspaceTag: "workspace:a",
          workspaceCreatedAt: "2026-02-22T00:00:00.000Z",
          workspaceChatReferenceId: "workspace-a",
          sources: [],
          selectedSourceIds: [],
          generatedArtifacts: [],
          notes: "A notes",
          currentNote: {
            id: 1,
            title: "A note",
            content: "A content",
            keywords: [],
            version: 1,
            isDirty: false
          },
          leftPaneCollapsed: false,
          rightPaneCollapsed: false,
          audioSettings: {
            provider: "openai",
            model: "gpt-4o-mini-tts",
            voice: "alloy",
            speed: 1,
            format: "mp3"
          }
        },
        "workspace-b": {
          workspaceId: "workspace-b",
          workspaceName: "Workspace B",
          workspaceTag: "workspace:b",
          workspaceCreatedAt: "2026-02-20T00:00:00.000Z",
          workspaceChatReferenceId: "workspace-b",
          sources: [],
          selectedSourceIds: [],
          generatedArtifacts: [],
          notes: "B notes",
          currentNote: {
            id: 2,
            title: "B note",
            content: "B content",
            keywords: [],
            version: 1,
            isDirty: false
          },
          leftPaneCollapsed: false,
          rightPaneCollapsed: false,
          audioSettings: {
            provider: "openai",
            model: "gpt-4o-mini-tts",
            voice: "alloy",
            speed: 1,
            format: "mp3"
          }
        }
      },
      workspaceChatSessions: {
        "workspace-a": {
          messages: [{ isBot: false, name: "You", message: "A chat", sources: [] }],
          historyId: "history-a",
          serverChatId: "chat-a"
        },
        "workspace-b": {
          messages: [{ isBot: false, name: "You", message: "B chat", sources: [] }],
          historyId: "history-b",
          serverChatId: "chat-b"
        }
      }
    }

    storage.setItem(STORAGE_KEY, buildEnvelope(baseState))

    expect(localStorage.getItem(snapshotKey("workspace-a"))).toBeTruthy()
    expect(localStorage.getItem(snapshotKey("workspace-b"))).toBeTruthy()
    expect(localStorage.getItem(chatKey("workspace-a"))).toBeTruthy()
    expect(localStorage.getItem(chatKey("workspace-b"))).toBeTruthy()

    writes.length = 0
    const nextState = {
      ...baseState,
      workspaceSnapshots: {
        ...baseState.workspaceSnapshots,
        "workspace-a": {
          ...baseState.workspaceSnapshots["workspace-a"],
          notes: "A notes updated"
        }
      }
    }
    storage.setItem(STORAGE_KEY, buildEnvelope(nextState))

    expect(writes).toContain(STORAGE_KEY)
    expect(writes).toContain(snapshotKey("workspace-a"))
    expect(writes).not.toContain(snapshotKey("workspace-b"))
    expect(writes).not.toContain(chatKey("workspace-a"))
    expect(writes).not.toContain(chatKey("workspace-b"))
  })

  it("reconstructs full persisted state from split keys on getItem", () => {
    const storage = createWorkspaceStorage()
    const indexPayload = {
      schema: "workspace_split_v1",
      splitVersion: 1,
      version: 1,
      state: {
        workspaceId: "workspace-a",
        savedWorkspaces: [],
        archivedWorkspaces: [],
        workspaceIds: ["workspace-a", "workspace-b"],
        workspaceSnapshots: {},
        workspaceChatSessions: {}
      }
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(indexPayload))
    localStorage.setItem(
      snapshotKey("workspace-a"),
      JSON.stringify({
        workspaceId: "workspace-a",
        workspaceName: "Workspace A",
        workspaceTag: "workspace:a",
        workspaceCreatedAt: "2026-02-22T00:00:00.000Z",
        workspaceChatReferenceId: "workspace-a",
        sources: [],
        selectedSourceIds: [],
        generatedArtifacts: [],
        notes: "A notes",
        currentNote: {
          id: 1,
          title: "A note",
          content: "A content",
          keywords: [],
          version: 1,
          isDirty: false
        },
        leftPaneCollapsed: false,
        rightPaneCollapsed: false,
        audioSettings: {
          provider: "openai",
          model: "gpt-4o-mini-tts",
          voice: "alloy",
          speed: 1,
          format: "mp3"
        }
      })
    )
    localStorage.setItem(
      snapshotKey("workspace-b"),
      JSON.stringify({
        workspaceId: "workspace-b",
        workspaceName: "Workspace B",
        workspaceTag: "workspace:b",
        workspaceCreatedAt: "2026-02-22T00:00:00.000Z",
        workspaceChatReferenceId: "workspace-b",
        sources: [],
        selectedSourceIds: [],
        generatedArtifacts: [],
        notes: "B notes",
        currentNote: {
          id: 2,
          title: "B note",
          content: "B content",
          keywords: [],
          version: 1,
          isDirty: false
        },
        leftPaneCollapsed: false,
        rightPaneCollapsed: false,
        audioSettings: {
          provider: "openai",
          model: "gpt-4o-mini-tts",
          voice: "alloy",
          speed: 1,
          format: "mp3"
        }
      })
    )
    localStorage.setItem(
      chatKey("workspace-b"),
      JSON.stringify({
        messages: [{ isBot: false, name: "You", message: "B chat", sources: [] }],
        historyId: "history-b",
        serverChatId: "chat-b"
      })
    )

    const raw = storage.getItem(STORAGE_KEY)
    expect(raw).toBeTruthy()

    const parsed = raw ? JSON.parse(raw) : null
    const state = parsed?.state as Record<string, any>
    expect(state.workspaceId).toBe("workspace-a")
    expect(state.workspaceSnapshots?.["workspace-a"]?.workspaceName).toBe(
      "Workspace A"
    )
    expect(state.workspaceSnapshots?.["workspace-b"]?.workspaceName).toBe(
      "Workspace B"
    )
    expect(state.workspaceChatSessions?.["workspace-b"]?.historyId).toBe(
      "history-b"
    )
  })

  it("migrates legacy monolithic payload to split keys on first read", () => {
    const storage = createWorkspaceStorage()
    const legacyPayload = buildEnvelope(
      {
        workspaceId: "workspace-legacy",
        savedWorkspaces: [],
        archivedWorkspaces: [],
        workspaceSnapshots: {
          "workspace-legacy": {
            workspaceId: "workspace-legacy",
            workspaceName: "Legacy Workspace",
            workspaceTag: "workspace:legacy",
            workspaceCreatedAt: "2026-02-22T00:00:00.000Z",
            workspaceChatReferenceId: "workspace-legacy",
            sources: [],
            selectedSourceIds: [],
            generatedArtifacts: [],
            notes: "Legacy notes",
            currentNote: {
              id: 1,
              title: "Legacy note",
              content: "Legacy content",
              keywords: [],
              version: 1,
              isDirty: false
            },
            leftPaneCollapsed: false,
            rightPaneCollapsed: false,
            audioSettings: {
              provider: "openai",
              model: "gpt-4o-mini-tts",
              voice: "alloy",
              speed: 1,
              format: "mp3"
            }
          }
        },
        workspaceChatSessions: {
          "workspace-legacy": {
            messages: [
              {
                isBot: false,
                name: "You",
                message: "Legacy chat",
                sources: []
              }
            ],
            historyId: "legacy-history",
            serverChatId: "legacy-chat"
          }
        }
      },
      1
    )

    localStorage.setItem(STORAGE_KEY, legacyPayload)

    const raw = storage.getItem(STORAGE_KEY)
    expect(raw).toBeTruthy()
    const migratedIndexRaw = localStorage.getItem(STORAGE_KEY)
    const migratedIndex = migratedIndexRaw ? JSON.parse(migratedIndexRaw) : null
    expect(migratedIndex?.schema).toBe("workspace_split_v1")
    expect(localStorage.getItem(snapshotKey("workspace-legacy"))).toBeTruthy()
    expect(localStorage.getItem(chatKey("workspace-legacy"))).toBeTruthy()
  })

  it("cleans up split workspace keys when index key is removed", () => {
    const storage = createWorkspaceStorage()
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        schema: "workspace_split_v1",
        splitVersion: 1,
        version: 1,
        state: {
          workspaceId: "workspace-a",
          savedWorkspaces: [],
          archivedWorkspaces: [],
          workspaceIds: ["workspace-a", "workspace-b"],
          workspaceSnapshots: {},
          workspaceChatSessions: {}
        }
      })
    )
    localStorage.setItem(snapshotKey("workspace-a"), JSON.stringify({ id: "a" }))
    localStorage.setItem(chatKey("workspace-a"), JSON.stringify({ id: "a" }))
    localStorage.setItem(snapshotKey("workspace-b"), JSON.stringify({ id: "b" }))
    localStorage.setItem(chatKey("workspace-b"), JSON.stringify({ id: "b" }))

    storage.removeItem(STORAGE_KEY)

    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
    expect(localStorage.getItem(snapshotKey("workspace-a"))).toBeNull()
    expect(localStorage.getItem(chatKey("workspace-a"))).toBeNull()
    expect(localStorage.getItem(snapshotKey("workspace-b"))).toBeNull()
    expect(localStorage.getItem(chatKey("workspace-b"))).toBeNull()
  })
})
