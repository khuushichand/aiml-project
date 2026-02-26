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
  "jobs.form.audioPracticalHint",
  "jobs.form.audioTestHint",
  "outputs.deliveryIssuesBannerDescription",
  "templates.modeHelpBasic",
  "templates.modeHelpAdvanced",
  "templates.modeBasicEditorHint",
  "templates.contentPlaceholder",
  "templates.syntaxErrorBeforeSave",
  "sources.deleteConfirmDescription",
  "sources.bulkDeleteConfirmDescription"
] as const

const FIRST_RUN_CANONICAL_TERMINOLOGY_KEYS = [
  "overview.onboarding.pipeline",
  "overview.onboarding.path.beginnerHint",
  "overview.onboarding.path.advancedHint",
  "overview.onboarding.steps.addFeed.description",
  "overview.onboarding.steps.createMonitor.description",
  "overview.onboarding.steps.reviewResults.description",
  "guide.steps.sources.description",
  "guide.steps.jobs.description",
  "guide.steps.runs.description",
  "guide.steps.items.description",
  "guide.steps.outputs.description",
  "guide.completedDescription",
  "teachPoints.jobs.description",
  "teachPoints.templates.description"
] as const

const FORBIDDEN_FIRST_RUN_ALIASES = [
  /\bsource(s)?\b/i,
  /\bjob(s)?\b/i,
  /\brun(s)?\b/i,
  /\bitem(s)?\b/i,
  /\boutput(s)?\b/i
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

  it("keeps source delete confirmations aligned with reversible undo behavior", () => {
    const labels = watchlistsLocale as JsonObject
    const singleDeleteCopy = String(getNestedValue(labels, "sources.deleteConfirmDescription") || "")
    const bulkDeleteCopy = String(getNestedValue(labels, "sources.bulkDeleteConfirmDescription") || "")

    expect(singleDeleteCopy.toLowerCase()).toContain("undo")
    expect(singleDeleteCopy.toLowerCase()).not.toContain("cannot be undone")
    expect(bulkDeleteCopy.toLowerCase()).toContain("undo")
  })

  it("keeps first-run guidance aligned with canonical watchlists terms", () => {
    const labels = watchlistsLocale as JsonObject

    for (const keyPath of FIRST_RUN_CANONICAL_TERMINOLOGY_KEYS) {
      const value = String(getNestedValue(labels, keyPath) || "")
      expect(value.trim().length, `Missing first-run copy key: ${keyPath}`).toBeGreaterThan(0)
      for (const forbiddenAlias of FORBIDDEN_FIRST_RUN_ALIASES) {
        expect(
          forbiddenAlias.test(value),
          `First-run copy should avoid system alias ${forbiddenAlias} at ${keyPath}`
        ).toBe(false)
      }
    }
  })
})
