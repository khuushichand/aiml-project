import { describe, expect, it } from "vitest"

import { isRecoverableAuthConfigError } from "@/services/auth-errors"

describe("isRecoverableAuthConfigError", () => {
  it("returns true for explicit auth status codes", () => {
    expect(
      isRecoverableAuthConfigError({
        message: "Request failed",
        status: 401
      })
    ).toBe(true)

    expect(
      isRecoverableAuthConfigError({
        message: "Forbidden",
        status: "403"
      })
    ).toBe(true)
  })

  it("returns true for auth/config message patterns", () => {
    expect(
      isRecoverableAuthConfigError(
        new Error("Invalid API key (GET /api/v1/chats/)")
      )
    ).toBe(true)

    expect(
      isRecoverableAuthConfigError(
        new Error("tldw server not configured")
      )
    ).toBe(true)
  })

  it("returns false for non-auth failures", () => {
    expect(
      isRecoverableAuthConfigError(
        new Error("Internal server error (GET /api/v1/chats/)")
      )
    ).toBe(false)
  })
})
