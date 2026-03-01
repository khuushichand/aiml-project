import { describe, expect, it } from "vitest"
import { createRepo2TxtStore } from "../index"

describe("repo2txt file tree slice", () => {
  it("auto-selects common code extensions", () => {
    const store = createRepo2TxtStore()
    store.getState().setNodes([{ path: "src/app.ts", type: "blob" }])
    expect(store.getState().selectedPaths.has("src/app.ts")).toBe(true)
  })
})
