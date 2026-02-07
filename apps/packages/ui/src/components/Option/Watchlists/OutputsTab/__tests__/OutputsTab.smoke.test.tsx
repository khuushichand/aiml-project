import { describe, expect, it } from "vitest"
import { OutputPreviewDrawer } from "../OutputPreviewDrawer"
import { OutputsTab } from "../OutputsTab"

describe("OutputsTab modules", () => {
  it("exports stage-4 outputs components", () => {
    expect(typeof OutputsTab).toBe("function")
    expect(typeof OutputPreviewDrawer).toBe("function")
  })
})
