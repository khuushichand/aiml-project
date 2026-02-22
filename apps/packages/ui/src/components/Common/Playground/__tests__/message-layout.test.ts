import { describe, expect, it } from "vitest"
import {
  resolveAvatarColumnAlignment,
  resolveMessageRenderSide
} from "../message-layout"

describe("message-layout", () => {
  it("keeps assistant messages on the left", () => {
    const side = resolveMessageRenderSide({
      isBot: true,
      isSystemMessage: false
    })

    expect(side).toBe("left")
    expect(resolveAvatarColumnAlignment(side)).toBe("items-end")
  })

  it("keeps system messages on the left", () => {
    const side = resolveMessageRenderSide({
      isBot: false,
      isSystemMessage: true
    })

    expect(side).toBe("left")
    expect(resolveAvatarColumnAlignment(side)).toBe("items-end")
  })

  it("moves user messages to the right", () => {
    const side = resolveMessageRenderSide({
      isBot: false,
      isSystemMessage: false
    })

    expect(side).toBe("right")
    expect(resolveAvatarColumnAlignment(side)).toBe("items-start")
  })
})
