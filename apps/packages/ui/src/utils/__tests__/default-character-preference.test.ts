import { describe, expect, it } from "vitest"
import {
  isFreshChatState,
  resolveCharacterSelectionId,
  shouldApplyDefaultCharacter,
  shouldResetDefaultCharacterBootstrap
} from "../default-character-preference"

describe("default-character-preference helpers", () => {
  it("normalizes character ids from string and number values", () => {
    expect(resolveCharacterSelectionId({ id: "  abc  " } as any)).toBe("abc")
    expect(resolveCharacterSelectionId({ id: 42 } as any)).toBe("42")
    expect(resolveCharacterSelectionId({ id: "" } as any)).toBeNull()
    expect(resolveCharacterSelectionId({ id: Number.NaN } as any)).toBeNull()
  })

  it("detects fresh chat state when there is no server chat id and no messages", () => {
    expect(isFreshChatState(null, 0)).toBe(true)
    expect(isFreshChatState("", 0)).toBe(true)
    expect(isFreshChatState("chat-1", 0)).toBe(false)
    expect(isFreshChatState(null, 1)).toBe(false)
  })

  it("applies default character only when chat is fresh and there is no explicit selection", () => {
    expect(
      shouldApplyDefaultCharacter({
        defaultCharacterId: "char-1",
        selectedCharacterId: null,
        isFreshChat: true,
        hasAppliedInSession: false
      })
    ).toBe(true)

    expect(
      shouldApplyDefaultCharacter({
        defaultCharacterId: "char-1",
        selectedCharacterId: "char-explicit",
        isFreshChat: true,
        hasAppliedInSession: false
      })
    ).toBe(false)

    expect(
      shouldApplyDefaultCharacter({
        defaultCharacterId: "char-1",
        selectedCharacterId: null,
        isFreshChat: false,
        hasAppliedInSession: false
      })
    ).toBe(false)

    expect(
      shouldApplyDefaultCharacter({
        defaultCharacterId: "char-1",
        selectedCharacterId: null,
        isFreshChat: true,
        hasAppliedInSession: true
      })
    ).toBe(false)
  })

  it("resets bootstrap state only when chat transitions from active to fresh", () => {
    expect(shouldResetDefaultCharacterBootstrap(false, true)).toBe(true)
    expect(shouldResetDefaultCharacterBootstrap(true, true)).toBe(false)
    expect(shouldResetDefaultCharacterBootstrap(false, false)).toBe(false)
    expect(shouldResetDefaultCharacterBootstrap(true, false)).toBe(false)
  })
})
