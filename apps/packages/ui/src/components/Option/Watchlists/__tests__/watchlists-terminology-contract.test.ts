import watchlistsLocale from "../../../../assets/locale/en/watchlists.json"
import { describe, expect, it } from "vitest"

type JsonObject = Record<string, unknown>

const getNestedValue = (source: JsonObject, keyPath: string): unknown =>
  keyPath.split(".").reduce<unknown>((acc, segment) => {
    if (!acc || typeof acc !== "object") return undefined
    return (acc as JsonObject)[segment]
  }, source)

describe("Watchlists terminology contract", () => {
  it("keeps top-level tab and page labels aligned for user-facing nouns", () => {
    const labels = watchlistsLocale as JsonObject
    const pairs: Array<[string, string, string]> = [
      ["Feeds", "tabs.sources", "sources.title"],
      ["Monitors", "tabs.jobs", "jobs.title"],
      ["Activity", "tabs.runs", "runs.title"],
      ["Articles", "tabs.items", "overview.cards.items.title"],
      ["Reports", "tabs.outputs", "outputs.title"],
      ["Activity", "tabs.runs", "overview.cards.runs.title"]
    ]

    for (const [expected, tabKeyPath, sectionKeyPath] of pairs) {
      expect(getNestedValue(labels, tabKeyPath)).toBe(expected)
      expect(getNestedValue(labels, sectionKeyPath)).toBe(expected)
    }
  })

  it("uses consistent help wording for Reports and Activity", () => {
    const labels = watchlistsLocale as JsonObject
    expect(getNestedValue(labels, "help.tabs.outputs")).toBe("Reports guidance")
    expect(getNestedValue(labels, "help.tabs.runs")).toBe("Activity guidance")
  })
})
