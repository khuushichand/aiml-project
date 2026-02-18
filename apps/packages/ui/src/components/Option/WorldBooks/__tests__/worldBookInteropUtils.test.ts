import { describe, expect, it } from "vitest"
import {
  convertWorldBookImport,
  detectWorldBookImportFormat,
  getWorldBookImportFormatLabel,
  getWorldBookImportJsonErrorMessage,
  validateWorldBookImportConversion,
  WORLD_BOOK_IMPORT_MERGE_HELP_TEXT
} from "../worldBookInteropUtils"

describe("worldBookInteropUtils", () => {
  it("detects and converts native tldw format", () => {
    const input = {
      world_book: { name: "Arcana", token_budget: 750 },
      entries: [{ keywords: ["wizard"], content: "Lore content" }]
    }

    expect(detectWorldBookImportFormat(input)).toBe("tldw")
    const result = convertWorldBookImport(input)
    expect(result.error).toBeUndefined()
    expect(result.payload?.world_book.name).toBe("Arcana")
    expect(result.payload?.entries).toHaveLength(1)
    expect(result.warnings).toEqual([])
  })

  it("converts SillyTavern character_book entries", () => {
    const input = {
      data: {
        name: "Card Name",
        character_book: {
          name: "ST Lore",
          entries: [
            {
              key: ["alpha", "beta"],
              content: "Silly content",
              order: 88,
              disable: false
            }
          ]
        }
      }
    }

    expect(detectWorldBookImportFormat(input)).toBe("sillytavern")
    const result = convertWorldBookImport(input)
    expect(result.payload?.world_book.name).toBe("ST Lore")
    expect(result.payload?.entries[0]).toEqual(
      expect.objectContaining({
        keywords: ["alpha", "beta"],
        content: "Silly content",
        priority: 88
      })
    )
  })

  it("converts Kobold world info and reports unsupported constant behavior", () => {
    const input = {
      name: "Kobold Book",
      entries: {
        "0": {
          key: ["location"],
          content: "City details",
          constant: true,
          order: 65
        }
      }
    }

    expect(detectWorldBookImportFormat(input)).toBe("kobold")
    const result = convertWorldBookImport(input)
    expect(result.payload?.world_book.name).toBe("Kobold Book")
    expect(result.payload?.entries[0]).toEqual(
      expect.objectContaining({
        keywords: ["location"],
        content: "City details",
        priority: 65
      })
    )
    expect(result.warnings.some((warning) => warning.includes("constant"))).toBe(true)
  })

  it("returns an error for unknown formats", () => {
    const result = convertWorldBookImport({ random: true })
    expect(result.payload).toBeUndefined()
    expect(result.error).toMatch(/Unsupported import format/i)
    expect(getWorldBookImportFormatLabel("unknown")).toBe("Unknown")
  })

  it("maps common JSON parse failures to user-friendly messages", () => {
    expect(
      getWorldBookImportJsonErrorMessage(new Error("Unexpected token } in JSON at position 8"))
    ).toMatch(/trailing commas or invalid characters/i)
    expect(
      getWorldBookImportJsonErrorMessage(new Error("Unexpected end of JSON input"))
    ).toMatch(/appears truncated/i)
    expect(getWorldBookImportJsonErrorMessage(new Error("boom"))).toBe(
      "File is not valid JSON."
    )
  })

  it("reports missing world_book field when format is unsupported", () => {
    const raw = { entries: [{ keywords: ["k"], content: "c" }] }
    const conversion = convertWorldBookImport(raw)
    expect(validateWorldBookImportConversion(raw, conversion)).toBe(
      "File is missing the 'world_book' field."
    )
  })

  it("reports empty entry sets for converted payloads", () => {
    const raw = { world_book: { name: "Arcana" }, entries: [] }
    const conversion = convertWorldBookImport(raw)
    expect(validateWorldBookImportConversion(raw, conversion)).toBe(
      "File is missing entries (found 0 entries)."
    )
  })

  it("returns valid converted payloads for SillyTavern and Kobold contracts", () => {
    const sillyRaw = {
      data: {
        character_book: {
          name: "ST Lore",
          entries: [{ key: ["alpha"], content: "Silly content" }]
        }
      }
    }
    const koboldRaw = {
      name: "Kobold Book",
      entries: {
        "0": { key: ["location"], content: "City details" }
      }
    }

    const sillyConversion = convertWorldBookImport(sillyRaw)
    const koboldConversion = convertWorldBookImport(koboldRaw)

    expect(validateWorldBookImportConversion(sillyRaw, sillyConversion)).toBeNull()
    expect(validateWorldBookImportConversion(koboldRaw, koboldConversion)).toBeNull()
  })

  it("exposes stable merge-help copy for UI tooltips", () => {
    expect(WORLD_BOOK_IMPORT_MERGE_HELP_TEXT).toContain("Existing entries are not removed")
  })
})
