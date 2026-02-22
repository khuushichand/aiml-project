import { afterEach, beforeEach, describe, expect, it } from "vitest"
import {
  WORKSPACE_STORAGE_KEY,
  WORKSPACE_STORAGE_QUOTA_EVENT,
  WORKSPACE_STORAGE_RECOVERY_EVENT,
  type WorkspaceStorageQuotaEventDetail,
  type WorkspaceStorageRecoveryEventDetail
} from "@/store/workspace-events"
import { createWorkspaceStorage } from "../workspace"

const STORAGE_KEY = WORKSPACE_STORAGE_KEY

const buildQuotaError = () =>
  typeof DOMException !== "undefined"
    ? new DOMException("Quota exceeded", "QuotaExceededError")
    : Object.assign(new Error("Quota exceeded"), {
        name: "QuotaExceededError",
        code: 22
      })

const buildPersistedPayload = (state: Record<string, unknown>) =>
  JSON.stringify({
    state,
    version: 1
  })

describe("workspace storage quota eviction recovery", () => {
  let originalSetItem: typeof Storage.prototype.setItem

  beforeEach(() => {
    originalSetItem = Storage.prototype.setItem
    localStorage.removeItem(STORAGE_KEY)
  })

  afterEach(() => {
    Storage.prototype.setItem = originalSetItem
  })

  it("evicts least-recently-used archived workspace data before retrying", () => {
    const storage = createWorkspaceStorage()
    const quotaEvents: Array<CustomEvent<WorkspaceStorageQuotaEventDetail>> = []
    const recoveryEvents: Array<CustomEvent<WorkspaceStorageRecoveryEventDetail>> = []
    const writes: string[] = []
    let callCount = 0

    const onQuota = (event: Event) =>
      quotaEvents.push(event as CustomEvent<WorkspaceStorageQuotaEventDetail>)
    const onRecovery = (event: Event) =>
      recoveryEvents.push(event as CustomEvent<WorkspaceStorageRecoveryEventDetail>)
    window.addEventListener(WORKSPACE_STORAGE_QUOTA_EVENT, onQuota as EventListener)
    window.addEventListener(
      WORKSPACE_STORAGE_RECOVERY_EVENT,
      onRecovery as EventListener
    )

    Storage.prototype.setItem = ((name: string, value: string) => {
      callCount += 1
      writes.push(value)
      if (callCount === 1) {
        throw buildQuotaError()
      }
    }) as typeof Storage.prototype.setItem

    const payload = buildPersistedPayload({
      workspaceId: "workspace-active",
      savedWorkspaces: [
        {
          id: "workspace-active",
          name: "Active",
          tag: "workspace:active",
          createdAt: "2026-02-22T00:00:00.000Z",
          lastAccessedAt: "2026-02-22T00:00:00.000Z",
          sourceCount: 1
        }
      ],
      archivedWorkspaces: [
        {
          id: "workspace-archived-old",
          name: "Archived Old",
          tag: "workspace:archived-old",
          createdAt: "2026-01-01T00:00:00.000Z",
          lastAccessedAt: "2026-01-01T00:00:00.000Z",
          sourceCount: 0
        },
        {
          id: "workspace-archived-new",
          name: "Archived New",
          tag: "workspace:archived-new",
          createdAt: "2026-02-01T00:00:00.000Z",
          lastAccessedAt: "2026-02-01T00:00:00.000Z",
          sourceCount: 0
        }
      ],
      workspaceSnapshots: {
        "workspace-active": {
          workspaceId: "workspace-active",
          generatedArtifacts: [],
          notes: ""
        },
        "workspace-archived-old": {
          workspaceId: "workspace-archived-old",
          generatedArtifacts: [],
          notes: "x".repeat(180000)
        },
        "workspace-archived-new": {
          workspaceId: "workspace-archived-new",
          generatedArtifacts: [],
          notes: "x".repeat(90000)
        }
      },
      workspaceChatSessions: {
        "workspace-active": {
          messages: [],
          historyId: null,
          serverChatId: null
        },
        "workspace-archived-old": {
          messages: [{ message: "old chat" }],
          historyId: "old-history",
          serverChatId: null
        },
        "workspace-archived-new": {
          messages: [{ message: "new chat" }],
          historyId: "new-history",
          serverChatId: null
        }
      }
    })

    storage.setItem(STORAGE_KEY, payload)

    expect(callCount).toBe(2)
    expect(quotaEvents).toHaveLength(0)
    expect(
      recoveryEvents.some(
        (event) => event.detail.action === "archived_workspace_removed"
      )
    ).toBe(true)
    expect(
      recoveryEvents.some((event) => event.detail.action === "retry_success")
    ).toBe(true)

    const recoveredPayload = JSON.parse(writes[1] || "{}")
    const recoveredState = recoveredPayload.state as Record<string, any>
    const archivedIds = Array.isArray(recoveredState.archivedWorkspaces)
      ? recoveredState.archivedWorkspaces.map((workspace: { id?: string }) => workspace.id)
      : []
    expect(archivedIds).not.toContain("workspace-archived-old")
    expect(recoveredState.workspaceSnapshots?.["workspace-archived-old"]).toBeUndefined()
    expect(
      recoveredState.workspaceChatSessions?.["workspace-archived-old"]
    ).toBeUndefined()

    window.removeEventListener(
      WORKSPACE_STORAGE_QUOTA_EVENT,
      onQuota as EventListener
    )
    window.removeEventListener(
      WORKSPACE_STORAGE_RECOVERY_EVENT,
      onRecovery as EventListener
    )
  })

  it("evicts oldest non-active chat sessions and oversized artifacts", () => {
    const storage = createWorkspaceStorage()
    const recoveryEvents: Array<CustomEvent<WorkspaceStorageRecoveryEventDetail>> = []
    const writes: string[] = []
    let callCount = 0

    const onRecovery = (event: Event) =>
      recoveryEvents.push(event as CustomEvent<WorkspaceStorageRecoveryEventDetail>)
    window.addEventListener(
      WORKSPACE_STORAGE_RECOVERY_EVENT,
      onRecovery as EventListener
    )

    Storage.prototype.setItem = ((name: string, value: string) => {
      callCount += 1
      writes.push(value)
      if (callCount === 1) {
        throw buildQuotaError()
      }
    }) as typeof Storage.prototype.setItem

    const payload = buildPersistedPayload({
      workspaceId: "workspace-active",
      savedWorkspaces: [
        {
          id: "workspace-active",
          lastAccessedAt: "2026-02-22T00:00:00.000Z"
        },
        {
          id: "workspace-old",
          lastAccessedAt: "2026-01-01T00:00:00.000Z"
        },
        {
          id: "workspace-newer",
          lastAccessedAt: "2026-02-10T00:00:00.000Z"
        }
      ],
      archivedWorkspaces: [],
      workspaceSnapshots: {
        "workspace-active": {
          workspaceId: "workspace-active",
          generatedArtifacts: [],
          notes: ""
        },
        "workspace-old": {
          workspaceId: "workspace-old",
          generatedArtifacts: [
            {
              id: "artifact-old-1",
              content: "A".repeat(180000)
            },
            {
              id: "artifact-old-2",
              content: "B".repeat(160000)
            }
          ],
          notes: ""
        },
        "workspace-newer": {
          workspaceId: "workspace-newer",
          generatedArtifacts: [
            {
              id: "artifact-new-1",
              content: "C".repeat(20000)
            }
          ],
          notes: ""
        }
      },
      workspaceChatSessions: {
        "workspace-active": {
          messages: [{ message: "active" }],
          historyId: "active-history",
          serverChatId: null
        },
        "workspace-old": {
          messages: [{ message: "old" }],
          historyId: "old-history",
          serverChatId: null
        },
        "workspace-newer": {
          messages: [{ message: "newer" }],
          historyId: "newer-history",
          serverChatId: null
        }
      }
    })

    storage.setItem(STORAGE_KEY, payload)

    expect(callCount).toBe(2)
    expect(
      recoveryEvents.some((event) => event.detail.action === "chat_session_removed")
    ).toBe(true)
    expect(
      recoveryEvents.some((event) => event.detail.action === "artifact_removed")
    ).toBe(true)
    expect(
      recoveryEvents.some((event) => event.detail.action === "retry_success")
    ).toBe(true)

    const recoveredPayload = JSON.parse(writes[1] || "{}")
    const recoveredState = recoveredPayload.state as Record<string, any>
    expect(recoveredState.workspaceChatSessions?.["workspace-old"]).toBeUndefined()
    expect(
      recoveredState.workspaceSnapshots?.["workspace-old"]?.generatedArtifacts
        ?.length
    ).toBeLessThan(2)

    window.removeEventListener(
      WORKSPACE_STORAGE_RECOVERY_EVENT,
      onRecovery as EventListener
    )
  })

  it("emits quota warning if retry still fails after recovery", () => {
    const storage = createWorkspaceStorage()
    const quotaEvents: Array<CustomEvent<WorkspaceStorageQuotaEventDetail>> = []
    const recoveryEvents: Array<CustomEvent<WorkspaceStorageRecoveryEventDetail>> = []
    let callCount = 0

    const onQuota = (event: Event) =>
      quotaEvents.push(event as CustomEvent<WorkspaceStorageQuotaEventDetail>)
    const onRecovery = (event: Event) =>
      recoveryEvents.push(event as CustomEvent<WorkspaceStorageRecoveryEventDetail>)
    window.addEventListener(WORKSPACE_STORAGE_QUOTA_EVENT, onQuota as EventListener)
    window.addEventListener(
      WORKSPACE_STORAGE_RECOVERY_EVENT,
      onRecovery as EventListener
    )

    Storage.prototype.setItem = (() => {
      callCount += 1
      throw buildQuotaError()
    }) as typeof Storage.prototype.setItem

    const payload = buildPersistedPayload({
      workspaceId: "workspace-active",
      savedWorkspaces: [],
      archivedWorkspaces: [
        {
          id: "workspace-archived-old",
          lastAccessedAt: "2026-01-01T00:00:00.000Z"
        }
      ],
      workspaceSnapshots: {
        "workspace-archived-old": {
          workspaceId: "workspace-archived-old",
          generatedArtifacts: [],
          notes: "x".repeat(120000)
        }
      },
      workspaceChatSessions: {}
    })

    expect(() => {
      storage.setItem(STORAGE_KEY, payload)
    }).not.toThrow()

    expect(callCount).toBe(2)
    expect(quotaEvents).toHaveLength(1)
    expect(
      recoveryEvents.some((event) => event.detail.action === "retry_failed")
    ).toBe(true)

    window.removeEventListener(
      WORKSPACE_STORAGE_QUOTA_EVENT,
      onQuota as EventListener
    )
    window.removeEventListener(
      WORKSPACE_STORAGE_RECOVERY_EVENT,
      onRecovery as EventListener
    )
  })
})
