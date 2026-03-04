// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  fetchMcpToolCatalogsViaDiscovery: vi.fn(),
  fetchMcpToolCatalogs: vi.fn()
}))

vi.mock("@/services/tldw/mcp", () => ({
  fetchMcpToolCatalogsViaDiscovery: (...args: unknown[]) =>
    mocks.fetchMcpToolCatalogsViaDiscovery(...args),
  fetchMcpToolCatalogs: (...args: unknown[]) => mocks.fetchMcpToolCatalogs(...args)
}))

import { ToolCatalogsTab } from "../ToolCatalogsTab"

describe("ToolCatalogsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.fetchMcpToolCatalogsViaDiscovery.mockImplementation(async (scope: string) => [
      { id: 1, name: `${scope}-catalog`, description: `${scope} catalog` }
    ])
    mocks.fetchMcpToolCatalogs.mockResolvedValue([])
  })

  it("switches scope and calls proper catalog loader", async () => {
    const user = userEvent.setup()
    render(<ToolCatalogsTab />)

    await user.selectOptions(screen.getByLabelText(/scope/i), "org")
    expect(await screen.findByText(/org catalogs/i)).toBeTruthy()
  })
})
