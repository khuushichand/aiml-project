import { describe, expect, it } from "vitest"
import fs from "node:fs"
import path from "node:path"

describe("PlaygroundMessage lazy Markdown guard", () => {
  it("wraps greeting Markdown rendering in React.Suspense", () => {
    const sourcePath = path.resolve(__dirname, "../Message.tsx")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(
      source
    ).toMatch(
      /renderGreetingMarkdown\s*\?\s*\(\s*<React\.Suspense[\s\S]*?<Markdown[\s\S]*?<\/React\.Suspense>/m
    )
    expect(source).not.toMatch(/renderGreetingMarkdown\s*\?\s*\(\s*<Markdown/m)
  })
})
