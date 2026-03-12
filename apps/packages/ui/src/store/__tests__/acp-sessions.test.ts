import { afterEach, describe, expect, it } from "vitest"

import { useACPSessionsStore } from "@/store/acp-sessions"

const resetStore = () => {
  useACPSessionsStore.getState().reset()
}

describe("ACP sessions store", () => {
  afterEach(() => {
    resetStore()
  })

  it("preserves tenancy metadata when replacing a local session with a server session", () => {
    const state = useACPSessionsStore.getState()
    const localId = state.createSession({
      cwd: "/workspace/repo",
      name: "Workspace Session",
      personaId: "persona-1",
      workspaceId: "workspace-1",
      workspaceGroupId: "group-1",
      scopeSnapshotId: "scope-1",
    })

    state.replaceSessionId(localId, "server-session-1")

    const session = useACPSessionsStore.getState().getSession("server-session-1")
    expect(session?.personaId).toBe("persona-1")
    expect(session?.workspaceId).toBe("workspace-1")
    expect(session?.workspaceGroupId).toBe("group-1")
    expect(session?.scopeSnapshotId).toBe("scope-1")
    expect(session?.backendStatus).toBe("active")
  })

  it("hydrates fork lineage and tenancy fields from server session payloads", () => {
    const state = useACPSessionsStore.getState()

    state.upsertSessionsFromServerList([
      {
        session_id: "fork-session-1",
        user_id: 1,
        agent_type: "codex",
        name: "Forked Session",
        status: "active",
        created_at: "2024-01-01T00:00:00.000Z",
        last_activity_at: "2024-01-01T00:01:00.000Z",
        message_count: 2,
        usage: { prompt_tokens: 1, completion_tokens: 2, total_tokens: 3 },
        tags: [],
        has_websocket: false,
        persona_id: "persona-1",
        workspace_id: "workspace-1",
        workspace_group_id: "group-1",
        scope_snapshot_id: "scope-1",
        forked_from: "root-session",
      },
    ])

    state.applySessionDetail({
      session_id: "fork-session-1",
      user_id: 1,
      agent_type: "codex",
      name: "Forked Session",
      status: "active",
      created_at: "2024-01-01T00:00:00.000Z",
      last_activity_at: "2024-01-01T00:01:00.000Z",
      message_count: 2,
      usage: { prompt_tokens: 1, completion_tokens: 2, total_tokens: 3 },
      tags: [],
      has_websocket: false,
      persona_id: "persona-1",
      workspace_id: "workspace-1",
      workspace_group_id: "group-1",
      scope_snapshot_id: "scope-1",
      forked_from: "root-session",
      fork_lineage: ["root-session"],
      messages: [],
      cwd: "/workspace/repo",
    })

    const session = useACPSessionsStore.getState().getSession("fork-session-1")
    expect(session?.forkParentSessionId).toBe("root-session")
    expect(session?.personaId).toBe("persona-1")
    expect(session?.workspaceId).toBe("workspace-1")
    expect(session?.workspaceGroupId).toBe("group-1")
    expect(session?.scopeSnapshotId).toBe("scope-1")
  })
})
