import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn(),
  bgUpload: vi.fn(),
  bgStream: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args),
  bgUpload: (...args: unknown[]) => mocks.bgUpload(...args),
  bgStream: (...args: unknown[]) => mocks.bgStream(...args)
}))

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: vi.fn(async () => null),
    set: vi.fn(async () => undefined),
    remove: vi.fn(async () => undefined)
  }),
  safeStorageSerde: {
    serialize: (value: unknown) => value,
    deserialize: (value: unknown) => value
  }
}))

import { TldwApiClient } from "@/services/tldw/TldwApiClient"

describe("TldwApiClient conversation share links", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("creates a share link with TTL and label", async () => {
    mocks.bgRequest.mockResolvedValue({
      share_id: "share-1",
      permission: "view",
      created_at: "2026-02-20T10:00:00Z",
      expires_at: "2026-02-21T10:00:00Z",
      token: "abc",
      share_path: "/knowledge/shared/abc"
    })

    const client = new TldwApiClient()
    const result = await client.createConversationShareLink("chat-1", {
      permission: "view",
      ttl_seconds: 3600,
      label: "QA review"
    })

    const call = mocks.bgRequest.mock.calls.at(-1)?.[0] as {
      path?: string
      method?: string
      headers?: Record<string, string>
      body?: unknown
    }
    expect(call.path).toBe(
      "/api/v1/chat/conversations/chat-1/share-links?scope_type=global"
    )
    expect(call.method).toBe("POST")
    expect(call.headers).toEqual({ "Content-Type": "application/json" })
    expect(call.body).toEqual({
      permission: "view",
      ttl_seconds: 3600,
      label: "QA review"
    })
    expect(result.share_id).toBe("share-1")
  })

  it("passes workspace scope to share-link endpoints", async () => {
    mocks.bgRequest
      .mockResolvedValueOnce({
        share_id: "share-2",
        permission: "view",
        created_at: "2026-02-20T10:00:00Z",
        expires_at: "2026-02-21T10:00:00Z"
      })
      .mockResolvedValueOnce({
        conversation_id: "chat-2",
        links: []
      })
      .mockResolvedValueOnce({ success: true, share_id: "share-2" })

    const client = new TldwApiClient()

    await client.createConversationShareLink(
      "chat-2",
      { label: "Scoped share" },
      { scope: { type: "workspace", workspaceId: "workspace-2" } }
    )
    await client.listConversationShareLinks("chat-2", {
      scope: { type: "workspace", workspaceId: "workspace-2" }
    })
    await client.revokeConversationShareLink("chat-2", "share-2", {
      scope: { type: "workspace", workspaceId: "workspace-2" }
    })

    const createCall = mocks.bgRequest.mock.calls.at(0)?.[0] as {
      path?: string
    }
    const listCall = mocks.bgRequest.mock.calls.at(1)?.[0] as {
      path?: string
    }
    const revokeCall = mocks.bgRequest.mock.calls.at(2)?.[0] as {
      path?: string
    }

    expect(createCall.path).toBe(
      "/api/v1/chat/conversations/chat-2/share-links?scope_type=workspace&workspace_id=workspace-2"
    )
    expect(listCall.path).toBe(
      "/api/v1/chat/conversations/chat-2/share-links?scope_type=workspace&workspace_id=workspace-2"
    )
    expect(revokeCall.path).toBe(
      "/api/v1/chat/conversations/chat-2/share-links/share-2?scope_type=workspace&workspace_id=workspace-2"
    )
  })

  it("lists and revokes share links for a conversation", async () => {
    mocks.bgRequest
      .mockResolvedValueOnce({
        conversation_id: "chat-1",
        links: [
          {
            id: "share-1",
            permission: "view",
            created_at: "2026-02-20T10:00:00Z",
            expires_at: "2026-02-21T10:00:00Z"
          }
        ]
      })
      .mockResolvedValueOnce({ success: true, share_id: "share-1" })

    const client = new TldwApiClient()

    const listed = await client.listConversationShareLinks("chat-1")
    await client.revokeConversationShareLink("chat-1", "share-1")

    const listCall = mocks.bgRequest.mock.calls.at(0)?.[0] as {
      path?: string
      method?: string
    }
    const revokeCall = mocks.bgRequest.mock.calls.at(1)?.[0] as {
      path?: string
      method?: string
    }

    expect(listCall.path).toBe(
      "/api/v1/chat/conversations/chat-1/share-links?scope_type=global"
    )
    expect(listCall.method).toBe("GET")
    expect(listed.links).toHaveLength(1)

    expect(revokeCall.path).toBe(
      "/api/v1/chat/conversations/chat-1/share-links/share-1?scope_type=global"
    )
    expect(revokeCall.method).toBe("DELETE")
  })

  it("resolves shared tokens using unauthenticated endpoint", async () => {
    mocks.bgRequest.mockResolvedValue({
      conversation_id: "chat-1",
      permission: "view",
      shared_by_user_id: "1",
      expires_at: "2026-02-21T10:00:00Z",
      messages: []
    })

    const client = new TldwApiClient()
    const result = await client.resolveConversationShareLink("token with space")

    const call = mocks.bgRequest.mock.calls.at(-1)?.[0] as {
      path?: string
      method?: string
      noAuth?: boolean
    }

    expect(call.path).toBe(
      "/api/v1/chat/shared/conversations/token%20with%20space"
    )
    expect(call.method).toBe("GET")
    expect(call.noAuth).toBe(true)
    expect(result.conversation_id).toBe("chat-1")
  })
})
