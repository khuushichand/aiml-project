import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("ComposerToolbar layout guard", () => {
  it("keeps primary/actions grouping and advanced-controls collapse affordance", () => {
    const sourcePath = path.resolve(__dirname, "../ComposerToolbar.tsx")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain('data-playground-toolbar-row="primary"')
    expect(source).toContain('data-playground-toolbar-row="actions"')
    expect(source).toContain('data-testid="composer-advanced-toggle"')
    expect(source).toContain("playgroundComposerAdvancedControlsOpen")
  })
})
