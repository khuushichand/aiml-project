import { describe, expect, it } from "vitest"
import {
  filterCharactersForWorkspace,
  hasInlineConversationCount,
  paginateCharactersForWorkspace,
  sortCharactersForWorkspace
} from "../search-utils"

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
    tags: ["research", "analysis"],
    creator: "alice"
  },
  {
    id: 4,
    name: "Story Crafter",
    description: "Shapes narrative arcs and scene pacing.",
    tags: ["writing"],
    creator: "bob"
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

  it("filters by creator when provided", () => {
    const filtered = filterCharactersForWorkspace(SAMPLE_CHARACTERS, {
      creator: "ALICE"
    })
    expect(filtered.map((character) => character.id)).toEqual([3])
  })
})

describe("sortCharactersForWorkspace", () => {
  it("sorts by name ascending by default", () => {
    const sorted = sortCharactersForWorkspace(SAMPLE_CHARACTERS, {})
    expect(sorted.map((character) => character.id)).toEqual([2, 1, 3, 4])
  })

  it("sorts by conversation count descending", () => {
    const sorted = sortCharactersForWorkspace(
      [
        { id: "a", name: "A", conversation_count: 1 },
        { id: "b", name: "B", chat_count: 3 },
        { id: "c", name: "C", conversationCount: 2 }
      ],
      { sortBy: "conversation_count", sortOrder: "desc" }
    )
    expect(sorted.map((character) => character.id)).toEqual(["b", "c", "a"])
  })
})

describe("paginateCharactersForWorkspace", () => {
  it("returns paged items with metadata", () => {
    const paged = paginateCharactersForWorkspace(
      Array.from({ length: 23 }, (_, index) => ({ id: index + 1 })),
      { page: 2, pageSize: 10 }
    )

    expect(paged.items.map((item) => item.id)).toEqual([
      11, 12, 13, 14, 15, 16, 17, 18, 19, 20
    ])
    expect(paged.total).toBe(23)
    expect(paged.hasMore).toBe(true)
  })
})

describe("hasInlineConversationCount", () => {
  it("detects known count fields", () => {
    expect(hasInlineConversationCount({ conversation_count: 1 })).toBe(true)
    expect(hasInlineConversationCount({ chat_count: 0 })).toBe(false)
    expect(hasInlineConversationCount({ conversationCount: 4 })).toBe(true)
  })
})
