import { describe, expect, it } from "vitest"
import { buildDiagnosticsSummary } from "../writing-diagnostics-utils"

describe("writing diagnostics utils", () => {
  it("marks warning when server is offline", () => {
    const result = buildDiagnosticsSummary({
      showOffline: true,
      showUnsupported: false,
      isGenerating: false
    })
    expect(result.status).toBe("warning")
  })

  it("marks busy while generation is running", () => {
    const result = buildDiagnosticsSummary({
      showOffline: false,
      showUnsupported: false,
      isGenerating: true
    })
    expect(result.status).toBe("busy")
  })

  it("marks ready when there are no warnings and no active generation", () => {
    const result = buildDiagnosticsSummary({
      showOffline: false,
      showUnsupported: false,
      isGenerating: false
    })
    expect(result.status).toBe("ready")
  })
})
