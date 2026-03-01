import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("writing mode copy guard", () => {
  it("contains draft/manage labels in option locale", () => {
    const locale = fs.readFileSync(
      path.resolve(__dirname, "../../../../public/_locales/en/option.json"),
      "utf8"
    )
    expect(locale).toContain("writingPlayground_modeDraft")
    expect(locale).toContain("writingPlayground_modeManage")
    expect(locale).toContain("writingPlayground_workspaceModeLabel")
    expect(locale).toContain("writingPlayground_draftQuickControls")
  })
})
