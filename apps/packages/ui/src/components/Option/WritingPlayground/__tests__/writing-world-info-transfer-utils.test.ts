import { describe, expect, it } from "vitest"
import {
  applyWorldInfoImport,
  buildWorldInfoExportPayload,
  parseWorldInfoImportPayload
} from "../writing-world-info-transfer-utils"

describe("writing world info transfer utils", () => {
  it("builds a stable export payload", () => {
    const payload = buildWorldInfoExportPayload({
      enabled: true,
      prefix: "WI:\\n",
      suffix: "\\n<END>",
      search_range: 2000,
      entries: [
        {
          id: "1",
          enabled: true,
          keys: ["hero"],
          content: "Hero notes",
          use_regex: false,
          case_sensitive: false,
          search_range: 150
        }
      ]
    })

    expect(payload.version).toBe(1)
    expect(payload.world_info.prefix).toBe("WI:\\n")
    expect(payload.world_info.entries).toHaveLength(1)
  })

  it("parses native world info payloads", () => {
    const parsed = parseWorldInfoImportPayload({
      world_info: {
        prefix: "P",
        suffix: "S",
        search_range: 500,
        entries: [
          {
            keys: "hero, city",
            content: "Use bright tone",
            search_range: 100
          }
        ]
      }
    })

    expect(parsed.error).toBeNull()
    expect(parsed.value?.prefix).toBe("P")
    expect(parsed.value?.entries).toHaveLength(1)
    expect(parsed.value?.entries?.[0]?.keys).toEqual(["hero", "city"])
    expect(parsed.value?.entries?.[0]?.search_range).toBe(100)
  })

  it("parses SillyTavern-style entries payload", () => {
    const parsed = parseWorldInfoImportPayload({
      entries: {
        a: {
          comment: "Entry A",
          content: "Lore A",
          key: ["alpha", "beta"],
          scanDepth: 250
        }
      }
    })

    expect(parsed.error).toBeNull()
    expect(parsed.value?.entries).toHaveLength(1)
    expect(parsed.value?.entries?.[0]?.content).toBe("Lore A")
    expect(parsed.value?.entries?.[0]?.keys).toEqual(["alpha", "beta"])
    expect(parsed.value?.entries?.[0]?.search_range).toBe(250)
  })

  it("rejects payloads with no usable entries", () => {
    const parsed = parseWorldInfoImportPayload({
      world_info: {
        entries: [
          {
            keys: [],
            content: ""
          }
        ]
      }
    })

    expect(parsed.value).toBeNull()
    expect(parsed.error).toContain("No valid world info")
  })

  it("applies imported world info in replace mode", () => {
    const next = applyWorldInfoImport(
      {
        enabled: true,
        prefix: "old-prefix",
        suffix: "old-suffix",
        search_range: 1000,
        entries: [
          {
            id: "old-1",
            enabled: true,
            keys: ["old"],
            content: "Old entry",
            use_regex: false,
            case_sensitive: false
          }
        ]
      },
      {
        prefix: "new-prefix",
        entries: [
          {
            id: "new-1",
            enabled: true,
            keys: ["new"],
            content: "New entry",
            use_regex: false,
            case_sensitive: false
          }
        ]
      },
      "replace"
    )

    expect(next.prefix).toBe("new-prefix")
    expect(next.suffix).toBe("old-suffix")
    expect(next.entries.map((entry) => entry.id)).toEqual(["new-1"])
  })

  it("applies imported world info in append mode and resolves id collisions", () => {
    const next = applyWorldInfoImport(
      {
        enabled: true,
        prefix: "prefix",
        suffix: "suffix",
        search_range: 1000,
        entries: [
          {
            id: "entry-1",
            enabled: true,
            keys: ["old"],
            content: "Old entry",
            use_regex: false,
            case_sensitive: false
          }
        ]
      },
      {
        entries: [
          {
            id: "entry-1",
            enabled: true,
            keys: ["new"],
            content: "New entry",
            use_regex: false,
            case_sensitive: false
          }
        ]
      },
      "append"
    )

    expect(next.entries).toHaveLength(2)
    expect(next.entries[0].id).toBe("entry-1")
    expect(next.entries[1].id).toBe("entry-1-2")
  })
})
