import sidepanel from "@/assets/locale/en/sidepanel.json"
import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

type JsonObject = Record<string, unknown>

const getNestedValue = (source: JsonObject, path: string): unknown =>
  path.split(".").reduce<unknown>((acc, segment) => {
    if (!acc || typeof acc !== "object") return undefined
    return (acc as JsonObject)[segment]
  }, source)

const REQUIRED_KEYS = [
  "knowledge.tabs.qaSearch",
  "knowledge.tabs.fileSearch",
  "knowledge.tabs.label",
  "knowledge.tabs.contextBadge",
  "qaSearch.searching",
  "qaSearch.generatedAnswer",
  "qaSearch.cached",
  "qaSearch.copyAnswer",
  "qaSearch.copied",
  "qaSearch.copy",
  "qaSearch.insertAnswer",
  "qaSearch.copyChunk",
  "qaSearch.insertChunk",
  "qaSearch.sourceChunks",
  "qaSearch.sourceChunksList",
  "qaSearch.strategy.standard",
  "qaSearch.strategy.agentic",
  "qaSearch.sort.label",
  "qaSearch.sort.relevance",
  "qaSearch.sort.source",
  "fileSearch.filterByType",
  "fileSearch.resultsList",
  "fileSearch.attached",
  "fileSearch.alreadyAttached",
  "fileSearch.attach",
  "fileSearch.openExternal",
  "fileSearch.open",
  "fileSearch.mediaType.video",
  "fileSearch.mediaType.audio",
  "fileSearch.mediaType.pdf",
  "fileSearch.mediaType.article",
  "fileSearch.mediaType.note",
  "fileSearch.mediaType.document",
  "fileSearch.mediaType.epub",
  "fileSearch.mediaType.html",
  "fileSearch.mediaType.xml"
] as const

describe("Knowledge panel locale keys", () => {
  it("includes Stage 4 QA/File search keys in English sidepanel locale", () => {
    for (const keyPath of REQUIRED_KEYS) {
      const value = getNestedValue(sidepanel as JsonObject, keyPath)
      expect(typeof value, `Missing or non-string locale key: ${keyPath}`).toBe(
        "string"
      )
      expect(String(value).trim().length).toBeGreaterThan(0)
    }
  })

  it("includes Stage 4 QA/File search keys across all sidepanel locale files", () => {
    const candidateRoots: string[] = [
      path.resolve(process.cwd(), "src/assets/locale"),
      path.resolve(process.cwd(), "apps/packages/ui/src/assets/locale")
    ]

    if (typeof import.meta.url === "string" && import.meta.url.startsWith("file:")) {
      const testDir = path.dirname(
        decodeURIComponent(new URL(import.meta.url).pathname)
      )
      candidateRoots.unshift(path.resolve(testDir, "../../../assets/locale"))
    }

    const localeRoot = candidateRoots.find((candidate) =>
      fs.existsSync(candidate)
    )
    expect(localeRoot, "Unable to locate locale root directory").toBeDefined()
    if (!localeRoot) return
    const localeDirs = fs
      .readdirSync(localeRoot, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name)
      .sort()

    for (const locale of localeDirs) {
      const sidepanelPath = path.join(localeRoot, locale, "sidepanel.json")
      expect(
        fs.existsSync(sidepanelPath),
        `Missing sidepanel locale file: ${sidepanelPath}`
      ).toBe(true)

      const parsed = JSON.parse(
        fs.readFileSync(sidepanelPath, "utf8")
      ) as JsonObject

      for (const keyPath of REQUIRED_KEYS) {
        const value = getNestedValue(parsed, keyPath)
        expect(
          typeof value,
          `Missing or non-string locale key: ${locale}.${keyPath}`
        ).toBe("string")
        expect(String(value).trim().length).toBeGreaterThan(0)
      }
    }
  })
})
