import { describe, expect, it } from "vitest"
import { getSourceStatusVisual } from "../sourceStatus"

describe("getSourceStatusVisual", () => {
  it("returns inactive when source is disabled", () => {
    expect(getSourceStatusVisual("ok", false)).toEqual({
      color: "default",
      label: "Inactive",
      iconToken: "neutral"
    })
  })

  it("returns mapped statuses for known values", () => {
    expect(getSourceStatusVisual("ok", true)).toEqual({
      color: "green",
      label: "Healthy",
      iconToken: "healthy"
    })
    expect(getSourceStatusVisual("deferred", true)).toEqual({
      color: "gold",
      label: "Deferred",
      iconToken: "attention"
    })
    expect(getSourceStatusVisual("failed", true)).toEqual({
      color: "red",
      label: "Failed",
      iconToken: "error"
    })
  })

  it("normalizes unknown statuses into title case", () => {
    expect(getSourceStatusVisual("source_timeout_warning", true)).toEqual({
      color: "default",
      label: "Source Timeout Warning",
      iconToken: "neutral"
    })
  })

  it("returns unknown when status is empty", () => {
    expect(getSourceStatusVisual(null, true)).toEqual({
      color: "default",
      label: "Unknown",
      iconToken: "neutral"
    })
  })
})
