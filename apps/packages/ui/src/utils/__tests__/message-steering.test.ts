import { describe, expect, it } from "vitest"
import {
  buildMessageSteeringSnippet,
  hasActiveMessageSteering,
  resolveMessageSteering
} from "../message-steering"

describe("message steering utilities", () => {
  it("prefers impersonate when both continue and impersonate are set", () => {
    const resolved = resolveMessageSteering({
      continueAsUser: true,
      impersonateUser: true,
      forceNarrate: false
    })

    expect(resolved.mode).toBe("impersonate_user")
    expect(resolved.impersonateUser).toBe(true)
    expect(resolved.continueAsUser).toBe(false)
    expect(resolved.hadConflict).toBe(true)
  })

  it("resolves continue mode from mode input", () => {
    const resolved = resolveMessageSteering({
      mode: "continue_as_user",
      forceNarrate: true
    })

    expect(resolved.mode).toBe("continue_as_user")
    expect(resolved.continueAsUser).toBe(true)
    expect(resolved.impersonateUser).toBe(false)
    expect(resolved.forceNarrate).toBe(true)
  })

  it("returns null snippet when steering is inactive", () => {
    expect(
      buildMessageSteeringSnippet({
        continueAsUser: false,
        impersonateUser: false,
        forceNarrate: false
      })
    ).toBeNull()
  })

  it("builds snippet text when steering is active", () => {
    const snippet = buildMessageSteeringSnippet({
      continueAsUser: false,
      impersonateUser: true,
      forceNarrate: true
    })

    expect(snippet).toContain("Steering instruction")
    expect(snippet).toContain("authored by the user")
    expect(snippet).toContain("narrative prose")
  })

  it("detects active steering when only force narrate is enabled", () => {
    expect(
      hasActiveMessageSteering({
        continueAsUser: false,
        impersonateUser: false,
        forceNarrate: true
      })
    ).toBe(true)
  })
})
