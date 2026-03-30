import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("PlaygroundChat model identity guard", () => {
  it("keeps explicit model/provider identity headers in compare cards", () => {
    const sourcePath = path.resolve(__dirname, "../PlaygroundCompareCluster.tsx")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain("compare-model-identity-")
    expect(source).toContain(
      "playground:composer.compareModelIdentityTag"
    )
    expect(source).toContain("playground:composer.compareProviderCustom")
    expect(source).toContain("playground:composer.compareCardAria")
    expect(source).toContain("getModelLabel(modelKey)")
  })
})
