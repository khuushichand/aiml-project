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
})
