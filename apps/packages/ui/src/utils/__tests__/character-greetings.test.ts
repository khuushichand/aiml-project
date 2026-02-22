import { describe, expect, it } from "vitest"
import {
  buildGreetingOptionsFromEntries,
  buildGreetingsChecksumFromOptions,
  collectGreetingEntries,
  collectGreetings,
  normalizeGreetingValue,
  parseGreetingSelectionIndex,
  resolveGreetingSelection
} from "../character-greetings"

describe("character greetings utils", () => {
  it("parses JSON-string greeting lists", () => {
    expect(normalizeGreetingValue('["Hi there","Welcome back"]')).toEqual([
      "Hi there",
      "Welcome back"
    ])
  })

  it("parses double-encoded JSON-string greeting lists", () => {
    expect(
      normalizeGreetingValue('"[\\"One\\", \\"Two\\", \\"Three\\"]"')
    ).toEqual(["One", "Two", "Three"])
  })

  it("keeps multiline single greetings intact", () => {
    expect(normalizeGreetingValue("Hello there.\nHow are you today?")).toEqual([
      "Hello there.\nHow are you today?"
    ])
  })

  it("collects primary and alternate greetings from mixed payloads", () => {
    const character = {
      first_message: "Hello!",
      alternate_greetings: '["Hey there!","Welcome!"]'
    }
    expect(collectGreetings(character)).toEqual([
      "Hello!",
      "Hey there!",
      "Welcome!"
    ])

    const entries = collectGreetingEntries(character)
    expect(entries.map((entry) => entry.text)).toEqual([
      "Hello!",
      "Hey there!",
      "Welcome!"
    ])
  })

  it("parses greeting selection indices from id formats", () => {
    expect(parseGreetingSelectionIndex("greeting:2:abc123")).toBe(2)
    expect(parseGreetingSelectionIndex("greeting:4:selected")).toBe(4)
    expect(parseGreetingSelectionIndex("greeting:-1:selected")).toBeNull()
    expect(parseGreetingSelectionIndex("invalid")).toBeNull()
  })

  it("resolves greeting by stored selection id", () => {
    const character = {
      greeting: "Primary",
      alternateGreetings: ["Secondary"]
    }
    const options = buildGreetingOptionsFromEntries(
      collectGreetingEntries(character)
    )
    const checksum = buildGreetingsChecksumFromOptions(options)
    const selectedOption = options[1]
    if (!selectedOption) {
      throw new Error("Expected alternate greeting option")
    }

    const result = resolveGreetingSelection({
      options,
      greetingSelectionId: selectedOption.id,
      greetingsChecksum: checksum,
      useCharacterDefault: false,
      fallback: "first"
    })

    expect(result.option?.text).toBe("Secondary")
    expect(result.isStale).toBe(false)
  })

  it("resolves greeting by legacy index id when hash differs", () => {
    const options = buildGreetingOptionsFromEntries(
      collectGreetingEntries({
        greeting: "Primary",
        alternate_greetings: ["Secondary"]
      })
    )
    const checksum = buildGreetingsChecksumFromOptions(options)

    const result = resolveGreetingSelection({
      options,
      greetingSelectionId: "greeting:1:selected",
      greetingsChecksum: checksum,
      useCharacterDefault: false,
      fallback: "first"
    })

    expect(result.option?.text).toBe("Secondary")
    expect(result.isStale).toBe(false)
  })

  it("falls back to first greeting when stored checksum is stale", () => {
    const options = buildGreetingOptionsFromEntries(
      collectGreetingEntries({
        greeting: "Primary",
        alternate_greetings: ["Secondary"]
      })
    )

    const result = resolveGreetingSelection({
      options,
      greetingSelectionId: options[1]?.id ?? null,
      greetingsChecksum: "stale-checksum",
      useCharacterDefault: false,
      fallback: "first"
    })

    expect(result.option?.text).toBe("Primary")
    expect(result.isStale).toBe(true)
  })
})
