import { describe, expect, it } from "vitest"

import {
  finalizeNormalizedOcclusionRect,
  resolveNextSelectedOcclusionId
} from "../image-occlusion"

describe("image occlusion geometry helpers", () => {
  it("creates normalized geometry from a drag regardless of drag direction", () => {
    const rect = finalizeNormalizedOcclusionRect({
      startClientX: 120,
      startClientY: 60,
      endClientX: 40,
      endClientY: 10,
      bounds: {
        left: 20,
        top: 10,
        width: 200,
        height: 100
      },
      minSizePx: 8
    })

    expect(rect).toEqual({
      x: 0.1,
      y: 0,
      width: 0.4,
      height: 0.5
    })
  })

  it("ignores small accidental drags", () => {
    const rect = finalizeNormalizedOcclusionRect({
      startClientX: 40,
      startClientY: 40,
      endClientX: 45,
      endClientY: 46,
      bounds: {
        left: 0,
        top: 0,
        width: 200,
        height: 100
      },
      minSizePx: 8
    })

    expect(rect).toBeNull()
  })

  it("selects the nearest surviving region after removal", () => {
    expect(resolveNextSelectedOcclusionId(["region-1", "region-2", "region-3"], "region-2")).toBe(
      "region-3"
    )
    expect(resolveNextSelectedOcclusionId(["region-1", "region-2"], "region-2")).toBe("region-1")
    expect(resolveNextSelectedOcclusionId(["region-1"], "region-1")).toBeNull()
  })
})
