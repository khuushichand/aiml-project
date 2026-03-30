import { readdirSync, readFileSync, statSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const pageObjectsDir = path.join(process.cwd(), "e2e/utils/page-objects")
const fixedSleepGuardFiles = [
  "ChatPage.ts",
  "CharactersPage.ts",
  "EvaluationsPage.ts",
  "FlashcardsPage.ts",
  "NotesPage.ts",
  "PromptsWorkspacePage.ts",
  "SearchPage.ts",
  "WorldBooksPage.ts",
  "WritingPlaygroundPage.ts",
]

const listPageObjectFiles = (dir: string): string[] => {
  const entries = readdirSync(dir)
  const files: string[] = []

  for (const entry of entries) {
    const fullPath = path.join(dir, entry)
    const stats = statSync(fullPath)
    if (stats.isDirectory()) {
      files.push(...listPageObjectFiles(fullPath))
      continue
    }
    if (entry.endsWith("Page.ts")) {
      files.push(fullPath)
    }
  }

  return files.sort()
}

describe("e2e page object readiness contracts", () => {
  it("keeps page objects off direct networkidle waits", () => {
    const files = listPageObjectFiles(pageObjectsDir)

    for (const file of files) {
      const source = readFileSync(file, "utf8")
      expect(source).not.toContain('waitForLoadState("networkidle"')
    }
  })

  it("keeps the shared high-traffic page objects off fixed sleep retries", () => {
    const files = listPageObjectFiles(pageObjectsDir).filter((file) =>
      fixedSleepGuardFiles.includes(path.basename(file))
    )

    for (const file of files) {
      const source = readFileSync(file, "utf8")
      expect(source).not.toContain("waitForTimeout(")
    }
  })
})
