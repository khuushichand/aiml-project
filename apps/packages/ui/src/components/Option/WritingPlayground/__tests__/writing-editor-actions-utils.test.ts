import { describe, expect, it } from "vitest"
import {
  applyPlaceholderAtRange,
  applyTextAtRange
} from "../writing-editor-actions-utils"

describe("writing editor actions utils", () => {
  it("inserts predict placeholder at cursor", () => {
    const result = applyPlaceholderAtRange("Hello world", 5, 5, "{predict}")

    expect(result.nextValue).toBe("Hello{predict} world")
    expect(result.cursor).toBe(14)
  })

  it("replaces selected text with fill placeholder", () => {
    const source = "The [middle] should change"
    const start = source.indexOf("[middle]")
    const end = start + "[middle]".length

    const result = applyPlaceholderAtRange(source, start, end, "{fill}")

    expect(result.nextValue).toBe("The {fill} should change")
    expect(result.cursor).toBe("The {fill}".length)
  })

  it("normalizes out-of-range selection values", () => {
    const result = applyPlaceholderAtRange("abc", -5, 99, "{predict}")

    expect(result.nextValue).toBe("{predict}")
    expect(result.cursor).toBe("{predict}".length)
  })

  it("inserts arbitrary text at selection range", () => {
    const source = "Token slot"
    const start = source.indexOf("slot")
    const end = start + "slot".length

    const result = applyTextAtRange(source, start, end, "replacement")

    expect(result.nextValue).toBe("Token replacement")
    expect(result.cursor).toBe("Token replacement".length)
  })

  it("preserves whitespace token text", () => {
    const result = applyTextAtRange("Hello", 5, 5, " world")

    expect(result.nextValue).toBe("Hello world")
    expect(result.cursor).toBe(11)
  })
})
