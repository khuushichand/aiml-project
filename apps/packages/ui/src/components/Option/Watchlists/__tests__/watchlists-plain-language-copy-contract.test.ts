import watchlistsLocale from "../../../../assets/locale/en/watchlists.json"
import { describe, expect, it } from "vitest"

type JsonObject = Record<string, unknown>

const getNestedValue = (source: JsonObject, keyPath: string): unknown =>
  keyPath.split(".").reduce<unknown>((acc, segment) => {
    if (!acc || typeof acc !== "object") return undefined
    return (acc as JsonObject)[segment]
  }, source)

const REQUIRED_PLAIN_LANGUAGE_KEYS = [
  "overview.onboarding.quickSetup.help.feed",
  "overview.onboarding.quickSetup.help.monitor",
  "overview.onboarding.quickSetup.help.review",
  "schedule.beginnerHint",
  "schedule.advancedOptionalHint",
  "schedule.cronBeginnerHint",
  "templates.modeHelpBasic",
  "templates.modeHelpAdvanced",
  "templates.modeBasicEditorHint",
  "templates.contentPlaceholder",
  "templates.syntaxErrorBeforeSave"
] as const

describe("Watchlists plain-language copy contract", () => {
  it("keeps key helper copy strings present for onboarding, scheduling, and templates", () => {
    const labels = watchlistsLocale as JsonObject

    for (const keyPath of REQUIRED_PLAIN_LANGUAGE_KEYS) {
      const value = getNestedValue(labels, keyPath)
      expect(typeof value, `Missing or non-string locale key: ${keyPath}`).toBe("string")
      expect(String(value).trim().length).toBeGreaterThan(0)
    }
  })
})
