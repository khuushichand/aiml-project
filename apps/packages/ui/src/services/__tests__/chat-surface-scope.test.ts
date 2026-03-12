import { describe, expect, it } from "vitest"

import {
  buildChatSurfaceScopeKey,
  buildChatSurfaceScopeKeyFromConfig
} from "@/services/chat-surface-scope"

const JWT_WITH_SUB =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJ1c2VyLTQyIn0.signature"

describe("chat-surface-scope", () => {
  it("changes the scope key when the server URL or auth mode changes", () => {
    expect(
      buildChatSurfaceScopeKey({
        serverUrl: "http://localhost:8000",
        authMode: "single-user",
        orgId: null,
        userId: null
      })
    ).not.toBe(
      buildChatSurfaceScopeKey({
        serverUrl: "https://prod.example.com",
        authMode: "multi-user",
        orgId: 7,
        userId: 42
      })
    )
  })

  it("uses access-token identity when an explicit user id is unavailable", () => {
    expect(
      buildChatSurfaceScopeKeyFromConfig({
        serverUrl: "https://prod.example.com",
        authMode: "multi-user",
        orgId: 7,
        accessToken: JWT_WITH_SUB
      })
    ).toContain("user:user-42")
  })
})
