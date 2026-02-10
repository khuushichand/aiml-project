import { describe, expect, it } from "vitest"

import {
  MEDIA_DISPLAY_MODE_FORMAT_TO_LABEL,
  MEDIA_DISPLAY_MODE_LABEL_TO_FORMAT,
  buildMediaNavigationMediaKey,
  buildMediaNavigationScopeKey,
  coerceMediaNavigationFormat,
  deriveScopedUserId,
  deriveServerFingerprint
} from "@/utils/media-navigation-scope"

const JWT_WITH_SUB =
  "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJ1c2VyLTQyIn0.signature"

describe("media-navigation-scope", () => {
  it("keeps canonical display-mode mapping stable", () => {
    expect(MEDIA_DISPLAY_MODE_LABEL_TO_FORMAT.Auto).toBe("auto")
    expect(MEDIA_DISPLAY_MODE_LABEL_TO_FORMAT.Plain).toBe("plain")
    expect(MEDIA_DISPLAY_MODE_LABEL_TO_FORMAT.Markdown).toBe("markdown")
    expect(MEDIA_DISPLAY_MODE_LABEL_TO_FORMAT.Rich).toBe("html")
    expect(MEDIA_DISPLAY_MODE_FORMAT_TO_LABEL.html).toBe("Rich")
  })

  it("coerces format values case-insensitively", () => {
    expect(coerceMediaNavigationFormat("AUTO")).toBe("auto")
    expect(coerceMediaNavigationFormat(" markdown ")).toBe("markdown")
    expect(coerceMediaNavigationFormat("HTML")).toBe("html")
  })

  it("falls back to default format for unknown values", () => {
    expect(coerceMediaNavigationFormat("rich")).toBe("auto")
    expect(coerceMediaNavigationFormat("text", "plain")).toBe("plain")
  })

  it("derives stable server fingerprint from normalized URL identity", () => {
    const a = deriveServerFingerprint("HTTP://Example.com:80/api/")
    const b = deriveServerFingerprint("http://example.com/api")
    const c = deriveServerFingerprint("http://example.com:8080/api")
    expect(a).toBe(b)
    expect(a).not.toBe(c)
  })

  it("derives scoped user id with explicit user id first", () => {
    expect(
      deriveScopedUserId({
        userId: "abc-123",
        authMode: "multi-user",
        accessToken: JWT_WITH_SUB
      })
    ).toBe("user:abc-123")
  })

  it("derives scoped user id from auth mode or access token fallback", () => {
    expect(
      deriveScopedUserId({
        authMode: "single-user"
      })
    ).toBe("user:single-user")

    expect(
      deriveScopedUserId({
        authMode: "multi-user",
        accessToken: JWT_WITH_SUB
      })
    ).toBe("user:user-42")
  })

  it("builds scope and media keys with required namespaces", () => {
    const scopeKey = buildMediaNavigationScopeKey({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user"
    })
    expect(scopeKey).toContain("server:")
    expect(scopeKey).toContain("user:single-user")

    const mediaKey = buildMediaNavigationMediaKey(
      {
        serverUrl: "http://127.0.0.1:8000",
        authMode: "single-user"
      },
      42
    )
    expect(mediaKey).toContain(":media:42")
    expect(mediaKey.startsWith(scopeKey)).toBe(true)
  })
})
