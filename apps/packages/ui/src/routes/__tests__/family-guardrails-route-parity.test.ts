import { existsSync, readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

const testFileDirectory = dirname(fileURLToPath(import.meta.url))
const webRouteRegistryRelativePath = "apps/packages/ui/src/routes/route-registry.tsx"
const extensionRouteRegistryRelativePath =
  "apps/tldw-frontend/extension/routes/route-registry.tsx"

const resolveWorkspaceRoot = (startDirectory: string): string => {
  let currentDirectory = startDirectory
  while (true) {
    const webPath = resolve(currentDirectory, webRouteRegistryRelativePath)
    const extensionPath = resolve(currentDirectory, extensionRouteRegistryRelativePath)
    if (existsSync(webPath) && existsSync(extensionPath)) {
      return currentDirectory
    }
    const parentDirectory = dirname(currentDirectory)
    if (parentDirectory === currentDirectory) {
      throw new Error("Unable to locate workspace root for family guardrails route parity test")
    }
    currentDirectory = parentDirectory
  }
}

const workspaceRoot = resolveWorkspaceRoot(testFileDirectory)
const webRouteRegistryPath = resolve(workspaceRoot, webRouteRegistryRelativePath)
const extensionRouteRegistryPath = resolve(
  workspaceRoot,
  extensionRouteRegistryRelativePath
)

const webRouteRegistrySource = readFileSync(webRouteRegistryPath, "utf8")
const extensionRouteRegistrySource = readFileSync(extensionRouteRegistryPath, "utf8")
const webRouteModulePath = resolve(
  workspaceRoot,
  "apps/packages/ui/src/routes/option-family-guardrails-wizard.tsx"
)
const extensionRouteModulePath = resolve(
  workspaceRoot,
  "apps/tldw-frontend/extension/routes/option-family-guardrails-wizard.tsx"
)
const webRouteModuleSource = readFileSync(webRouteModulePath, "utf8")
const extensionRouteModuleSource = readFileSync(extensionRouteModulePath, "utf8")

const normalizeSource = (source: string): string =>
  source
    .replace(/\r\n/g, "\n")
    .trim()

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

  it("keeps the dedicated family wizard route modules in sync", () => {
    expect(normalizeSource(extensionRouteModuleSource)).toBe(normalizeSource(webRouteModuleSource))
  })
})
