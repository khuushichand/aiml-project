import { describe, expect, it } from "vitest"
import { isPlaceholderApiKey } from "../api-key"

describe("isPlaceholderApiKey", () => {
  it("allows the documented local demo key", () => {
    expect(
      isPlaceholderApiKey("THIS-IS-A-SECURE-KEY-123-REPLACE-ME")
    ).toBe(false)
  })

  it("rejects obvious placeholder values", () => {
    expect(isPlaceholderApiKey("replace-me")).toBe(true)
    expect(isPlaceholderApiKey("YOUR_API_KEY_HERE")).toBe(true)
    expect(isPlaceholderApiKey("<replace-me>")).toBe(true)
  })
})
