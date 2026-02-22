import { describe, expect, it } from "vitest"
import { isTimeoutLikeError } from "@/utils/request-timeout"

describe("request-timeout", () => {
  it("treats AbortError as timeout-like", () => {
    const err = new Error("Aborted")
    err.name = "AbortError"
    expect(isTimeoutLikeError(err)).toBe(true)
  })

  it("treats timeout wording as timeout-like", () => {
    expect(isTimeoutLikeError(new Error("Request timed out"))).toBe(true)
    expect(isTimeoutLikeError("Extension messaging timeout")).toBe(true)
  })

  it("does not classify unrelated errors as timeout-like", () => {
    expect(isTimeoutLikeError(new Error("Unauthorized"))).toBe(false)
  })
})
