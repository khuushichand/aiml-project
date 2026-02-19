import { describe, expect, it } from "vitest"
import type { WatchlistGroup } from "@/types/watchlists"
import {
  collectDescendantGroupIds,
  isGroupParentAssignmentCyclic
} from "../group-hierarchy"

const groupsFixture: WatchlistGroup[] = [
  { id: 1, name: "Root", parent_group_id: null },
  { id: 2, name: "Child", parent_group_id: 1 },
  { id: 3, name: "Grandchild", parent_group_id: 2 },
  { id: 4, name: "Sibling", parent_group_id: null }
]

describe("group hierarchy guardrails", () => {
  it("collects nested descendants for a group", () => {
    const descendants = collectDescendantGroupIds(groupsFixture, 1)
    expect(descendants.has(2)).toBe(true)
    expect(descendants.has(3)).toBe(true)
    expect(descendants.has(4)).toBe(false)
  })

  it("flags direct self-parent assignments as cyclic", () => {
    expect(isGroupParentAssignmentCyclic(groupsFixture, 2, 2)).toBe(true)
  })

  it("flags parent assignment to a descendant as cyclic", () => {
    expect(isGroupParentAssignmentCyclic(groupsFixture, 1, 3)).toBe(true)
  })

  it("allows parent assignment to unrelated groups", () => {
    expect(isGroupParentAssignmentCyclic(groupsFixture, 2, 4)).toBe(false)
  })

  it("treats null/undefined parent assignments as non-cyclic", () => {
    expect(isGroupParentAssignmentCyclic(groupsFixture, 2, null)).toBe(false)
    expect(isGroupParentAssignmentCyclic(groupsFixture, 2, undefined)).toBe(false)
  })
})

