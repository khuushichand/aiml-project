import { describe, expect, it } from "vitest"
import {
  buildDictionaryImportPreview,
  buildRenamedImportPreview,
  extractFileStem,
} from "../components/dictionaryImportPreviewUtils"

describe("dictionaryImportPreviewUtils", () => {
  describe("extractFileStem", () => {
    it("returns a safe stem from file names", () => {
      expect(extractFileStem("medical-dict.json")).toBe("medical-dict")
      expect(extractFileStem("README")).toBe("README")
      expect(extractFileStem("   ")).toBe("Imported Dictionary")
    })
  })

  describe("buildDictionaryImportPreview", () => {
    it("returns mode-specific empty-source validation error", () => {
      const fileResult = buildDictionaryImportPreview({
        importFormat: "json",
        importMode: "file",
        importSourceContent: "   ",
        importMarkdownName: "",
      })
      expect(fileResult.preview).toBeNull()
      expect(fileResult.errors).toEqual([
        "Select a file before generating an import preview.",
      ])

      const pasteResult = buildDictionaryImportPreview({
        importFormat: "json",
        importMode: "paste",
        importSourceContent: "   ",
        importMarkdownName: "",
      })
      expect(pasteResult.preview).toBeNull()
      expect(pasteResult.errors).toEqual([
        "Paste dictionary content before generating an import preview.",
      ])
    })

    it("builds JSON preview summary and detects advanced fields", () => {
      const result = buildDictionaryImportPreview({
        importFormat: "json",
        importMode: "paste",
        importSourceContent: JSON.stringify({
          name: "Medical Terms",
          entries: [
            {
              pattern: "BP",
              replacement: "blood pressure",
              group: "Clinical",
              probability: 0.5,
            },
          ],
        }),
        importMarkdownName: "",
      })

      expect(result.errors).toEqual([])
      expect(result.preview).toEqual(
        expect.objectContaining({
          format: "json",
          summary: expect.objectContaining({
            name: "Medical Terms",
            entryCount: 1,
            groups: ["Clinical"],
            hasAdvancedFields: true,
          }),
        })
      )
    })

    it("returns JSON syntax guidance when parsing fails", () => {
      const result = buildDictionaryImportPreview({
        importFormat: "json",
        importMode: "paste",
        importSourceContent: '{"name":"Broken", "entries": [}',
        importMarkdownName: "",
      })

      expect(result.preview).toBeNull()
      expect(result.errors[0]).toContain("Invalid JSON syntax:")
      expect(result.errors[1]).toBe("Expected top-level fields: `name` and `entries`.")
    })

    it("builds Markdown preview summary with heading fallback and groups", () => {
      const result = buildDictionaryImportPreview({
        importFormat: "markdown",
        importMode: "paste",
        importSourceContent:
          "# Markdown Import Dict\n\n## Clinical\n\n## Entry: BP\n- **Replacement**: blood pressure\n",
        importMarkdownName: "Fallback Name",
      })

      expect(result.errors).toEqual([])
      expect(result.preview).toEqual(
        expect.objectContaining({
          format: "markdown",
          summary: expect.objectContaining({
            name: "Markdown Import Dict",
            entryCount: 1,
            groups: ["Clinical"],
          }),
        })
      )
    })
  })

  describe("buildRenamedImportPreview", () => {
    it("renames JSON payload previews", () => {
      const renamed = buildRenamedImportPreview(
        {
          format: "json",
          payload: {
            kind: "json",
            data: {
              name: "Original",
              entries: [],
            },
          },
          summary: {
            name: "Original",
            entryCount: 0,
            groups: [],
            hasAdvancedFields: false,
          },
        },
        "Original (2)"
      )
      expect(renamed.summary.name).toBe("Original (2)")
      expect((renamed.payload.kind === "json" && renamed.payload.data.name) || "").toBe(
        "Original (2)"
      )
    })

    it("renames Markdown payload previews", () => {
      const renamed = buildRenamedImportPreview(
        {
          format: "markdown",
          payload: {
            kind: "markdown",
            name: "Original",
            content: "# Original",
          },
          summary: {
            name: "Original",
            entryCount: 0,
            groups: [],
            hasAdvancedFields: false,
          },
        },
        "Original (2)"
      )
      expect(renamed.summary.name).toBe("Original (2)")
      expect(renamed.payload.kind).toBe("markdown")
      if (renamed.payload.kind === "markdown") {
        expect(renamed.payload.name).toBe("Original (2)")
      }
    })
  })
})
