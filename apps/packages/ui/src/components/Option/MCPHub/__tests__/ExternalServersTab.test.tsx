// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mocks = vi.hoisted(() => ({
  listExternalServers: vi.fn(),
  setExternalServerSecret: vi.fn(),
  setExternalServerSlotSecret: vi.fn(),
  clearExternalServerSlotSecret: vi.fn(),
  getExternalServerAuthTemplate: vi.fn(),
  updateExternalServerAuthTemplate: vi.fn(),
  importExternalServer: vi.fn(),
  createExternalServer: vi.fn(),
  updateExternalServer: vi.fn(),
  deleteExternalServer: vi.fn(),
  createExternalServerCredentialSlot: vi.fn(),
  updateExternalServerCredentialSlot: vi.fn(),
  deleteExternalServerCredentialSlot: vi.fn()
}))

vi.mock("@/services/tldw/mcp-hub", () => ({
  listExternalServers: (...args: unknown[]) => mocks.listExternalServers(...args),
  setExternalServerSecret: (...args: unknown[]) => mocks.setExternalServerSecret(...args),
  setExternalServerSlotSecret: (...args: unknown[]) => mocks.setExternalServerSlotSecret(...args),
  clearExternalServerSlotSecret: (...args: unknown[]) => mocks.clearExternalServerSlotSecret(...args),
  getExternalServerAuthTemplate: (...args: unknown[]) => mocks.getExternalServerAuthTemplate(...args),
  updateExternalServerAuthTemplate: (...args: unknown[]) => mocks.updateExternalServerAuthTemplate(...args),
  importExternalServer: (...args: unknown[]) => mocks.importExternalServer(...args),
  createExternalServer: (...args: unknown[]) => mocks.createExternalServer(...args),
  updateExternalServer: (...args: unknown[]) => mocks.updateExternalServer(...args),
  deleteExternalServer: (...args: unknown[]) => mocks.deleteExternalServer(...args),
  createExternalServerCredentialSlot: (...args: unknown[]) => mocks.createExternalServerCredentialSlot(...args),
  updateExternalServerCredentialSlot: (...args: unknown[]) => mocks.updateExternalServerCredentialSlot(...args),
  deleteExternalServerCredentialSlot: (...args: unknown[]) => mocks.deleteExternalServerCredentialSlot(...args)
}))

import { ExternalServersTab } from "../ExternalServersTab"

