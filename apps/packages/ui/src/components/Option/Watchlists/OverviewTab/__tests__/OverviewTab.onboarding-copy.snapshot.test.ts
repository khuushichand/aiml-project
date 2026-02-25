import watchlistsLocale from "../../../../../assets/locale/en/watchlists.json"
import { describe, expect, it } from "vitest"

type JsonObject = Record<string, unknown>

const pick = <T = unknown>(source: JsonObject, keyPath: string): T | undefined =>
  keyPath.split(".").reduce<unknown>((acc, segment) => {
    if (!acc || typeof acc !== "object") return undefined
    return (acc as JsonObject)[segment]
  }, source) as T | undefined

describe("Overview onboarding copy snapshot", () => {
  it("keeps quick setup and guided-tour onboarding blocks stable", () => {
    const labels = watchlistsLocale as JsonObject
    const snapshot = {
      overviewOnboarding: pick(labels, "overview.onboarding"),
      guide: pick(labels, "guide"),
      teachPoints: pick(labels, "teachPoints")
    }

    expect(snapshot).toMatchSnapshot()
  })
})
