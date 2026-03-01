import { readFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

type NestedTutorialJson = Record<string, unknown>
type ExtensionLocaleJson = Record<string, { message?: unknown }>

const testDir = path.dirname(fileURLToPath(import.meta.url))
const srcRoot = path.resolve(testDir, "../../")

const nestedTutorials = JSON.parse(
  readFileSync(
    path.resolve(srcRoot, "assets/locale/en/tutorials.json"),
    "utf8"
  )
) as NestedTutorialJson

const extensionTutorials = JSON.parse(
  readFileSync(
    path.resolve(srcRoot, "public/_locales/en/tutorials.json"),
    "utf8"
  )
) as ExtensionLocaleJson

const flattenNested = (
  value: unknown,
  prefix: string[] = []
): Record<string, string> => {
  if (typeof value === "string") {
    return { [prefix.join("_")]: value }
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {}
  }

  return Object.entries(value as Record<string, unknown>).reduce(
    (acc, [key, nested]) => {
      const nextPrefix = [...prefix, key]
      return { ...acc, ...flattenNested(nested, nextPrefix) }
    },
    {} as Record<string, string>
  )
}

describe("tutorial locale mirror parity", () => {
  it("keeps extension _locales tutorial strings in sync with nested tutorial strings", () => {
    const flattenedNested = flattenNested(nestedTutorials)
    const extensionMessages = Object.fromEntries(
      Object.entries(extensionTutorials).map(([key, value]) => [
        key,
        String(value?.message ?? "")
      ])
    )

    const nestedKeys = Object.keys(flattenedNested).sort()
    const extensionKeys = Object.keys(extensionMessages).sort()
    expect(extensionKeys).toEqual(nestedKeys)

    for (const key of nestedKeys) {
      expect(extensionMessages[key]).toBe(flattenedNested[key])
    }
  })
})
