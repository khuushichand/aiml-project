import { describe, expect, it } from "vitest"
import {
  buildContextPreviewFilename,
  serializeContextPreviewJson
} from "../writing-context-preview-utils"

describe("writing context preview utils", () => {
  it("serializes messages to pretty JSON", () => {
    const json = serializeContextPreviewJson([
      { role: "system", content: "hello" },
      { role: "user", content: "world" }
    ])

    expect(json).toContain('"role": "system"')
    expect(json).toContain('"content": "world"')
    expect(json.split("\n").length).toBeGreaterThan(2)
  })

  it("builds stable export filename", () => {
    const filename = buildContextPreviewFilename(new Date("2026-02-26T10:15:00Z"))
    expect(filename).toBe("writing-context-preview-2026-02-26.json")
  })
})
