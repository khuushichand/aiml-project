import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("ParameterPresets guard", () => {
  it("keeps explicit preset parameter detail rows in tooltip content", () => {
    const sourcePath = path.resolve(__dirname, "../ParameterPresets.tsx")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain("formatPresetSettingEntries")
    expect(source).toContain("PRESET_SETTING_LABELS")
    expect(source).toContain("Frequency penalty")
    expect(source).toContain("Presence penalty")
  })
})
