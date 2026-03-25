import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("sidepanel persona imports", () => {
  it("sources TestLabDryRunCompletedResult from TestLabPanel", () => {
    const routeSourcePath = path.resolve(__dirname, "../sidepanel-persona.tsx")
    const routeSource = fs.readFileSync(routeSourcePath, "utf8")

    expect(routeSource).toContain('type TestLabDryRunCompletedResult')
    expect(routeSource).toContain(
      'from "@/components/PersonaGarden/TestLabPanel"'
    )
    expect(routeSource).not.toContain(
      'type TestLabDryRunCompletedResult,\n} from "@/components/PersonaGarden/SetupTestAndFinishStep"'
    )
  })

  it("defers inactive persona garden tab panels behind lazy route boundaries", () => {
    const routeSourcePath = path.resolve(__dirname, "../sidepanel-persona.tsx")
    const routeSource = fs.readFileSync(routeSourcePath, "utf8")

    expect(routeSource).not.toContain(
      'import { CommandsPanel',
    )
    expect(routeSource).not.toContain(
      'import { LiveSessionPanel } from "@/components/PersonaGarden/LiveSessionPanel"',
    )
    expect(routeSource).not.toContain(
      'import { ProfilePanel } from "@/components/PersonaGarden/ProfilePanel"',
    )
    expect(routeSource).not.toContain(
      'import { VoiceExamplesPanel } from "@/components/PersonaGarden/VoiceExamplesPanel"',
    )
    expect(routeSource).not.toContain(
      'import { ConnectionsPanel } from "@/components/PersonaGarden/ConnectionsPanel"',
    )
    expect(routeSource).not.toContain(
      'import { StateDocsPanel } from "@/components/PersonaGarden/StateDocsPanel"',
    )
    expect(routeSource).not.toContain(
      'import { ScopesPanel } from "@/components/PersonaGarden/ScopesPanel"',
    )
    expect(routeSource).not.toContain(
      'import { PoliciesPanel } from "@/components/PersonaGarden/PoliciesPanel"',
    )
    expect(routeSource).toContain('import("@/components/PersonaGarden/CommandsPanel")')
    expect(routeSource).toContain('import("@/components/PersonaGarden/TestLabPanel")')
    expect(routeSource).toContain('import("@/components/PersonaGarden/LiveSessionPanel")')
    expect(routeSource).toContain('import("@/components/PersonaGarden/ProfilePanel")')
    expect(routeSource).toContain('import("@/components/PersonaGarden/VoiceExamplesPanel")')
    expect(routeSource).toContain('import("@/components/PersonaGarden/ConnectionsPanel")')
    expect(routeSource).toContain('import("@/components/PersonaGarden/StateDocsPanel")')
    expect(routeSource).toContain('import("@/components/PersonaGarden/ScopesPanel")')
    expect(routeSource).toContain('import("@/components/PersonaGarden/PoliciesPanel")')
  })
})
