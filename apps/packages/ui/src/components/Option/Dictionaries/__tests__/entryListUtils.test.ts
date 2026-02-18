import { describe, expect, it } from "vitest"
import {
  buildDictionaryEntryGroupOptions,
  DICTIONARY_ENTRY_COLUMN_RESPONSIVE,
  filterDictionaryEntriesBySearchAndGroup
} from "../entryListUtils"

describe("dictionary entry list utils", () => {
  it("builds case-insensitive deduped group autocomplete options", () => {
    const options = buildDictionaryEntryGroupOptions([
      { group: "Clinical" },
      { group: "clinical" },
      { group: " Abbrev " },
      { group: "abbrev" },
      { group: "" },
      { group: null }
    ])

    expect(options).toEqual([
      { label: "Abbrev", value: "Abbrev" },
      { label: "Clinical", value: "Clinical" }
    ])
  })

  it("filters entries by search text and selected group composition", () => {
    const entries = [
      {
        id: 1,
        pattern: "BP",
        replacement: "blood pressure",
        group: "Clinical"
      },
      {
        id: 2,
        pattern: "HR",
        replacement: "heart rate",
        group: "Clinical"
      },
      {
        id: 3,
        pattern: "FYI",
        replacement: "for your information",
        group: "Chat"
      }
    ]

    expect(
      filterDictionaryEntriesBySearchAndGroup(entries, "blood", "clinical").map(
        (entry) => entry.id
      )
    ).toEqual([1])

    expect(
      filterDictionaryEntriesBySearchAndGroup(entries, "", "chat").map(
        (entry) => entry.id
      )
    ).toEqual([3])
  })

  it("defines responsive breakpoints for secondary columns", () => {
    expect(DICTIONARY_ENTRY_COLUMN_RESPONSIVE.type).toEqual(["sm"])
    expect(DICTIONARY_ENTRY_COLUMN_RESPONSIVE.probability).toEqual(["md"])
    expect(DICTIONARY_ENTRY_COLUMN_RESPONSIVE.group).toEqual(["sm"])
  })
})
