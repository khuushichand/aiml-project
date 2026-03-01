import { describe, expect, it } from "vitest"
import { LocalProvider } from "../LocalProvider"

describe("LocalProvider", () => {
  it("initializes directory mode and returns blob nodes", async () => {
    const provider = new LocalProvider()
    const file = new File(["const a=1"], "src/a.ts", { type: "text/plain" })
    await provider.initialize({
      source: "directory",
      files: { 0: file, length: 1 } as unknown as FileList
    })
    const tree = await provider.fetchTree("local://directory")
    expect(tree.some((node) => node.path.includes("a.ts"))).toBe(true)
  })
})
