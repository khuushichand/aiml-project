// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  listExternalServers: vi.fn(),
  setExternalServerSecret: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  listExternalServers: (...args: unknown[]) => mocks.listExternalServers(...args),
  setExternalServerSecret: (...args: unknown[]) => mocks.setExternalServerSecret(...args)
}))

import { ExternalServersTab } from "../ExternalServersTab"

describe("ExternalServersTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listExternalServers.mockResolvedValue([
      {
        id: "docs",
        name: "Docs",
        enabled: true,
        owner_scope_type: "global",
        transport: "stdio",
        config: {},
        secret_configured: false
      }
    ])
    mocks.setExternalServerSecret.mockResolvedValue({
      server_id: "docs",
      secret_configured: true
    })
  })

  it("submits secret and only displays configured state", async () => {
    const user = userEvent.setup()
    render(<ExternalServersTab />)

    const secretInput = (await screen.findByLabelText(/secret/i)) as HTMLInputElement
    await user.type(secretInput, "super-secret")
    await user.click(screen.getByRole("button", { name: /save secret/i }))

    expect(await screen.findByText(/secret configured/i)).toBeTruthy()
    expect(secretInput.value).toBe("")
    expect(screen.queryByDisplayValue("super-secret")).toBeNull()
  })
})
