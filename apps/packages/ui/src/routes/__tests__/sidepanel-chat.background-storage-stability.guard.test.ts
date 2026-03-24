import { readFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

const testDir = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(testDir, "../sidepanel-chat.tsx")

describe("sidepanel-chat background storage stability", () => {
  it("reuses a stable storage instance for background image settings", () => {
    const source = readFileSync(sourcePath, "utf8")

    expect(source).toContain(
      "const backgroundImageStorageRef = React.useRef(createSafeStorage())"
    )
    expect(source).toContain("instance: backgroundImageStorageRef.current")
    expect(source).not.toContain("instance: createSafeStorage()")
  })
})
