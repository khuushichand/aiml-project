import { describe, expect, it } from "vitest"
import {
  buildSourceTypeCounts,
  filterItemsBySourceType,
  formatChunkPosition,
  formatSourceDate,
  getRelevanceDescriptor,
  getSourceTypeLabel,
  normalizeSourceType,
  sortSourceItems,
  type SourceListItem,
} from "../sourceListUtils"

const makeItem = (
  id: string,
  originalIndex: number,
  overrides: Partial<SourceListItem["result"]> = {}
): SourceListItem => ({
  originalIndex,
  result: {
    id,
    metadata: {
      title: `Title ${id}`,
      source_type: "media_db",
    },
    ...overrides,
  },
})

describe("sourceListUtils", () => {
  it("normalizes source types and returns friendly labels", () => {
    expect(normalizeSourceType("notes")).toBe("notes")
    expect(normalizeSourceType("unknown-type")).toBe("unknown")
    expect(getSourceTypeLabel("media_db")).toBe("Document")
    expect(getSourceTypeLabel("notes", { plural: true })).toBe("Notes")
  })

  it("builds source type counts and filters by active type", () => {
    const items = [
      makeItem("a", 0, { metadata: { source_type: "media_db" } }),
      makeItem("b", 1, { metadata: { source_type: "notes" } }),
      makeItem("c", 2, { metadata: { source_type: "notes" } }),
    ]

    expect(buildSourceTypeCounts(items.map((item) => item.result))).toEqual({
      media_db: 1,
      notes: 2,
    })
    expect(filterItemsBySourceType(items, "notes").map((item) => item.result.id)).toEqual([
      "b",
      "c",
    ])
  })

  it("formats chunk positions across common chunk id formats", () => {
    expect(formatChunkPosition("3/12")).toBe("Chunk 3 of 12")
    expect(formatChunkPosition("chunk_4_of_20")).toBe("Chunk 4 of 20")
    expect(formatChunkPosition("chunk-7")).toBe("Chunk 7")
    expect(formatChunkPosition("128")).toBe("Chunk 128")
    expect(formatChunkPosition("doc-aabbcc-uuid")).toBeNull()
  })

  it("produces relevance descriptor levels with color semantics", () => {
    expect(getRelevanceDescriptor(0.91)?.level).toBe("high")
    expect(getRelevanceDescriptor(0.67)?.level).toBe("moderate")
    expect(getRelevanceDescriptor(0.21)?.level).toBe("low")
    expect(getRelevanceDescriptor(undefined)).toBeNull()
  })

  it("sorts items by title, date, and cited-first", () => {
    const items = [
      makeItem("z", 0, {
        metadata: {
          title: "Zulu",
          source_type: "media_db",
          created_at: "2026-01-05T12:00:00.000Z",
        },
      }),
      makeItem("a", 1, {
        metadata: {
          title: "Alpha",
          source_type: "notes",
          created_at: "2026-02-05T12:00:00.000Z",
        },
      }),
      makeItem("m", 2, {
        metadata: {
          title: "Mike",
          source_type: "chats",
        },
      }),
    ]
    const cited = new Set<number>([2])

    expect(sortSourceItems(items, "title", cited).map((item) => item.result.id)).toEqual([
      "a",
      "m",
      "z",
    ])
    expect(sortSourceItems(items, "date", cited).map((item) => item.result.id)).toEqual([
      "a",
      "z",
      "m",
    ])
    expect(sortSourceItems(items, "cited", cited).map((item) => item.result.id)).toEqual([
      "m",
      "z",
      "a",
    ])
  })

  it("formats source date from metadata date keys", () => {
    const dated = makeItem("d", 0, {
      metadata: {
        source_type: "media_db",
        title: "Dated source",
        published_at: "2026-02-01T12:00:00.000Z",
      },
    })
    const formatted = formatSourceDate(dated.result)
    expect(formatted).toContain("2026")
  })
})

