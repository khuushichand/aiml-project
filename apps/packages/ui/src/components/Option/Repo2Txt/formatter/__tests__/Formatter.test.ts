import { describe, expect, it } from "vitest"
import { Formatter } from "../Formatter"

describe("Formatter", () => {
  it("returns directory tree and token count", async () => {
    const output = await Formatter.formatAsync(
      [{ name: "a.ts", path: "a.ts", type: "file" }],
      [{ path: "a.ts", text: "const a=1" }]
    )
    expect(output.directoryTree).toContain("a.ts")
    expect(output.tokenCount).toBeGreaterThan(0)
  })
})
