import { describe, expect, it } from "vitest"
import {
  applyTagOperationToTags,
  buildTagUsage,
  characterHasTag,
  parseCharacterTags
} from "../tag-manager-utils"

describe("tag-manager-utils", () => {
  it("parses and normalizes tag arrays", () => {
    expect(parseCharacterTags(["alpha", " beta ", "", "alpha"])).toEqual([
      "alpha",
      "beta"
    ])
  })

  it("parses JSON tag strings", () => {
    expect(parseCharacterTags('["story", "guide", "story"]')).toEqual([
      "story",
      "guide"
    ])
  })

  it("builds usage counts sorted by frequency", () => {
    const usage = buildTagUsage([
      { tags: ["alpha", "beta"] },
      { tags: ["alpha"] },
      { tags: '["beta", "gamma"]' }
    ])
    expect(usage).toEqual([
      { tag: "alpha", count: 2 },
      { tag: "beta", count: 2 },
      { tag: "gamma", count: 1 }
    ])
  })

  it("renames tags with dedupe", () => {
    expect(applyTagOperationToTags(["alpha", "beta", "alpha"], "rename", "alpha", "beta")).toEqual([
      "beta"
    ])
  })

  it("merges tags into existing destination", () => {
    expect(applyTagOperationToTags(["source", "target", "misc"], "merge", "source", "target")).toEqual([
      "target",
      "misc"
    ])
  })

  it("deletes tags", () => {
    expect(applyTagOperationToTags(["alpha", "beta"], "delete", "beta")).toEqual([
      "alpha"
    ])
  })

  it("checks membership with normalized parsed tags", () => {
    expect(characterHasTag({ tags: '["one", "two"]' }, "two")).toBe(true)
    expect(characterHasTag({ tags: ["one", "two"] }, "three")).toBe(false)
  })
})
