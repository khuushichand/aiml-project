import sidepanel from "@/assets/locale/en/sidepanel.json"
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
})