describe("ExternalServersTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listExternalServers.mockResolvedValue([
      {
        id: "docs-managed",
        name: "Docs Managed",
        enabled: true,
        owner_scope_type: "global",
        transport: "stdio",
        config: {},
        secret_configured: false,
        server_source: "managed",
        binding_count: 2,
        runtime_executable: true,
        auth_template_present: false,
        auth_template_valid: false,
        auth_template_blocked_reason: "no_auth_template",
        credential_slots: [
          {
            server_id: "docs-managed",
            slot_name: "token_readonly",
            display_name: "Read-only token",
            secret_kind: "bearer_token",
            privilege_class: "read",
            is_required: true,
            secret_configured: false
          }
        ]
      },
      {
        id: "search-legacy",
        name: "Search Legacy",
        enabled: true,
        owner_scope_type: "global",
        transport: "websocket",
        config: {},
        secret_configured: false,
        server_source: "legacy",
        binding_count: 0,
        runtime_executable: false,
        auth_template_present: false,
        auth_template_valid: false,
        auth_template_blocked_reason: "no_auth_template"
      },
      {
        id: "docs-legacy",
        name: "Docs Legacy",
        enabled: true,
        owner_scope_type: "global",
        transport: "stdio",
        config: {},
        secret_configured: false,
        server_source: "legacy",
        superseded_by_server_id: "docs-managed",
        binding_count: 0,
        runtime_executable: false,
        auth_template_present: false,
        auth_template_valid: false,
        auth_template_blocked_reason: "no_auth_template"
      }
    ])
    mocks.getExternalServerAuthTemplate.mockImplementation(async (serverId: string) => {
      if (serverId === "docs-managed") {
        return {
          mode: "template",
          mappings: []
        }
      }
      return {
        mode: "template",
        mappings: []
      }
    })
    mocks.updateExternalServerAuthTemplate.mockImplementation(async (_serverId: string, payload: unknown) => payload)
    mocks.setExternalServerSecret.mockResolvedValue({
      server_id: "docs-managed",
      secret_configured: true
    })
    mocks.setExternalServerSlotSecret.mockResolvedValue({
      server_id: "docs-managed",
      slot_name: "token_readonly",
      secret_configured: true
    })
    mocks.clearExternalServerSlotSecret.mockResolvedValue({ ok: true })
    mocks.importExternalServer.mockResolvedValue({
      id: "search-legacy",
      name: "Search Legacy",
      enabled: true,
      owner_scope_type: "global",
      transport: "websocket",
      config: {},
      secret_configured: false,
      server_source: "managed",
      binding_count: 0,
      runtime_executable: true,
      auth_template_present: false,
      auth_template_valid: false,
      auth_template_blocked_reason: "no_auth_template",
      credential_slots: []
    })
    mocks.createExternalServer.mockResolvedValue({
      id: "new-managed",
      name: "New Managed",
      enabled: true,
      owner_scope_type: "global",
      transport: "websocket",
      config: {},
      secret_configured: false,
      server_source: "managed",
      binding_count: 0,
      runtime_executable: true,
      auth_template_present: false,
      auth_template_valid: false,
      auth_template_blocked_reason: "no_auth_template",
      credential_slots: []
    })
    mocks.updateExternalServer.mockResolvedValue({
      id: "docs-managed",
      name: "Docs Managed Updated",
      enabled: true,
      owner_scope_type: "global",
      transport: "stdio",
      config: {},
      secret_configured: false,
      server_source: "managed",
      binding_count: 2,
      runtime_executable: true,
      auth_template_present: true,
      auth_template_valid: true,
      auth_template_blocked_reason: null,
      credential_slots: [
        {
          server_id: "docs-managed",
          slot_name: "token_readonly",
          display_name: "Read-only token",
          secret_kind: "bearer_token",
          privilege_class: "read",
          is_required: true,
          secret_configured: true
        }
      ]
    })
    mocks.createExternalServerCredentialSlot.mockResolvedValue({
      server_id: "docs-managed",
      slot_name: "token_write",
      display_name: "Write token",
      secret_kind: "bearer_token",
      privilege_class: "write",
      is_required: false,
      secret_configured: false
    })
    mocks.updateExternalServerCredentialSlot.mockResolvedValue({
      server_id: "docs-managed",
      slot_name: "token_readonly",
      display_name: "Read-only token updated",
      secret_kind: "bearer_token",
      privilege_class: "read",
      is_required: true,
      secret_configured: true
    })
    mocks.deleteExternalServerCredentialSlot.mockResolvedValue({ ok: true })
    mocks.deleteExternalServer.mockResolvedValue({ ok: true })
    vi.stubGlobal("confirm", vi.fn(() => true))
  })

  it("renders managed and legacy servers, supports import, and still saves managed secrets", async () => {
    const user = userEvent.setup()
    render(<ExternalServersTab />)

    expect((await screen.findAllByText(/legacy read only/i)).length).toBe(2)
    expect(screen.getByText("Search Legacy")).toBeTruthy()
    expect(screen.getByText("Docs Legacy")).toBeTruthy()
    expect(screen.getByText(/superseded by docs-managed/i)).toBeTruthy()
    expect(screen.getByText(/2 bindings/i)).toBeTruthy()
    expect(screen.getByText(/1 slot/i)).toBeTruthy()
    expect(screen.getAllByText("Read-only token").length).toBeGreaterThan(0)

    const secretInput = (await screen.findByLabelText(/slot secret/i)) as HTMLInputElement
    await user.type(secretInput, "super-secret")
    await user.click(screen.getByRole("button", { name: /save slot secret/i }))

    expect(mocks.setExternalServerSlotSecret).toHaveBeenCalledWith(
      "docs-managed",
      "token_readonly",
      "super-secret"
    )
    expect(await screen.findByText(/slot secret configured/i)).toBeTruthy()
    expect(secretInput.value).toBe("")
    expect(screen.queryByDisplayValue("super-secret")).toBeNull()

    await user.click(screen.getByRole("button", { name: /import to mcp hub/i }))
    expect(mocks.importExternalServer).toHaveBeenCalledWith("search-legacy")
  })

  it("renders auth template readiness and saves transport-aware mappings", async () => {
    const user = userEvent.setup()
    render(<ExternalServersTab />)

    expect((await screen.findAllByText(/no auth template/i)).length).toBeGreaterThan(0)

    await user.click(screen.getByRole("button", { name: /add mapping/i }))
    await user.type(screen.getByLabelText(/target name 1/i), "DOCS_TOKEN")
    await user.type(screen.getByLabelText(/prefix 1/i), "Bearer ")
    await user.click(screen.getByRole("button", { name: /save auth template/i }))

    expect(mocks.updateExternalServerAuthTemplate).toHaveBeenCalledWith("docs-managed", {
      mode: "template",
      mappings: [
        {
          slot_name: "token_readonly",
          target_type: "env",
          target_name: "DOCS_TOKEN",
          prefix: "Bearer ",
          suffix: "",
          required: true
        }
      ]
    })
    expect(await screen.findByText(/auth template updated/i)).toBeTruthy()
  })

  it("creates, edits, and deletes managed servers and credential slots", async () => {
    const user = userEvent.setup()
    render(<ExternalServersTab />)

    await screen.findByText("Docs Legacy")

    await user.click(screen.getByRole("button", { name: /add slot/i }))
    await user.type(screen.getByLabelText(/slot name/i), "token_write")
    await user.type(screen.getByLabelText(/slot display name/i), "Write token")
    await user.selectOptions(screen.getByLabelText(/privilege class/i), "write")
    await user.click(screen.getByRole("button", { name: /^save slot$/i }))

    expect(mocks.createExternalServerCredentialSlot).toHaveBeenCalledWith("docs-managed", {
      slot_name: "token_write",
      display_name: "Write token",
      secret_kind: "bearer_token",
      privilege_class: "write",
      is_required: true
    })

    await user.click(screen.getByRole("button", { name: /edit read-only token/i }))
    const slotNameInput = screen.queryByLabelText(/slot name/i)
    expect(slotNameInput).toBeNull()
    const displayNameInput = screen.getByLabelText(/slot display name/i)
    await user.clear(displayNameInput)
    await user.type(displayNameInput, "Read-only token updated")
    await user.click(screen.getByRole("button", { name: /update slot/i }))

    expect(mocks.updateExternalServerCredentialSlot).toHaveBeenCalledWith("docs-managed", "token_readonly", {
      display_name: "Read-only token updated",
      secret_kind: "bearer_token",
      privilege_class: "read",
      is_required: true
    })

    await user.click(screen.getByRole("button", { name: /delete read-only token/i }))
    expect(mocks.deleteExternalServerCredentialSlot).toHaveBeenCalledWith("docs-managed", "token_readonly")

    await user.click(screen.getByRole("button", { name: /new managed server/i }))
    await user.type(screen.getByLabelText(/server id/i), "new-managed")
    await user.type(screen.getByLabelText(/^name$/i), "New Managed")
    await user.selectOptions(screen.getByLabelText(/transport/i), "websocket")
    await user.click(screen.getByRole("button", { name: /save server/i }))

    expect(mocks.createExternalServer).toHaveBeenCalledWith({
      server_id: "new-managed",
      name: "New Managed",
      transport: "websocket",
      config: {},
      owner_scope_type: "global",
      enabled: true
    })

    await user.click(screen.getByRole("button", { name: /edit docs managed/i }))
    const nameInput = screen.getByLabelText(/^name$/i)
    await user.clear(nameInput)
    await user.type(nameInput, "Docs Managed Updated")
    await user.click(screen.getByRole("button", { name: /update server/i }))

    expect(mocks.updateExternalServer).toHaveBeenCalledWith("docs-managed", {
      name: "Docs Managed Updated",
      transport: "stdio",
      config: {},
      owner_scope_type: "global",
      enabled: true
    })

    await user.click(screen.getByRole("button", { name: /delete docs managed/i }))
    expect(mocks.deleteExternalServer).toHaveBeenCalledWith("docs-managed")
  }, 15000)

  it("opens the managed server editor from a drill target", async () => {
    const onDrillHandled = vi.fn()
    render(
      <ExternalServersTab
        drillTarget={{
          tab: "credentials",
          object_kind: "external_server",
          object_id: "docs-managed",
          action: "edit",
          request_id: 12
        }}
        onDrillHandled={onDrillHandled}
      />
    )

    expect(await screen.findByDisplayValue("Docs Managed")).toBeTruthy()
    expect(screen.getByDisplayValue("stdio")).toBeTruthy()
    expect(onDrillHandled).toHaveBeenCalledWith(12)
  })

  it("falls back to visible focus for legacy servers from a drill target", async () => {
    const onDrillHandled = vi.fn()
    render(
      <ExternalServersTab
        drillTarget={{
          tab: "credentials",
          object_kind: "external_server",
          object_id: "search-legacy",
          action: "focus",
          request_id: 13
        }}
        onDrillHandled={onDrillHandled}
      />
    )

    expect(await screen.findByText("Search Legacy")).toBeTruthy()
    expect(await screen.findByText(/focused from audit/i)).toBeTruthy()
    expect(onDrillHandled).toHaveBeenCalledWith(13)
  })
})
