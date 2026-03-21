import { readFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

const testDir = path.dirname(fileURLToPath(import.meta.url))
const chatPagePath = path.resolve(testDir, "../e2e/utils/page-objects/ChatPage.ts")
const mediaPagePath = path.resolve(testDir, "../e2e/utils/page-objects/MediaPage.ts")

describe("e2e page object contracts", () => {
  it("keeps the chat workflow bound to the web chat surface contract", () => {
    const source = readFileSync(chatPagePath, "utf8")

    expect(source).not.toContain('page.getByTestId("chat-header")')
    expect(source).not.toContain('/new saved chat/i')
    expect(source).toContain("article[aria-label*='Assistant message']")
    expect(source).toContain('getByRole("log", { name: /chat messages/i })')
    expect(source).toContain("Generating response")
  })

  it("keeps the media workflow bound to the media inspector shell contract", () => {
    const source = readFileSync(mediaPagePath, "utf8")

    expect(source).not.toContain('waitForLoadState("networkidle"')
    expect(source).toContain('getByRole("heading", { name: /media inspector/i })')
    expect(source).toContain('getByTestId("media-results-list")')
  })
})
