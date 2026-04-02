import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const readSource = (relativePath: string) =>
  readFileSync(path.join(process.cwd(), relativePath), "utf8")

describe("stage 5 route alias contract", () => {
  it("allows the claims-review alias route to satisfy the gate via the redirect panel", () => {
    const source = readSource("e2e/smoke/stage5-release-gate.spec.ts")

    expect(source).toContain("allowRedirectPanel?: boolean")
    expect(source).toContain('path: "/claims-review"')
    expect(source).toContain('name: "Claims Review"')
    expect(source).toContain('expectedPath: "/content-review"')
    expect(source).toContain("allowRedirectPanel: true")
    expect(source).toContain('const redirectPanel = page.getByTestId("route-redirect-panel")')
    expect(source).toContain("let resolvedViaRedirectPanel = false")
    expect(source).toContain("resolvedViaRedirectPanel =")
    expect(source).toContain("await redirectPanel.isVisible().catch(() => false)")
  })
})
