import { describe, expect, it } from "vitest"
import {
  getPromptCollectionMembershipId,
  isPromptInCollection,
  mergePromptIdsForCollection
} from "../prompt-collections-utils"

describe("prompt-collections-utils", () => {
  it("prefers server id for collection membership when available", () => {
    expect(getPromptCollectionMembershipId({ id: "local-1", serverId: 42 })).toBe(42)
  })

  it("falls back to numeric local ids for collection membership", () => {
    expect(getPromptCollectionMembershipId({ id: 7 })).toBe(7)
    expect(getPromptCollectionMembershipId({ id: "11" })).toBe(11)
  })

  it("treats prompts without numeric ids as non-members", () => {
    const ids = new Set([1, 2, 3])
    expect(isPromptInCollection({ id: "local-abc" }, ids)).toBe(false)
  })

  it("merges collection prompt ids while reporting added and skipped rows", () => {
    const result = mergePromptIdsForCollection(
      [10, 20, 20],
      [
        { id: "30" },
        { id: "local-only" },
        { serverId: 40 },
        { serverId: 20 }
      ]
    )

    expect(result.promptIds).toEqual([10, 20, 30, 40])
    expect(result.added).toBe(2)
    expect(result.skipped).toBe(1)
  })
})

