import { describe, expect, it } from "vitest"
import {
  mapServerSearchItemsToLocalPrompts,
  matchesPromptSearchText,
  matchesTagFilter
} from "../custom-prompts-utils"

describe("custom-prompts-utils", () => {
  it("supports tag match mode any and all", () => {
    expect(matchesTagFilter(["coding", "python"], ["python", "tests"], "any")).toBe(true)
    expect(matchesTagFilter(["coding", "python"], ["python", "tests"], "all")).toBe(false)
    expect(matchesTagFilter(["coding", "python"], ["coding", "python"], "all")).toBe(true)
    expect(matchesTagFilter(["coding"], [], "all")).toBe(true)
  })

  it("matches local prompt search text across core fields", () => {
    const prompt = {
      title: "Refactor helper",
      author: "qa",
      details: "Focus on resilience",
      system_prompt: "You are strict",
      user_prompt: "Improve tests"
    }

    expect(
      matchesPromptSearchText(prompt, "resilience", () => ["backend"])
    ).toBe(true)
    expect(
      matchesPromptSearchText(prompt, "backend", () => ["backend"])
    ).toBe(true)
    expect(
      matchesPromptSearchText(prompt, "missing", () => ["backend"])
    ).toBe(false)
  })

  it("maps server search rows to local prompts by serverId preserving server order", () => {
    const mapped = mapServerSearchItemsToLocalPrompts(
      [
        {
          id: 22,
          uuid: "s2",
          name: "Second"
        },
        {
          id: 11,
          uuid: "s1",
          name: "First"
        }
      ],
      [
        { id: "local-1", serverId: 11, name: "First local" },
        { id: "local-2", serverId: 22, name: "Second local" },
        { id: "local-3", name: "Unsynced local" }
      ]
    )

    expect(mapped.map((item) => item.id)).toEqual(["local-2", "local-1"])
  })
})
