import { describe, expect, it } from "vitest"
import { buildReferencedBySignalMap } from "../worldBookRelationshipUtils"

describe("worldBookRelationshipUtils", () => {
  it("builds referenced-by signals from keyword/content overlaps", () => {
    const result = buildReferencedBySignalMap([
      {
        entry_id: 1,
        keywords: ["castle"],
        content: "Castle location details"
      },
      {
        entry_id: 2,
        keywords: ["guard"],
        content: "Guards patrol the CASTLE walls nightly."
      },
      {
        entry_id: 3,
        keywords: ["market"],
        content: "Merchants arrive at dawn."
      }
    ])

    expect(result[1]).toEqual([
      {
        sourceEntryId: 2,
        matchedKeyword: "castle"
      }
    ])
    expect(result[2]).toBeUndefined()
    expect(result[3]).toBeUndefined()
  })

  it("ignores self references, invalid ids, and duplicate source-target matches", () => {
    const result = buildReferencedBySignalMap([
      {
        entry_id: 10,
        keywords: ["wizard", "mage"],
        content: "wizard and mage both appear here"
      },
      {
        entry_id: 11,
        keywords: ["tower"],
        content: "A wizard guards the tower. A mage guards the tower."
      },
      {
        entry_id: "invalid",
        keywords: ["wizard"],
        content: "wizard"
      }
    ])

    expect(result[10]).toEqual([
      {
        sourceEntryId: 11,
        matchedKeyword: "wizard"
      }
    ])
  })
})
