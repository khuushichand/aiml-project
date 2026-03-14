// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  listCapabilityAdapterMappings: vi.fn(),
  previewCapabilityAdapterMapping: vi.fn(),
  createCapabilityAdapterMapping: vi.fn(),
  updateCapabilityAdapterMapping: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  listCapabilityAdapterMappings: (...args: unknown[]) => mocks.listCapabilityAdapterMappings(...args),
  previewCapabilityAdapterMapping: (...args: unknown[]) => mocks.previewCapabilityAdapterMapping(...args),
  createCapabilityAdapterMapping: (...args: unknown[]) => mocks.createCapabilityAdapterMapping(...args),
  updateCapabilityAdapterMapping: (...args: unknown[]) => mocks.updateCapabilityAdapterMapping(...args)
}))

import { CapabilityMappingsTab } from "../CapabilityMappingsTab"

describe("CapabilityMappingsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listCapabilityAdapterMappings
      .mockResolvedValueOnce([
        {
          id: 1,
          mapping_id: "research.global",
          title: "Research Mapping",
          description: "Maps research capability to search tools",
          owner_scope_type: "global",
          owner_scope_id: null,
          capability_name: "tool.invoke.research",
          adapter_contract_version: 1,
          resolved_policy_document: { allowed_tools: ["web.search"] },
          supported_environment_requirements: ["workspace_bounded_read"],
          is_active: true
        }
      ])
      .mockResolvedValueOnce([
        {
          id: 1,
          mapping_id: "research.global",
          title: "Research Mapping",
          description: "Maps research capability to search tools",
          owner_scope_type: "global",
          owner_scope_id: null,
          capability_name: "tool.invoke.research",
          adapter_contract_version: 1,
          resolved_policy_document: { allowed_tools: ["web.search"] },
          supported_environment_requirements: ["workspace_bounded_read"],
          is_active: true
        },
        {
          id: 2,
          mapping_id: "docs.global",
          title: "Docs Mapping",
          description: null,
          owner_scope_type: "global",
          owner_scope_id: null,
          capability_name: "tool.invoke.docs",
          adapter_contract_version: 1,
          resolved_policy_document: { allowed_tools: ["docs.search"] },
          supported_environment_requirements: [],
          is_active: true
        }
      ])
    mocks.previewCapabilityAdapterMapping.mockResolvedValue({
      normalized_mapping: {
        mapping_id: "docs.global",
        title: "Docs Mapping",
        description: null,
        owner_scope_type: "global",
        owner_scope_id: null,
        capability_name: "tool.invoke.docs",
        adapter_contract_version: 1,
        resolved_policy_document: { allowed_tools: ["docs.search"] },
        supported_environment_requirements: [],
        is_active: true
      },
      warnings: ["preview warning"],
      affected_scope_summary: {
        owner_scope_type: "global",
        owner_scope_id: null,
        display_scope: "Global"
      }
    })
    mocks.createCapabilityAdapterMapping.mockResolvedValue({
      id: 2,
      mapping_id: "docs.global",
      title: "Docs Mapping",
      description: null,
      owner_scope_type: "global",
      owner_scope_id: null,
      capability_name: "tool.invoke.docs",
      adapter_contract_version: 1,
      resolved_policy_document: { allowed_tools: ["docs.search"] },
      supported_environment_requirements: [],
      is_active: true
    })
    mocks.updateCapabilityAdapterMapping.mockResolvedValue({
      id: 1,
      mapping_id: "research.global",
      title: "Research Mapping",
      description: "Maps research capability to search tools",
      owner_scope_type: "global",
      owner_scope_id: null,
      capability_name: "tool.invoke.research",
      adapter_contract_version: 1,
      resolved_policy_document: { allowed_tools: ["web.search"] },
      supported_environment_requirements: ["workspace_bounded_read"],
      is_active: true
    })
  })

  it("lists mappings and lets users preview and save a new mapping", async () => {
    const user = userEvent.setup()
    render(<CapabilityMappingsTab />)

    expect(await screen.findByText("Research Mapping")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: /new mapping/i }))
    await user.type(screen.getByLabelText("Mapping ID"), "docs.global")
    await user.type(screen.getByLabelText("Title"), "Docs Mapping")
    await user.type(screen.getByLabelText("Capability Name"), "tool.invoke.docs")
    fireEvent.change(screen.getByLabelText("Resolved Policy JSON"), {
      target: { value: JSON.stringify({ allowed_tools: ["docs.search"] }) }
    })

    await user.click(screen.getByRole("button", { name: /preview mapping/i }))

    await waitFor(() =>
      expect(mocks.previewCapabilityAdapterMapping).toHaveBeenCalledWith(
        expect.objectContaining({
          mapping_id: "docs.global",
          capability_name: "tool.invoke.docs",
          resolved_policy_document: { allowed_tools: ["docs.search"] }
        })
      )
    )
    expect(screen.getByText("preview warning")).toBeTruthy()
    expect(within(screen.getByText("Preview Result").closest(".ant-card")!).getByText("Global")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: /save mapping/i }))

    await waitFor(() =>
      expect(mocks.createCapabilityAdapterMapping).toHaveBeenCalledWith(
        expect.objectContaining({
          mapping_id: "docs.global",
          title: "Docs Mapping",
          capability_name: "tool.invoke.docs"
        })
      )
    )
    expect(await screen.findByText("Docs Mapping")).toBeTruthy()
  })
})
