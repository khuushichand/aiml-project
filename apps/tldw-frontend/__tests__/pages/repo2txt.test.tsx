import { describe, expect, it } from "vitest"
import Repo2TxtPage from "@web/pages/repo2txt"

describe("web repo2txt page", () => {
  it("exports a page component", () => {
    expect(Repo2TxtPage).toBeTypeOf("function")
  })
})
