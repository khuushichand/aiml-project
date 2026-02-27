import { describe, expect, it } from "vitest"
import {
  buildContextSystemMessages,
  getTriggeredWorldInfoEntries,
  injectSystemMessages,
  parseWorldInfoKeysInput,
  type WritingContextSettings
} from "../writing-context-utils"

const makeSettings = (
  partial: Partial<WritingContextSettings>
): WritingContextSettings => ({
  memory_block: {
    enabled: false,
    prefix: "",
    text: "",
    suffix: ""
  },
  author_note: {
    enabled: false,
    prefix: "",
    text: "",
    suffix: "",
    insertion_depth: 1
  },
  world_info: {
    enabled: false,
    search_range: 0,
    entries: []
  },
  ...partial
})

describe("writing context utils", () => {
  it("builds system messages for memory, world info and author note", () => {
    const settings = makeSettings({
      memory_block: {
        enabled: true,
        prefix: "Memory:\n",
        text: "Alice is a detective.",
        suffix: ""
      },
      world_info: {
        enabled: true,
        search_range: 500,
        entries: [
          {
            id: "1",
            enabled: true,
            keys: ["detective"],
            content: "Use noir tone.",
            use_regex: false,
            case_sensitive: false
          }
        ]
      },
      author_note: {
        enabled: true,
        prefix: "Author note:\n",
        text: "Keep pacing tight.",
        suffix: "",
        insertion_depth: 2
      }
    })
    const messages = buildContextSystemMessages(
      "The detective enters the room.",
      settings
    )

    expect(messages).toHaveLength(3)
    expect(messages[0]).toMatchObject({
      role: "system",
      content: "Memory:\nAlice is a detective."
    })
    expect(messages[1].content).toContain("World info context:")
    expect(messages[2].content).toContain("Author note:")
    expect(messages[2].content).toContain("depth: 2")
  })

  it("matches regex world info keys", () => {
    const entries = getTriggeredWorldInfoEntries("chapter 12 begins", {
      enabled: true,
      search_range: 100,
      entries: [
        {
          id: "rx",
          enabled: true,
          keys: ["chapter\\s+\\d+"],
          content: "Add recap.",
          use_regex: true,
          case_sensitive: false
        }
      ]
    })
    expect(entries).toHaveLength(1)
    expect(entries[0].id).toBe("rx")
  })

  it("injects extra system messages after existing system prompt", () => {
    const merged = injectSystemMessages(
      [
        { role: "system", content: "Primary system prompt" },
        { role: "user", content: "Write a scene" }
      ],
      [{ role: "system", content: "Context block" }]
    )
    expect(merged.map((msg) => msg.role)).toEqual(["system", "system", "user"])
    expect(merged[0].content).toBe("Primary system prompt")
    expect(merged[1].content).toBe("Context block")
  })

  it("parses world info keys from comma and newline delimiters", () => {
    expect(parseWorldInfoKeysInput("hero,city\nvillain")).toEqual([
      "hero",
      "city",
      "villain"
    ])
  })
})
