import { describe, expect, it } from "vitest"
import {
  buildDuplicateDictionaryName,
  compareDictionaryActive,
  compareDictionaryEntryCount,
  compareDictionaryName,
  filterDictionariesBySearch,
  formatRelativeTimestamp
} from "../listUtils"

describe("dictionary list utils", () => {
  it("filters dictionaries by name and description case-insensitively", () => {
    const dictionaries = [
      { id: 1, name: "Medical Terms", description: "Abbreviations" },
      { id: 2, name: "Chat Speak", description: "casual slang" },
      { id: 3, name: "Engineering", description: "Infra acronyms" }
    ]

    expect(filterDictionariesBySearch(dictionaries, "medical")).toEqual([
      dictionaries[0]
    ])
    expect(filterDictionariesBySearch(dictionaries, "SLaNg")).toEqual([
      dictionaries[1]
    ])
    expect(filterDictionariesBySearch(dictionaries, "")).toEqual(dictionaries)
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
})

