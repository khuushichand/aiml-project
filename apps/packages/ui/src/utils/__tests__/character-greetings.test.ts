import { describe, expect, it } from "vitest"
import {
  collectGreetingEntries,
  collectGreetings,
  normalizeGreetingValue
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
})
