import { describe, expect, it } from "vitest"
import {
  buildContextSystemMessages,
  composeContextPrompt,
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
    prefix: "",
    suffix: "",
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
        prefix: "",
        suffix: "",
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
      prefix: "",
      suffix: "",
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

  it("supports per-entry world info search range overrides", () => {
    const prompt = "alpha " + "x".repeat(60) + " omega"
    const entries = getTriggeredWorldInfoEntries(prompt, {
      enabled: true,
      search_range: 1000,
      prefix: "",
      suffix: "",
      entries: [
        {
          id: "alpha-near",
          enabled: true,
          keys: ["alpha"],
          content: "Alpha context",
          use_regex: false,
          case_sensitive: false,
          search_range: 10
        },
        {
          id: "omega-near",
          enabled: true,
          keys: ["omega"],
          content: "Omega context",
          use_regex: false,
          case_sensitive: false,
          search_range: 10
        }
      ]
    })
    expect(entries.map((entry) => entry.id)).toEqual(["omega-near"])
  })

  it("applies world info prefix and suffix to injected content", () => {
    const messages = buildContextSystemMessages("hero enters", {
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
        enabled: true,
        search_range: 100,
        prefix: "WI:\n",
        suffix: "\n<END>",
        entries: [
          {
            id: "wi-1",
            enabled: true,
            keys: ["hero"],
            content: "The hero is tired.",
            use_regex: false,
            case_sensitive: false
          }
        ]
      }
    })

    expect(messages).toHaveLength(1)
    expect(messages[0].content).toContain("WI:")
    expect(messages[0].content).toContain("The hero is tired.")
    expect(messages[0].content).toContain("<END>")
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

  it("composes prompt with context order placeholders", () => {
    const settings = makeSettings({
      memory_block: {
        enabled: true,
        prefix: "MEM:\n",
        text: "Keep tone noir.",
        suffix: "\n/MEM"
      },
      world_info: {
        enabled: true,
        search_range: 100,
        prefix: "WI:\n",
        suffix: "\n/WI",
        entries: [
          {
            id: "wi-1",
            enabled: true,
            keys: ["detective"],
            content: "City is always raining.",
            use_regex: false,
            case_sensitive: false
          }
        ]
      },
      context_order:
        "{memPrefix}{wiPrefix}{wiText}{wiSuffix}{memText}{memSuffix}\n{prompt}"
    })

    const composed = composeContextPrompt(
      "The detective lights a cigarette.",
      settings,
      { tokenRatio: 1 }
    )

    expect(composed).toContain("MEM:")
    expect(composed).toContain("WI:")
    expect(composed).toContain("City is always raining.")
    expect(composed).toContain("Keep tone noir.")
    expect(composed).toContain("The detective lights a cigarette.")
  })

  it("inserts author note by depth from bottom of truncated prompt", () => {
    const settings = makeSettings({
      author_note: {
        enabled: true,
        prefix: "AN:\n",
        text: "Raise tension.",
        suffix: "",
        insertion_depth: 1
      },
      context_order: "{prompt}",
      context_length: 100
    })

    const composed = composeContextPrompt("line1\nline2\nline3", settings, {
      tokenRatio: 1
    })

    expect(composed).toContain("AN:\nRaise tension.")
    expect(composed.indexOf("AN:\nRaise tension.")).toBeLessThan(
      composed.indexOf("line3")
    )
  })

  it("respects context budget when composing prompt", () => {
    const settings = makeSettings({
      context_order: "{prompt}",
      context_length: 10
    })
    const prompt = "0123456789ABCDEFGHIJ"
    const composed = composeContextPrompt(prompt, settings, { tokenRatio: 1 })

    expect(composed).toBe("ABCDEFGHIJ")
  })
})
