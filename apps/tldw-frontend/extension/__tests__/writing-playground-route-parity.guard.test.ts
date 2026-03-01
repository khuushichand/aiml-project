import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("writing playground route parity", () => {
  it("keeps shared PageShell and WritingPlayground mount parity", () => {
    const webRoute = fs.readFileSync(
      path.resolve(__dirname, "../../../packages/ui/src/routes/option-writing-playground.tsx"),
      "utf8"
    )
    const extRoute = fs.readFileSync(
      path.resolve(__dirname, "../routes/option-writing-playground.tsx"),
      "utf8"
    )

    expect(webRoute).toContain('PageShell className="py-6" maxWidthClassName="max-w-7xl"')
    expect(extRoute).toContain('PageShell className="py-6" maxWidthClassName="max-w-7xl"')
    expect(webRoute).toContain("<WritingPlayground />")
    expect(extRoute).toContain("<WritingPlayground />")
  })
})
