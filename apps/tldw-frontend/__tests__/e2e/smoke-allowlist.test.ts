import { describe, expect, it } from "vitest"

import { classifySmokeIssues } from "../../e2e/smoke/smoke.setup"

describe("smoke hard-gate allowlist", () => {
  it("allowlists minimal-backend family wizard latest-draft 404 noise", () => {
    const classified = classifySmokeIssues("/settings/family-guardrails", {
      pageErrors: [],
      consoleErrors: [
        {
          type: "error",
          text: "Failed to load resource: the server responded with a status of 404 (Not Found)"
        }
      ],
      requestFailures: []
    })

    expect(classified.allowlistedConsoleErrors).toHaveLength(1)
    expect(classified.unexpectedConsoleErrors).toHaveLength(0)
  })

  it("allowlists minimal-backend prompt studio status 404 noise", () => {
    const classified = classifySmokeIssues("/settings/prompt-studio", {
      pageErrors: [],
      consoleErrors: [
        {
          type: "error",
          text: "Failed to load resource: the server responded with a status of 404 (Not Found)"
        }
      ],
      requestFailures: []
    })

    expect(classified.allowlistedConsoleErrors).toHaveLength(1)
    expect(classified.unexpectedConsoleErrors).toHaveLength(0)
  })

  it("allowlists minimal-backend collections reading probe 404 noise", () => {
    const classified = classifySmokeIssues("/collections", {
      pageErrors: [],
      consoleErrors: [
        {
          type: "error",
          text: "Failed to load resource: the server responded with a status of 404 (Not Found)"
        }
      ],
      requestFailures: []
    })

    expect(classified.allowlistedConsoleErrors).toHaveLength(1)
    expect(classified.unexpectedConsoleErrors).toHaveLength(0)
  })

  it("allowlists minimal-backend moderation playground 404 noise", () => {
    const classified = classifySmokeIssues("/moderation-playground", {
      pageErrors: [],
      consoleErrors: [
        {
          type: "error",
          text: "Failed to load resource: the server responded with a status of 404 (Not Found)"
        }
      ],
      requestFailures: []
    })

    expect(classified.allowlistedConsoleErrors).toHaveLength(1)
    expect(classified.unexpectedConsoleErrors).toHaveLength(0)
  })

  it("allowlists minimal-backend chunking capabilities 404 noise", () => {
    const classified = classifySmokeIssues("/chunking-playground", {
      pageErrors: [],
      consoleErrors: [
        {
          type: "error",
          text: "Failed to load resource: the server responded with a status of 404 (Not Found)"
        }
      ],
      requestFailures: []
    })

    expect(classified.allowlistedConsoleErrors).toHaveLength(1)
    expect(classified.unexpectedConsoleErrors).toHaveLength(0)
  })
})
