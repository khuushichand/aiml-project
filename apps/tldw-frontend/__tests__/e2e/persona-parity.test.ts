import { describe, expect, it } from "vitest"

import { PAGE_MAPPINGS } from "@web/e2e/page-mapping"
import { PAGES } from "@web/e2e/smoke/page-inventory"

describe("persona webui-extension parity metadata", () => {
  it("maps persona route between WebUI and extension sidepanel", () => {
    const personaMapping = PAGE_MAPPINGS.find(
      (mapping) => mapping.extensionSidepanelPath === "/persona"
    )
    expect(personaMapping).toBeDefined()
    expect(personaMapping?.webuiPath).toBe("/persona")
    expect(personaMapping?.sharedComponent).toBe("SidepanelPersona")
  })

  it("includes persona route in WebUI smoke inventory", () => {
    const personaEntry = PAGES.find((page) => page.path === "/persona")
    expect(personaEntry).toBeDefined()
    expect(personaEntry?.category).toBe("chat")
  })
})
