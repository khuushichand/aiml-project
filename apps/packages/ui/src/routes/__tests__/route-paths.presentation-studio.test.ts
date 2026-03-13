import { describe, expect, it } from "vitest"
import {
  PRESENTATION_STUDIO_DETAIL_PATH,
  PRESENTATION_STUDIO_NEW_PATH,
  PRESENTATION_STUDIO_PATH,
  PRESENTATION_STUDIO_START_PATH
} from "../route-paths"

describe("route-paths presentation studio", () => {
  it("builds presentation studio route constants", () => {
    expect(PRESENTATION_STUDIO_PATH).toBe("/presentation-studio")
    expect(PRESENTATION_STUDIO_NEW_PATH).toBe("/presentation-studio/new")
    expect(PRESENTATION_STUDIO_DETAIL_PATH).toBe("/presentation-studio/:projectId")
    expect(PRESENTATION_STUDIO_START_PATH).toBe("/presentation-studio/start")
  })
})
