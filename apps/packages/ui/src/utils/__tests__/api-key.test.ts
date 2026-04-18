import { describe, expect, it } from "vitest"
import {
  isPlaceholderApiKey,
  LOCAL_SINGLE_USER_DEMO_KEY
} from "../api-key"

describe("isPlaceholderApiKey", () => {
  it("allows the documented local demo key", () => {
    expect(isPlaceholderApiKey(LOCAL_SINGLE_USER_DEMO_KEY)).toBe(false)
  })

  it("rejects obvious placeholder values", () => {
    expect(isPlaceholderApiKey("replace-me")).toBe(true)
    expect(isPlaceholderApiKey("YOUR_API_KEY_HERE")).toBe(true)
    expect(isPlaceholderApiKey("<replace-me>")).toBe(true)
  })
})
