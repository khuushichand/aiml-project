// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, within, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  listGovernanceAuditFindings: vi.fn(),
  copyToClipboard: vi.fn(),
  downloadBlob: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  listGovernanceAuditFindings: (...args: unknown[]) => mocks.listGovernanceAuditFindings(...args)
}))

vi.mock("@/utils/clipboard", () => ({
  copyToClipboard: (...args: unknown[]) => mocks.copyToClipboard(...args)
}))

vi.mock("@/utils/download-blob", () => ({
  downloadBlob: (...args: unknown[]) => mocks.downloadBlob(...args)
}))

import { GovernanceAuditTab } from "../GovernanceAuditTab"

describe("GovernanceAuditTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.copyToClipboard.mockResolvedValue(undefined)
    mocks.downloadBlob.mockImplementation(() => undefined)
    mocks.listGovernanceAuditFindings.mockResolvedValue({
      items: [
        {
          finding_type: "assignment_validation_blocker",
          severity: "error",
          scope_type: "user",
          scope_id: 7,
          object_kind: "policy_assignment",
          object_id: "11",
          object_label: "researcher",
          message: "Named workspace source contains overlapping roots for multi-root execution.",
          details: {
            conflicting_workspace_ids: ["workspace-alpha", "workspace-beta"]
          },
          navigate_to: {
            tab: "assignments",
            object_kind: "policy_assignment",
            object_id: "11"
          },
          related_object_kind: "workspace_set_object",
          related_object_id: "51",
          related_object_label: "Primary Workspace Set"
        },
        {
          finding_type: "external_binding_issue",
          severity: "warning",
          scope_type: "user",
          scope_id: 7,
          object_kind: "policy_assignment",
          object_id: "12",
          object_label: "writer",
          message: "Assignment binding points at a missing required slot.",
          details: {},
          navigate_to: {
            tab: "assignments",
            object_kind: "policy_assignment",
            object_id: "12"
          },
          related_object_kind: "workspace_set_object",
          related_object_id: "51",
          related_object_label: "Primary Workspace Set"
        },
        {
          finding_type: "workspace_source_readiness_warning",
          severity: "warning",
          scope_type: "user",
          scope_id: 7,
          object_kind: "workspace_set_object",
          object_id: "51",
          object_label: "Primary Workspace Set",
          message: "May overlap with another trusted root in multi-root assignments.",
          details: {},
          navigate_to: {
            tab: "workspace-sets",
            object_kind: "workspace_set_object",
            object_id: "51"
          }
        },
        {
          finding_type: "external_server_configuration_issue",
          severity: "error",
          scope_type: "global",
          scope_id: null,
          object_kind: "external_server",
          object_id: "docs-managed",
          object_label: "Docs Managed",
          message: "required_slot_secret_missing",
          details: {},
          navigate_to: {
            tab: "credentials",
            object_kind: "external_server",
            object_id: "docs-managed"
          },
          related_object_kind: "external_server",
          related_object_id: "docs-managed",
          related_object_label: "Docs Managed"
        }
      ],
      total: 4,
      counts: {
        error: 2,
        warning: 2
      }
    })
  })

  it("groups findings, shows related-object summaries, and filters by related object focus", async () => {
    const user = userEvent.setup()
    const onOpen = vi.fn()
    render(<GovernanceAuditTab onOpen={onOpen} />)

    expect(await screen.findByText("Assignment blockers")).toBeTruthy()
    expect(screen.getByText("4 findings")).toBeTruthy()
    expect(screen.getByText("2 errors")).toBeTruthy()
    expect(screen.getByText("2 warnings")).toBeTruthy()
    expect(screen.getByText("Top related objects in current filtered findings")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Primary Workspace Set · workspace_set_object · 2 findings" })).toBeTruthy()
    expect(screen.getByRole("button", { name: "Docs Managed · external_server · 1 finding" })).toBeTruthy()

    await user.click(
      screen.getByRole("button", {
        name: "Primary Workspace Set · workspace_set_object · 2 findings"
      })
    )

    expect(screen.getByText("2 findings")).toBeTruthy()
    expect(screen.getByText("Related object: Primary Workspace Set")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Clear related object focus" })).toBeTruthy()
    expect(screen.getByText("researcher")).toBeTruthy()
    expect(screen.getByText("writer")).toBeTruthy()
    const focusedBlockerSection = screen.getByTestId("audit-group-assignment_validation_blocker")
    expect(within(focusedBlockerSection).getByText("Suggested next steps")).toBeTruthy()
    expect(
      within(focusedBlockerSection).getByText("Open the assignment configuration.")
    ).toBeTruthy()
    expect(
      within(focusedBlockerSection).getByText(
        "Remove one conflicting workspace or change the path scope to a non-multi-root mode."
      )
    ).toBeTruthy()
    expect(screen.queryByText("Docs Managed")).toBeNull()
    expect(
      screen.getByRole("button", { name: "Docs Managed · external_server · 1 finding" })
    ).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "Clear related object focus" }))
    expect(screen.getByText("4 findings")).toBeTruthy()
    expect(screen.getByText("Docs Managed")).toBeTruthy()

    const blockerSection = screen.getByTestId("audit-group-assignment_validation_blocker")
    await user.click(within(blockerSection).getAllByRole("button", { name: /open/i })[0])
    expect(onOpen).toHaveBeenCalledWith({
      tab: "assignments",
      object_kind: "policy_assignment",
      object_id: "11"
    })
  })

  it("copies and exports the currently filtered audit view", async () => {
    const user = userEvent.setup()
    render(<GovernanceAuditTab />)

    expect(await screen.findByText("Primary Workspace Set")).toBeTruthy()

    await user.click(
      screen.getByRole("button", {
        name: "Primary Workspace Set · workspace_set_object · 2 findings"
      })
    )
    await user.click(screen.getByRole("button", { name: "Copy report" }))

    await waitFor(() => {
      expect(mocks.copyToClipboard).toHaveBeenCalledTimes(1)
    })
    expect(mocks.copyToClipboard).toHaveBeenCalledWith({
      text: expect.stringContaining("Related object focus: Primary Workspace Set (workspace_set_object)"),
      formatted: false
    })
    expect(screen.getByText("Audit report copied.")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "Download JSON" }))

    await waitFor(() => {
      expect(mocks.downloadBlob).toHaveBeenCalledTimes(1)
    })
    const [jsonBlob, jsonFilename] = mocks.downloadBlob.mock.calls[0]
    expect(jsonFilename).toBe("mcp-hub-audit.json")
    const jsonPayload = JSON.parse(await jsonBlob.text())
    expect(jsonPayload.filters).toEqual({
      severity: "all",
      finding_type: "all",
      object_kind: "all",
      scope_type: "all",
      has_related_object_only: false
    })
    expect(jsonPayload.related_object_focus).toEqual({
      kind: "workspace_set_object",
      id: "51",
      label: "Primary Workspace Set"
    })
    expect(jsonPayload.counts).toEqual({
      total: 2,
      error: 1,
      warning: 1
    })
    expect(jsonPayload.items).toHaveLength(2)
    expect(jsonPayload.items[0].suggested_steps).toEqual([
      "Open the assignment configuration.",
      "Remove one conflicting workspace or change the path scope to a non-multi-root mode.",
      "Save again to re-run readiness validation."
    ])
    expect(jsonPayload.items[0].suggestion_note).toBeNull()
    expect(screen.getByText("JSON export downloaded.")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "Download Markdown" }))

    await waitFor(() => {
      expect(mocks.downloadBlob).toHaveBeenCalledTimes(2)
    })
    const [markdownBlob, markdownFilename] = mocks.downloadBlob.mock.calls[1]
    expect(markdownFilename).toBe("mcp-hub-audit.md")
    await expect(markdownBlob.text()).resolves.toContain("# MCP Hub Governance Audit")
    await expect(markdownBlob.text()).resolves.toContain(
      "Top related objects in current filtered findings"
    )
    await expect(markdownBlob.text()).resolves.toContain("Primary Workspace Set")
    await expect(markdownBlob.text()).resolves.toContain("Suggested next steps")
    await expect(markdownBlob.text()).resolves.toContain("Open the assignment configuration.")
    expect(screen.getByText("Markdown export downloaded.")).toBeTruthy()
  })

  it("surfaces clipboard and download failures", async () => {
    const user = userEvent.setup()
    mocks.copyToClipboard.mockRejectedValueOnce(new Error("copy failed"))
    mocks.downloadBlob.mockImplementationOnce(() => {
      throw new Error("download failed")
    })

    render(<GovernanceAuditTab />)
    expect(await screen.findByText("Assignment blockers")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "Copy report" }))
    expect(await screen.findByText("Failed to copy audit report.")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "Download JSON" }))
    expect(await screen.findByText("Failed to download JSON export.")).toBeTruthy()
  })
})
