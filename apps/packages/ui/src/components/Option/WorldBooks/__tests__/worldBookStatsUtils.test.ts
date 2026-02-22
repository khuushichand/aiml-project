import { describe, expect, it } from "vitest"
import {
  getBudgetUtilizationBand,
  getBudgetUtilizationColor,
  getBudgetUtilizationPercent,
  getTokenEstimatorNote
} from "../worldBookStatsUtils"

describe("worldBookStatsUtils", () => {
  it("calculates utilization percentage from estimated tokens and budget", () => {
    expect(getBudgetUtilizationPercent(50, 200)).toBe(25)
    expect(getBudgetUtilizationPercent(120, 100)).toBe(120)
    expect(getBudgetUtilizationPercent(0, 100)).toBe(0)
  })

  it("returns null utilization when budget is unavailable", () => {
    expect(getBudgetUtilizationPercent(100, null)).toBeNull()
    expect(getBudgetUtilizationPercent(100, 0)).toBeNull()
  })

  it("maps utilization thresholds to expected bands and colors", () => {
    expect(getBudgetUtilizationBand(69.9)).toBe("safe")
    expect(getBudgetUtilizationBand(70)).toBe("warning")
    expect(getBudgetUtilizationBand(90)).toBe("warning")
    expect(getBudgetUtilizationBand(90.1)).toBe("critical")

    expect(getBudgetUtilizationColor("safe")).toBe("#52c41a")
    expect(getBudgetUtilizationColor("warning")).toBe("#faad14")
    expect(getBudgetUtilizationColor("critical")).toBe("#ff4d4f")
  })

  it("uses estimator metadata in note copy when backend provides it", () => {
    expect(getTokenEstimatorNote({ token_estimation_method: "cl100k_base" })).toBe(
      "Estimated using cl100k_base."
    )
    expect(getTokenEstimatorNote({ tokenizer_name: "gpt-4o-mini" })).toBe(
      "Estimated using gpt-4o-mini."
    )
    expect(getTokenEstimatorNote({})).toBe("Estimated using ~4 characters per token.")
  })
})
