import { describe, expect, it } from "vitest"
import {
  buildAvailableChatModelIds,
  findUnavailableChatModel,
  normalizeChatModelId
} from "../chat-model-availability"

describe("chat model availability utilities", () => {
  it("normalizes prefixed model IDs", () => {
    expect(normalizeChatModelId(" tldw:gpt-4o-mini ")).toBe("gpt-4o-mini")
  })

  it("builds available IDs from model and name fields", () => {
    const ids = buildAvailableChatModelIds([
      { model: "tldw:gpt-4o-mini" },
      { name: "claude-3-5-sonnet" },
      { model: "gpt-4o-mini" }
    ])

    expect([...ids]).toEqual(["gpt-4o-mini", "claude-3-5-sonnet"])
  })

  it("does not flag unavailable model when catalog is empty", () => {
    const unavailable = findUnavailableChatModel(["gpt-4o-mini"], new Set())
    expect(unavailable).toBeNull()
  })

  it("returns the first unavailable model ID", () => {
    const unavailable = findUnavailableChatModel(
      [" tldw:gpt-4o-mini ", "missing-model"],
      new Set(["gpt-4o-mini"])
    )
    expect(unavailable).toBe("missing-model")
  })
})
