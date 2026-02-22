import { describe, expect, it } from "vitest"
import {
  deriveAdminGuardFromError,
  sanitizeAdminErrorMessage
} from "../admin-error-utils"

describe("admin error utilities", () => {
  it("derives guard state for forbidden and unavailable admin APIs", () => {
    expect(deriveAdminGuardFromError(new Error("Request failed: 403"))).toBe(
      "forbidden"
    )
    expect(deriveAdminGuardFromError(new Error("Request failed: 503"))).toBe(
      "notFound"
    )
    expect(deriveAdminGuardFromError(new Error("Request failed: 404"))).toBe(
      "notFound"
    )
    expect(deriveAdminGuardFromError(new Error("network down"))).toBe(null)
  })

  it("redacts endpoints and filesystem paths from user-facing errors", () => {
    const message = sanitizeAdminErrorMessage(
      new Error(
        "Request failed: 503 (GET /api/v1/admin/llamacpp/status) config=/Users/dev/.config/tldw/config.txt"
      ),
      "fallback message"
    )

    expect(message).toContain("[admin-endpoint]")
    expect(message).toContain("[redacted-path]")
    expect(message).not.toContain("/api/v1/admin/llamacpp/status")
    expect(message).not.toContain("/Users/dev/.config/tldw/config.txt")
  })

  it("returns fallback when message is missing", () => {
    expect(sanitizeAdminErrorMessage(null, "fallback message")).toBe(
      "fallback message"
    )
  })
})

