import { existsSync, readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

describe("web chat workflows page route", () => {
  it("exposes a Next.js page shim for chat workflows", () => {
    expect(existsSync("pages/chat-workflows.tsx")).toBe(true)

    const source = readFileSync("pages/chat-workflows.tsx", "utf8")

    expect(source).toMatch(
      /dynamic\(\(\) => import\("@\/routes\/option-chat-workflows"\), \{/
    )
    expect(source).toMatch(/ssr:\s*false/)
  })
})
