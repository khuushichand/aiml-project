import { describe, expect, it } from "vitest"
import { filterCharactersForWorkspace } from "../search-utils"

const SAMPLE_CHARACTERS = [
  {
    id: 1,
    name: "Lore Mentor",
    description: "Helps with world building and lore design.",
    tags: ["writing", "lore"]
  },
  {
    id: 2,
    name: "Code Coach",
    description: "Pair-programming helper for partial refactors.",
    tags: ["coding", "teaching"]
  },
  {
    id: 3,
    name: "Research Guide",
    description: "Summarizes papers and highlights key findings.",
    tags: ["research", "analysis"]
  }
]

describe("filterCharactersForWorkspace", () => {
  it("supports partial query matching across names", () => {
    const filtered = filterCharactersForWorkspace(SAMPLE_CHARACTERS, {
      query: "coach"
    })
    expect(filtered.map((character) => character.id)).toEqual([2])
  })

  it("supports partial query matching across descriptions", () => {
    const filtered = filterCharactersForWorkspace(SAMPLE_CHARACTERS, {
      query: "world build"
    })
    expect(filtered.map((character) => character.id)).toEqual([1])
  })

  it("matches query and tags together", () => {
    const filtered = filterCharactersForWorkspace(SAMPLE_CHARACTERS, {
      query: "guide",
      tags: ["research"]
    })
    expect(filtered.map((character) => character.id)).toEqual([3])
  })

  it("handles case-insensitive tag matching with matchAll", () => {
    const filtered = filterCharactersForWorkspace(SAMPLE_CHARACTERS, {
      tags: ["WRITING", "Lore"],
      matchAllTags: true
    })
    expect(filtered.map((character) => character.id)).toEqual([1])
  })
})

