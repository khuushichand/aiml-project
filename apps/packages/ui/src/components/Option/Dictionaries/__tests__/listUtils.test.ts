import { describe, expect, it } from "vitest"
import {
  buildDictionaryDeactivationWarning,
  buildDictionaryDeletionConfirmationCopy,
  buildDuplicateDictionaryName,
  compareDictionaryActive,
  compareDictionaryEntryCount,
  compareDictionaryName,
  filterDictionariesBySearch,
  isDictionaryVersionConflictError,
  formatDictionaryChatReferenceTitle,
  formatDictionaryUsageLabel,
  formatRelativeTimestamp,
  normalizeDictionaryTags,
  normalizeDictionaryChatState,
  resolveDictionaryChatReferenceId
} from "../listUtils"

describe("dictionary list utils", () => {
  it("filters dictionaries by name and description case-insensitively", () => {
    const dictionaries = [
      {
        id: 1,
        name: "Medical Terms",
        description: "Abbreviations",
        category: "Clinical",
        tags: ["medicine", "provider"]
      },
      { id: 2, name: "Chat Speak", description: "casual slang" },
      { id: 3, name: "Engineering", description: "Infra acronyms" }
    ]

    expect(filterDictionariesBySearch(dictionaries, "medical")).toEqual([
      dictionaries[0]
    ])
    expect(filterDictionariesBySearch(dictionaries, "SLaNg")).toEqual([
      dictionaries[1]
    ])
    expect(filterDictionariesBySearch(dictionaries, "clinical")).toEqual([
      dictionaries[0]
    ])
    expect(filterDictionariesBySearch(dictionaries, "provider")).toEqual([
      dictionaries[0]
    ])
    expect(filterDictionariesBySearch(dictionaries, "")).toEqual(dictionaries)
  })

  it("normalizes dictionary tags from list and string representations", () => {
    expect(normalizeDictionaryTags(["One", " two ", "ONE"])).toEqual(["One", "two"])
    expect(normalizeDictionaryTags('["alpha","beta"]')).toEqual(["alpha", "beta"])
    expect(normalizeDictionaryTags("foo, bar")).toEqual(["foo", "bar"])
    expect(normalizeDictionaryTags("")).toEqual([])
  })

  it("sorts by dictionary name alphabetically", () => {
    const dictionaries = [
      { name: "zeta" },
      { name: "Alpha" },
      { name: "beta" }
    ]
    const sorted = [...dictionaries].sort(compareDictionaryName)
    expect(sorted.map((item) => item.name)).toEqual(["Alpha", "beta", "zeta"])
  })

  it("sorts by entry count numerically", () => {
    const dictionaries = [
      { entry_count: 10 },
      { entry_count: 2 },
      { entry_count: 25 }
    ]
    const sorted = [...dictionaries].sort(compareDictionaryEntryCount)
    expect(sorted.map((item) => item.entry_count)).toEqual([2, 10, 25])
  })

  it("sorts by active status with inactive first", () => {
    const dictionaries = [
      { id: 1, is_active: true },
      { id: 2, is_active: false },
      { id: 3, is_active: true }
    ]
    const sorted = [...dictionaries].sort(compareDictionaryActive)
    expect(sorted.map((item) => item.id)).toEqual([2, 1, 3])
  })

  it("formats recent timestamps as relative time", () => {
    const now = new Date("2026-02-18T12:00:00Z")
    const oneHourAgo = "2026-02-18T11:00:00Z"
    const twoDaysAgo = "2026-02-16T12:00:00Z"
    expect(formatRelativeTimestamp(oneHourAgo, now)).toBe("1 hour ago")
    expect(formatRelativeTimestamp(twoDaysAgo, now)).toBe("2 days ago")
    expect(formatRelativeTimestamp(null, now)).toBe("—")
  })

  it("builds unique duplicate names with copy suffixes", () => {
    const existing = [
      "Medical Terms",
      "Medical Terms (copy)",
      "medical terms (copy 2)"
    ]
    expect(buildDuplicateDictionaryName("Medical Terms", existing)).toBe(
      "Medical Terms (copy 3)"
    )
    expect(buildDuplicateDictionaryName("Chat Speak", existing)).toBe(
      "Chat Speak (copy)"
    )
  })

  it("formats used-by labels with active context", () => {
    expect(
      formatDictionaryUsageLabel({ used_by_chat_count: 0, used_by_active_chat_count: 0 })
    ).toBe("—")
    expect(
      formatDictionaryUsageLabel({ used_by_chat_count: 2, used_by_active_chat_count: 0 })
    ).toBe("2 chats")
    expect(
      formatDictionaryUsageLabel({ used_by_chat_count: 5, used_by_active_chat_count: 2 })
    ).toBe("5 chats (2 active)")
  })

  it("normalizes chat references for list/table renderers", () => {
    expect(resolveDictionaryChatReferenceId({ chat_id: "abc-123" })).toBe("abc-123")
    expect(resolveDictionaryChatReferenceId({ id: 42 })).toBe("42")
    expect(resolveDictionaryChatReferenceId(null)).toBe("")

    expect(formatDictionaryChatReferenceTitle({ chat_id: "abcdef123456", title: "" })).toBe(
      "Chat abcdef12"
    )
    expect(formatDictionaryChatReferenceTitle({ id: "chat-7", title: "Triage Session" })).toBe(
      "Triage Session"
    )

    expect(normalizeDictionaryChatState("resolved")).toBe("resolved")
    expect(normalizeDictionaryChatState(" backlog ")).toBe("backlog")
    expect(normalizeDictionaryChatState("unknown")).toBe("in-progress")
  })

  it("builds deactivation warning only when active chats are linked", () => {
    expect(
      buildDictionaryDeactivationWarning(
        { used_by_chat_count: 2, used_by_active_chat_count: 0 },
        "Cancel"
      )
    ).toBeNull()

    const warning = buildDictionaryDeactivationWarning(
      { used_by_chat_count: 3, used_by_active_chat_count: 1 },
      "Cancel"
    )
    expect(warning).not.toBeNull()
    expect(warning?.title).toBe("Deactivate dictionary?")
    expect(warning?.content).toContain("1 active chat session")
    expect(warning?.content).toContain("3 linked chat sessions")
  })

  it("builds deletion confirmation copy with linked chat context", () => {
    expect(
      buildDictionaryDeletionConfirmationCopy({
        used_by_chat_count: 0,
        used_by_active_chat_count: 0
      })
    ).toBe("Delete dictionary?")

    expect(
      buildDictionaryDeletionConfirmationCopy({
        used_by_chat_count: 2,
        used_by_active_chat_count: 0
      })
    ).toContain("linked to 2 chat session(s)")

    expect(
      buildDictionaryDeletionConfirmationCopy({
        used_by_chat_count: 4,
        used_by_active_chat_count: 1
      })
    ).toContain("including 1 active session(s)")
  })

  it("detects optimistic-locking version conflicts without flagging name conflicts", () => {
    expect(
      isDictionaryVersionConflictError(
        new Error("Dictionary was modified by another session. Expected version 2, current version 3.")
      )
    ).toBe(true)
    expect(
      isDictionaryVersionConflictError(new Error("409 conflict: expected version mismatch"))
    ).toBe(true)
    expect(
      isDictionaryVersionConflictError(new Error("Dictionary name already exists"))
    ).toBe(false)
  })
})
