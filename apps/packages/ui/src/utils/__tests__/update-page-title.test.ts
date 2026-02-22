import { afterEach, describe, expect, it, vi } from "vitest"
import { updatePageTitle } from "../update-page-title"

describe("updatePageTitle", () => {
  afterEach(() => {
    document.head.innerHTML = "<title>Reset</title>"
  })

  it("updates document.title without requiring an existing title element", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {})
    document.head.innerHTML = ""

    updatePageTitle("Chat Ready")

    expect(document.title).toBe("Chat Ready")
    expect(warnSpy).not.toHaveBeenCalled()

    warnSpy.mockRestore()
  })
})
