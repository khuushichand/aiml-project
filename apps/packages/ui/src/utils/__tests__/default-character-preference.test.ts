import { describe, expect, it } from "vitest"
import {
  DEFAULT_CHARACTER_PROFILE_PREFERENCE_KEY,
  extractDefaultCharacterPreferenceId,
  isFreshChatState,
  normalizeDefaultCharacterPreferenceId,
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

  it("normalizes profile default-character values to nullable string ids", () => {
    expect(normalizeDefaultCharacterPreferenceId("  char-9  ")).toBe("char-9")
    expect(normalizeDefaultCharacterPreferenceId(7)).toBe("7")
    expect(normalizeDefaultCharacterPreferenceId("   ")).toBeNull()
    expect(normalizeDefaultCharacterPreferenceId(Number.NaN)).toBeNull()
  })

  it("extracts default-character id from profile preferences payloads", () => {
    expect(
      extractDefaultCharacterPreferenceId({
        preferences: {
          [DEFAULT_CHARACTER_PROFILE_PREFERENCE_KEY]: "char-11"
        }
      })
    ).toBe("char-11")

    expect(
      extractDefaultCharacterPreferenceId({
        preferences: {
          [DEFAULT_CHARACTER_PROFILE_PREFERENCE_KEY]: {
            value: "char-12",
            source: "user"
          }
        }
      })
    ).toBe("char-12")

    expect(extractDefaultCharacterPreferenceId({ preferences: {} })).toBeNull()
  })
})
