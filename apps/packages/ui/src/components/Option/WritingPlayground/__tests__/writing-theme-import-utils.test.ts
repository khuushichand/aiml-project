import { describe, expect, it } from "vitest"
import { extractImportedThemeItems } from "../writing-theme-import-utils"

describe("writing theme import utils", () => {
  it("extracts theme items from arrays", () => {
    const items = extractImportedThemeItems([
      { name: "Midnight", class_name: "midnight", css: ".x{color:white;}" }
    ])

    expect(items).toEqual([
      {
        name: "Midnight",
        className: "midnight",
        css: ".x{color:white;}",
        schemaVersion: 1,
        isDefault: false,
        order: 0
      }
    ])
  })

  it("extracts theme items from themes maps", () => {
    const items = extractImportedThemeItems({
      themes: {
        "Serif Light": {
          className: "serif-light",
          css: ".serif-light{color:#111;}",
          isDefault: true,
          order: 1
        }
      }
    })

    expect(items).toEqual([
      {
        name: "Serif Light",
        className: "serif-light",
        css: ".serif-light{color:#111;}",
        schemaVersion: 1,
        isDefault: true,
        order: 1
      }
    ])
  })

  it("extracts Mikupad-style theme export maps", () => {
    const items = extractImportedThemeItems({
      "Neon Noir": {
        className: "neon-noir",
        css: ".neon-noir{background:#000;}",
        isDefault: "true",
        order: 7
      }
    })

    expect(items).toEqual([
      {
        name: "Neon Noir",
        className: "neon-noir",
        css: ".neon-noir{background:#000;}",
        schemaVersion: 1,
        isDefault: true,
        order: 7
      }
    ])
  })

  it("extracts single theme payload objects", () => {
    const items = extractImportedThemeItems({
      name: "Slate",
      className: "slate",
      css: ".slate{color:#eee;}",
      schema_version: 2,
      is_default: true,
      order: 5
    })

    expect(items).toEqual([
      {
        name: "Slate",
        className: "slate",
        css: ".slate{color:#eee;}",
        schemaVersion: 2,
        isDefault: true,
        order: 5
      }
    ])
  })
})
