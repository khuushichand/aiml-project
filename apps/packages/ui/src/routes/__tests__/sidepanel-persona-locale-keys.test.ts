import sidepanel from "@/assets/locale/en/sidepanel.json"
import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

type JsonObject = Record<string, unknown>

const getNestedValue = (source: JsonObject, keyPath: string): unknown =>
  keyPath.split(".").reduce<unknown>((acc, segment) => {
    if (!acc || typeof acc !== "object") return undefined
    return (acc as JsonObject)[segment]
  }, source)

const REQUIRED_PERSONA_PROMPT_KEYS = [
  "persona.unsavedStateDiscardPrompt",
  "persona.unsavedStateDiscardPromptConnect",
  "persona.unsavedStateDiscardPromptDisconnect",
  "persona.unsavedStateDiscardPromptReloadState",
  "persona.unsavedStateDiscardPromptPersonaSwitch",
  "persona.unsavedStateDiscardPromptSessionSwitch",
  "persona.unsavedStateDiscardPromptRestoreState",
  "persona.unsavedStateDiscardPromptRouteTransition",
  "persona.unsavedStateBeforeUnloadPrompt"
] as const

const PRIORITY_LOCALIZED_LOCALES = ["es", "fr", "de", "zh", "ja-JP"] as const

const resolveLocaleRoot = (): string | undefined => {
  const candidateRoots: string[] = [
    path.resolve(process.cwd(), "src/assets/locale"),
    path.resolve(process.cwd(), "apps/packages/ui/src/assets/locale")
  ]

  if (typeof import.meta.url === "string" && import.meta.url.startsWith("file:")) {
    const testDir = path.dirname(decodeURIComponent(new URL(import.meta.url).pathname))
    candidateRoots.unshift(path.resolve(testDir, "../../assets/locale"))
  }

  return candidateRoots.find((candidate) => fs.existsSync(candidate))
}

describe("Sidepanel persona locale keys", () => {
  it("includes unsaved-draft persona prompt keys in English sidepanel locale", () => {
    for (const keyPath of REQUIRED_PERSONA_PROMPT_KEYS) {
      const value = getNestedValue(sidepanel as JsonObject, keyPath)
      expect(typeof value, `Missing or non-string locale key: ${keyPath}`).toBe(
        "string"
      )
      expect(String(value).trim().length).toBeGreaterThan(0)
    }
  })

  it("keeps persona prompt keys present across all sidepanel locale files", () => {
    const localeRoot = resolveLocaleRoot()
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

      const parsed = JSON.parse(fs.readFileSync(sidepanelPath, "utf8")) as JsonObject
      for (const keyPath of REQUIRED_PERSONA_PROMPT_KEYS) {
        const value = getNestedValue(parsed, keyPath)
        expect(
          typeof value,
          `Missing or non-string locale key: ${locale}.${keyPath}`
        ).toBe("string")
        expect(String(value).trim().length).toBeGreaterThan(0)
      }
    }
  })

  it("uses localized (non-English) persona prompt copy for priority locales", () => {
    const localeRoot = resolveLocaleRoot()
    expect(localeRoot, "Unable to locate locale root directory").toBeDefined()
    if (!localeRoot) return

    const englishSidepanel = sidepanel as JsonObject
    for (const locale of PRIORITY_LOCALIZED_LOCALES) {
      const sidepanelPath = path.join(localeRoot, locale, "sidepanel.json")
      expect(
        fs.existsSync(sidepanelPath),
        `Missing sidepanel locale file: ${sidepanelPath}`
      ).toBe(true)

      const parsed = JSON.parse(fs.readFileSync(sidepanelPath, "utf8")) as JsonObject
      for (const keyPath of REQUIRED_PERSONA_PROMPT_KEYS) {
        const localizedValue = String(getNestedValue(parsed, keyPath) || "").trim()
        const englishValue = String(getNestedValue(englishSidepanel, keyPath) || "").trim()
        expect(
          localizedValue.length > 0,
          `Missing localized value: ${locale}.${keyPath}`
        ).toBe(true)
        expect(
          localizedValue === englishValue,
          `Expected localized copy for ${locale}.${keyPath}, but value still matches English`
        ).toBe(false)
      }
    }
  })
})
