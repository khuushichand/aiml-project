import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("PlaygroundMessage quick actions guard", () => {
  it("keeps quick transform prompt insertion with citation references and lineage", () => {
    const messageSourcePath = path.resolve(__dirname, "../Message.tsx")
    const messageSource = fs.readFileSync(messageSourcePath, "utf8")
    const quickActionSourcePath = path.resolve(
      __dirname,
      "../quick-message-actions.ts"
    )
    const quickActionSource = fs.readFileSync(quickActionSourcePath, "utf8")

    expect(messageSource).toContain("buildQuickMessageActionPrompt")
    expect(messageSource).toContain("onQuickMessageAction")
    expect(messageSource).toContain("tldw:set-composer-message")
    expect(messageSource).toContain("buildSourceReference")
    expect(quickActionSource).toContain("Message lineage:")
    expect(quickActionSource).toContain("Keep citation markers like [1], [2]")
  })
})
