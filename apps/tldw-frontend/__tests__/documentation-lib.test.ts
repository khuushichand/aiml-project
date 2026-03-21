import { describe, expect, it } from "vitest"

import {
  listDocumentationManifest,
  readDocumentationContent,
} from "@web/lib/documentation"

describe("documentation library", () => {
  it("discovers published server documentation from the repository", async () => {
    const manifest = await listDocumentationManifest()

    expect(
      manifest.server.some(
        (doc) => doc.relativePath === "API-related/AuthNZ-API-Guide.md"
      )
    ).toBe(true)
  })

  it("reads published server documentation content", async () => {
    const content = await readDocumentationContent(
      "server",
      "API-related/AuthNZ-API-Guide.md"
    )

    expect(content).toContain("# AuthNZ API Guide")
  })

  it("rejects path traversal outside the documentation roots", async () => {
    await expect(
      readDocumentationContent("server", "../README.md")
    ).rejects.toThrow("Invalid documentation path.")
  })
})
