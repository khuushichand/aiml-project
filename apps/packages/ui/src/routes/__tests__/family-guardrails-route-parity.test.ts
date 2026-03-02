import { existsSync, readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

const testFileDirectory = dirname(fileURLToPath(import.meta.url))

const webRouteRegistryPath = resolve(testFileDirectory, "../route-registry.tsx")
const extensionRouteRegistryPath = resolve(
  testFileDirectory,
  "../../../../../tldw-frontend/extension/routes/route-registry.tsx"
)

if (!existsSync(webRouteRegistryPath)) {
  throw new Error("Unable to locate web route-registry.tsx for family guardrails parity test")
}
if (!existsSync(extensionRouteRegistryPath)) {
  throw new Error("Unable to locate extension route-registry.tsx for family guardrails parity test")
}

const webRouteRegistrySource = readFileSync(webRouteRegistryPath, "utf8")
const extensionRouteRegistrySource = readFileSync(extensionRouteRegistryPath, "utf8")

describe("family guardrails route parity", () => {
  it("registers the same family wizard settings path in web and extension registries", () => {
    expect(webRouteRegistrySource).toContain('path: "/settings/family-guardrails"')
    expect(extensionRouteRegistrySource).toContain('path: "/settings/family-guardrails"')
  })

  it("uses dedicated family wizard option route modules in both surfaces", () => {
    expect(webRouteRegistrySource).toMatch(
      /const OptionFamilyGuardrailsWizard = lazy\(\s*\(\) => import\("\.\/option-family-guardrails-wizard"\)\s*\)/
    )
    expect(extensionRouteRegistrySource).toMatch(
      /const OptionFamilyGuardrailsWizard = lazy\(\s*\(\) => import\("\.\/option-family-guardrails-wizard"\)\s*\)/
    )
  })

  it("keeps family wizard navigation metadata aligned", () => {
    expect(webRouteRegistrySource).toContain('labelToken: "settings:familyGuardrailsWizardNav"')
    expect(extensionRouteRegistrySource).toContain('labelToken: "settings:familyGuardrailsWizardNav"')
    expect(webRouteRegistrySource).toContain("order: 8")
    expect(extensionRouteRegistrySource).toContain("order: 8")
  })
})
