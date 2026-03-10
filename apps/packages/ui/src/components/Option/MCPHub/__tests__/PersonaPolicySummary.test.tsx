// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

const mocks = vi.hoisted(() => ({
  getEffectivePolicy: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  getEffectivePolicy: (...args: unknown[]) => mocks.getEffectivePolicy(...args)
}))

import { PersonaPolicySummary } from "../PersonaPolicySummary"

describe("PersonaPolicySummary", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getEffectivePolicy.mockResolvedValue({
      enabled: true,
      allowed_tools: ["Bash(git *)"],
      denied_tools: ["Bash(rm *)"],
      capabilities: ["process.execute"],
      approval_policy_id: 17,
      approval_mode: "ask_outside_profile",
      policy_document: {},
      sources: []
    })
  })

  it("renders the effective tool policy for a selected persona", async () => {
    render(<PersonaPolicySummary personaId="researcher" />)

    expect(await screen.findByText("process.execute")).toBeTruthy()
    expect(screen.getByText("Bash(git *)")).toBeTruthy()
    expect(screen.getByText("Bash(rm *)")).toBeTruthy()
    expect(screen.getByRole("link", { name: /open mcp hub/i })).toBeTruthy()
  })
})
