import { describe, expect, it } from "vitest"
import { resolveGenerationStopStrings } from "../writing-stop-mode-utils"

describe("writing stop mode utils", () => {
  it("uses normalized custom stop strings when basic mode is disabled", () => {
    expect(
      resolveGenerationStopStrings({
        useBasicMode: false,
        basicModeType: "max_tokens",
        customStopStrings: ["END", " ", "", "###"],
        fillSuffix: "ignored"
      })
    ).toEqual(["END", "###"])
  })

  it("returns newline stop when basic mode uses new_line", () => {
    expect(
      resolveGenerationStopStrings({
        useBasicMode: true,
        basicModeType: "new_line",
        customStopStrings: ["END"],
        fillSuffix: "ignored"
      })
    ).toEqual(["\n"])
  })

  it("derives stop string from fill suffix prefix when mode is fill_suffix", () => {
    expect(
      resolveGenerationStopStrings({
        useBasicMode: true,
        basicModeType: "fill_suffix",
        customStopStrings: [],
        fillSuffix: "  world"
      })
    ).toEqual(["wo"])
  })

  it("returns no stop when fill_suffix mode has empty suffix", () => {
    expect(
      resolveGenerationStopStrings({
        useBasicMode: true,
        basicModeType: "fill_suffix",
        customStopStrings: [],
        fillSuffix: "   "
      })
    ).toEqual([])
  })
})
