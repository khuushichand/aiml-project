import { describe, expect, it } from "vitest"
import {
  buildExtraBodyPayload,
  parseExtraBodyJsonObject,
  parseStringListInput,
  sanitizeExtraBodyPayload
} from "../extra-body-utils"

describe("writing extra_body utils", () => {
  it("builds extra_body payload from base settings and advanced fields", () => {
    const payload = buildExtraBodyPayload({
      top_k: 40,
      seed: 123,
      stop: ["END", "", "  ", "###"],
      advanced_extra_body: {
        typical_p: 0.95,
        repeat_penalty: 1.1,
        ignore_eos: false,
        banned_tokens: ["foo", "", " bar "],
        grammar: "root ::= [a-z]+"
      }
    })

    expect(payload).toEqual({
      typical_p: 0.95,
      repeat_penalty: 1.1,
      ignore_eos: false,
      banned_tokens: ["foo", "bar"],
      grammar: "root ::= [a-z]+",
      top_k: 40,
      seed: 123,
      stop: ["END", "###"]
    })
  })

  it("returns undefined when nothing should be sent", () => {
    const payload = buildExtraBodyPayload({
      top_k: 0,
      seed: null,
      stop: [],
      advanced_extra_body: {
        grammar: "   ",
        banned_tokens: [],
        typical_p: null
      }
    })

    expect(payload).toBeUndefined()
  })

  it("sanitizes nested payload values but keeps false and zero", () => {
    const sanitized = sanitizeExtraBodyPayload({
      enabled: false,
      score: 0,
      empty: "",
      whitespace: "   ",
      list: ["one", "", " two ", "   "],
      nested: {
        keep: "x",
        drop: ""
      }
    })

    expect(sanitized).toEqual({
      enabled: false,
      score: 0,
      list: ["one", "two"],
      nested: {
        keep: "x"
      }
    })
  })

  it("parses comma and newline separated lists", () => {
    expect(parseStringListInput("one,two\nthree\r\nfour")).toEqual([
      "one",
      "two",
      "three",
      "four"
    ])
    expect(parseStringListInput("  a  ,  b  \n\nc  ")).toEqual(["a", "b", "c"])
  })

  it("parses a JSON object string and sanitizes it", () => {
    const result = parseExtraBodyJsonObject(
      "{\"mirostat\":2,\"grammar\":\"  root ::= .+  \",\"empty\":\"\"}"
    )
    expect(result.error).toBeNull()
    expect(result.value).toEqual({
      mirostat: 2,
      grammar: "root ::= .+"
    })
  })

  it("rejects non-object JSON payloads", () => {
    const listResult = parseExtraBodyJsonObject("[1,2,3]")
    expect(listResult.error).toContain("JSON object")
    expect(listResult.value).toEqual({})

    const invalidResult = parseExtraBodyJsonObject("{oops")
    expect(invalidResult.error).toContain("Invalid JSON")
    expect(invalidResult.value).toEqual({})
  })
})
