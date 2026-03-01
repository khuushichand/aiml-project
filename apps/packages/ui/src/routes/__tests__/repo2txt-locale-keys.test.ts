import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"
import enOption from "@/assets/locale/en/option.json"

const REQUIRED_KEYS = [
  "repo2txt.nav",
  "repo2txt.title",
  "repo2txt.description",
  "repo2txt.generate",
  "header.modeRepo2txt"
] as const

const getPathValue = (source: unknown, key: string): unknown =>
  key.split(".").reduce<unknown>((value, segment) => {
    if (!value || typeof value !== "object") return undefined
    return (value as Record<string, unknown>)[segment]
  }, source)

describe("repo2txt locale keys", () => {
  it("has required English option locale keys", () => {
    for (const key of REQUIRED_KEYS) {
      const value = getPathValue(enOption as unknown, key)
      expect(typeof value).toBe("string")
      expect(String(value).trim().length).toBeGreaterThan(0)
    }
  })

  it("keeps repo2txt option keys present across locale directories", () => {
    const localeRoot = path.resolve(process.cwd(), "src/assets/locale")
    for (const locale of fs.readdirSync(localeRoot)) {
      const optionPath = path.join(localeRoot, locale, "option.json")
      expect(fs.existsSync(optionPath)).toBe(true)
      const parsed = JSON.parse(fs.readFileSync(optionPath, "utf8")) as unknown
      for (const key of REQUIRED_KEYS) {
        const value = getPathValue(parsed, key)
        expect(typeof value).toBe("string")
      }
    }
  })
})
