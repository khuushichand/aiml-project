import { describe, expect, it } from "vitest"
import {
  buildConversationShareUrl,
  getActiveShareLinkCount,
  isShareLinkActive,
  sortShareLinksByCreatedDesc
} from "../chat-share-links"

describe("chat share link helpers", () => {
  it("counts only active links", () => {
    const now = Date.parse("2026-02-20T12:00:00.000Z")
    const links = [
      {
        id: "active",
        permission: "view" as const,
        created_at: "2026-02-20T10:00:00.000Z",
        expires_at: "2026-02-21T10:00:00.000Z",
        revoked_at: null
      },
      {
        id: "expired",
        permission: "view" as const,
        created_at: "2026-02-20T09:00:00.000Z",
        expires_at: "2026-02-20T11:00:00.000Z",
        revoked_at: null
      },
      {
        id: "revoked",
        permission: "view" as const,
        created_at: "2026-02-20T08:00:00.000Z",
        expires_at: "2026-02-21T08:00:00.000Z",
        revoked_at: "2026-02-20T09:30:00.000Z"
      }
    ]

    expect(getActiveShareLinkCount(links, now)).toBe(1)
    expect(isShareLinkActive(links[0], now)).toBe(true)
    expect(isShareLinkActive(links[1], now)).toBe(false)
    expect(isShareLinkActive(links[2], now)).toBe(false)
  })

  it("sorts links by created time descending", () => {
    const sorted = sortShareLinksByCreatedDesc([
      {
        id: "older",
        permission: "view" as const,
        created_at: "2026-02-20T08:00:00.000Z",
        expires_at: "2026-02-21T08:00:00.000Z"
      },
      {
        id: "newer",
        permission: "view" as const,
        created_at: "2026-02-20T10:00:00.000Z",
        expires_at: "2026-02-21T10:00:00.000Z"
      }
    ])

    expect(sorted.map((entry) => entry.id)).toEqual(["newer", "older"])
  })

  it("builds share URL from share_path first, then token fallback", () => {
    expect(
      buildConversationShareUrl("https://example.com", {
        share_path: "/knowledge/shared/path-token",
        token: "ignored"
      })
    ).toBe("https://example.com/knowledge/shared/path-token")

    expect(
      buildConversationShareUrl("https://example.com", {
        share_path: null,
        token: "abc 123"
      })
    ).toBe("https://example.com/knowledge/shared/abc%20123")

    expect(
      buildConversationShareUrl("https://example.com", {
        share_path: null,
        token: null
      })
    ).toBeNull()
  })
})
