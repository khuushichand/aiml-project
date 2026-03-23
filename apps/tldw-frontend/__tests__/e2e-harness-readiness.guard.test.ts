import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const readSource = (relativePath: string) =>
  readFileSync(path.join(process.cwd(), relativePath), "utf8")

describe("e2e harness readiness contracts", () => {
  it("keeps smoke and review harnesses off direct networkidle waits", () => {
    const smokeSource = readSource("e2e/smoke/all-pages.spec.ts")
    const reviewSource = readSource("e2e/review/parallel-review.spec.ts")

    expect(smokeSource).toContain("waitForAppShell")
    expect(reviewSource).toContain("waitForAppShell")
    expect(smokeSource).not.toContain("waitForLoadState('networkidle'")
    expect(reviewSource).not.toContain('waitForLoadState("networkidle"')
  })

  it("keeps BasePage state change checks on polling instead of fixed sleeps", () => {
    const basePageSource = readSource("e2e/utils/page-objects/BasePage.ts")

    expect(basePageSource).toContain("expect\n                .poll")
    expect(basePageSource).not.toContain("waitForTimeout(500)")
  })
})
