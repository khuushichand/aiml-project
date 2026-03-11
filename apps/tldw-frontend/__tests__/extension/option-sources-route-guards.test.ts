import { existsSync, readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

const loadSource = (...candidates: string[]) => {
  const path = candidates.find((candidate) => existsSync(candidate))
  if (!path) {
    throw new Error(`Missing extension route source: ${candidates.join(" | ")}`)
  }
  return readFileSync(path, "utf8")
}

describe("extension sources route guard parity", () => {
  it("wraps the new and detail routes with the shared availability gate", () => {
    expect(
      loadSource(
        "apps/tldw-frontend/extension/routes/option-sources-new.tsx",
        "tldw-frontend/extension/routes/option-sources-new.tsx",
        "extension/routes/option-sources-new.tsx"
      )
    ).toContain("SourcesAvailabilityGate")

    expect(
      loadSource(
        "apps/tldw-frontend/extension/routes/option-sources-detail.tsx",
        "tldw-frontend/extension/routes/option-sources-detail.tsx",
        "extension/routes/option-sources-detail.tsx"
      )
    ).toContain("SourcesAvailabilityGate")
  })
})
