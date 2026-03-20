import { describe, expect, it } from "vitest"

describe("Characters utils exports", () => {
  it("re-exports resolveCharacterSelectionId for character hooks", async () => {
    const utilsModule = await import("../utils")

    expect(utilsModule.resolveCharacterSelectionId).toBeTypeOf("function")
  })
})
