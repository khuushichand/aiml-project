import { describe, expect, it } from "vitest"
import { moveWorldInfoEntry } from "../writing-world-info-utils"

const makeEntries = () => [
  {
    id: "entry-1",
    enabled: true,
    keys: ["one"],
    content: "One",
    use_regex: false,
    case_sensitive: false
  },
  {
    id: "entry-2",
    enabled: true,
    keys: ["two"],
    content: "Two",
    use_regex: false,
    case_sensitive: false
  },
  {
    id: "entry-3",
    enabled: true,
    keys: ["three"],
    content: "Three",
    use_regex: false,
    case_sensitive: false
  }
]

describe("writing world info utils", () => {
  it("moves an entry up by one position", () => {
    const next = moveWorldInfoEntry(makeEntries(), "entry-3", "up")
    expect(next.map((entry) => entry.id)).toEqual([
      "entry-1",
      "entry-3",
      "entry-2"
    ])
  })

  it("moves an entry down by one position", () => {
    const next = moveWorldInfoEntry(makeEntries(), "entry-1", "down")
    expect(next.map((entry) => entry.id)).toEqual([
      "entry-2",
      "entry-1",
      "entry-3"
    ])
  })

  it("keeps order when target is already at boundary", () => {
    const top = makeEntries()
    const bottom = makeEntries()

    expect(moveWorldInfoEntry(top, "entry-1", "up").map((entry) => entry.id)).toEqual(
      ["entry-1", "entry-2", "entry-3"]
    )
    expect(
      moveWorldInfoEntry(bottom, "entry-3", "down").map((entry) => entry.id)
    ).toEqual(["entry-1", "entry-2", "entry-3"])
  })

  it("keeps order for unknown entry ids", () => {
    const next = moveWorldInfoEntry(makeEntries(), "missing", "up")
    expect(next.map((entry) => entry.id)).toEqual([
      "entry-1",
      "entry-2",
      "entry-3"
    ])
  })
})
