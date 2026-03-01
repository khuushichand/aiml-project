import path from "node:path"
import { fileURLToPath } from "node:url"

import { describe, expect, test } from "bun:test"

import config from "../../wxt.config.ts"

const testDir = path.dirname(fileURLToPath(import.meta.url))
const extensionRoot = path.resolve(testDir, "../..")

describe("wxt config publicDir", () => {
  test("points directly at shared ui public assets", () => {
    const expectedSharedPublicDir = path.resolve(extensionRoot, "../packages/ui/src/public")
    const legacySymlinkPath = path.join(extensionRoot, "public")

    expect(config.publicDir).toBe(expectedSharedPublicDir)
    expect(config.publicDir).not.toBe(legacySymlinkPath)
  })
})
