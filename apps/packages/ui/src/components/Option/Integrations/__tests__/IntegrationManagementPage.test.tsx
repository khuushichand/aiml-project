// @vitest-environment jsdom

import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  listPersonalIntegrations: vi.fn(),
  listWorkspaceIntegrations: vi.fn(),
  connectPersonalIntegration: vi.fn(),
  updatePersonalIntegration: vi.fn(),
  deletePersonalIntegration: vi.fn(),
  getWorkspaceSlackPolicy: vi.fn(),
  getWorkspaceDiscordPolicy: vi.fn(),
  getWorkspaceTelegramBot: vi.fn(),
  listWorkspaceTelegramLinkedActors: vi.fn(),
  updateWorkspaceSlackPolicy: vi.fn(),
  updateWorkspaceDiscordPolicy: vi.fn(),
  updateWorkspaceTelegramBot: vi.fn(),
  createWorkspaceTelegramPairingCode: vi.fn(),
  revokeWorkspaceTelegramLinkedActor: vi.fn()
}))

vi.mock("@/services/integrations-control-plane", () => ({
  listPersonalIntegrations: (...args: unknown[]) => mocks.listPersonalIntegrations(...args),
  listWorkspaceIntegrations: (...args: unknown[]) => mocks.listWorkspaceIntegrations(...args),
  connectPersonalIntegration: (...args: unknown[]) => mocks.connectPersonalIntegration(...args),
  updatePersonalIntegration: (...args: unknown[]) => mocks.updatePersonalIntegration(...args),
  deletePersonalIntegration: (...args: unknown[]) => mocks.deletePersonalIntegration(...args),
  getWorkspaceSlackPolicy: (...args: unknown[]) => mocks.getWorkspaceSlackPolicy(...args),
  getWorkspaceDiscordPolicy: (...args: unknown[]) => mocks.getWorkspaceDiscordPolicy(...args),
  getWorkspaceTelegramBot: (...args: unknown[]) => mocks.getWorkspaceTelegramBot(...args),
  listWorkspaceTelegramLinkedActors: (...args: unknown[]) => mocks.listWorkspaceTelegramLinkedActors(...args),
  updateWorkspaceSlackPolicy: (...args: unknown[]) => mocks.updateWorkspaceSlackPolicy(...args),
  updateWorkspaceDiscordPolicy: (...args: unknown[]) => mocks.updateWorkspaceDiscordPolicy(...args),
  updateWorkspaceTelegramBot: (...args: unknown[]) => mocks.updateWorkspaceTelegramBot(...args),
  createWorkspaceTelegramPairingCode: (...args: unknown[]) => mocks.createWorkspaceTelegramPairingCode(...args),
  revokeWorkspaceTelegramLinkedActor: (...args: unknown[]) => mocks.revokeWorkspaceTelegramLinkedActor(...args)
}))

import { IntegrationManagementPage } from "../IntegrationManagementPage"

const renderWithQueryClient = (ui: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  })

  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  )
}

describe("IntegrationManagementPage", () => {
  beforeEach(() => {
    for (const mock of Object.values(mocks)) {
      mock.mockReset()
    }
  })

  it("renders personal slack and discord cards and hides telegram", async () => {
    mocks.listPersonalIntegrations.mockResolvedValue({
      scope: "personal",
      items: [
        {
          id: "personal:slack",
          provider: "slack",
          scope: "personal",
          display_name: "Slack",
          status: "connected",
          enabled: true,
          metadata: {},
          actions: ["disconnect"]
        },
        {
          id: "personal:discord",
          provider: "discord",
          scope: "personal",
          display_name: "Discord",
          status: "disconnected",
          enabled: false,
          metadata: {},
          actions: ["connect"]
        },
        {
          id: "workspace:telegram",
          provider: "telegram",
          scope: "workspace",
          display_name: "Telegram",
          status: "connected",
          enabled: true,
          metadata: {},
          actions: ["inspect"]
        }
      ]
    })

    renderWithQueryClient(<IntegrationManagementPage scope="personal" />)

    expect(await screen.findByText("Slack")).toBeInTheDocument()
    expect(screen.getByText("Discord")).toBeInTheDocument()
    expect(screen.queryByText("Telegram")).not.toBeInTheDocument()
  })

  it("starts the personal connect flow from the management drawer", async () => {
    const user = userEvent.setup()
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null)

    mocks.listPersonalIntegrations.mockResolvedValue({
      scope: "personal",
      items: [
        {
          id: "personal:slack",
          provider: "slack",
          scope: "personal",
          display_name: "Slack",
          status: "disconnected",
          enabled: false,
          metadata: {},
          actions: ["connect"]
        }
      ]
    })
    mocks.connectPersonalIntegration.mockResolvedValue({
      provider: "slack",
      connection_id: "personal:slack",
      status: "ready",
      auth_url: "https://slack.example.test/oauth",
      auth_session_id: "session-123",
      expires_at: "2026-03-20T22:00:00+00:00"
    })

    renderWithQueryClient(<IntegrationManagementPage scope="personal" />)

    await user.click(await screen.findByRole("button", { name: "Manage" }))
    await user.click(await screen.findByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(mocks.connectPersonalIntegration).toHaveBeenCalledWith("slack")
    })
    expect(openSpy).toHaveBeenCalledWith("https://slack.example.test/oauth", "_blank", "noopener,noreferrer")

    openSpy.mockRestore()
  })

  it("updates and removes a personal integration from the management drawer", async () => {
    const user = userEvent.setup()

    mocks.listPersonalIntegrations.mockResolvedValue({
      scope: "personal",
      items: [
        {
          id: "personal:slack",
          provider: "slack",
          scope: "personal",
          display_name: "Slack",
          status: "connected",
          enabled: true,
          metadata: {},
          actions: ["disable", "remove"]
        }
      ]
    })
    mocks.updatePersonalIntegration.mockResolvedValue({
      id: "personal:slack",
      provider: "slack",
      scope: "personal",
      display_name: "Slack",
      status: "disabled",
      enabled: false,
      metadata: {},
      actions: ["enable", "remove"]
    })
    mocks.deletePersonalIntegration.mockResolvedValue({
      deleted: true,
      provider: "slack",
      connection_id: "personal:slack"
    })

    renderWithQueryClient(<IntegrationManagementPage scope="personal" />)

    await user.click(await screen.findByRole("button", { name: "Manage" }))
    await user.click(await screen.findByRole("button", { name: "Disable" }))

    await waitFor(() => {
      expect(mocks.updatePersonalIntegration).toHaveBeenCalledWith("slack", "personal:slack", { enabled: false })
    })

    await user.click(await screen.findByRole("button", { name: "Remove" }))

    await waitFor(() => {
      expect(mocks.deletePersonalIntegration).toHaveBeenCalledWith("slack", "personal:slack")
    })
  })

  it("renders workspace slack, discord, and telegram controls", async () => {
    mocks.listWorkspaceIntegrations.mockResolvedValue({
      scope: "workspace",
      items: [
        {
          id: "workspace:slack",
          provider: "slack",
          scope: "workspace",
          display_name: "Slack workspace",
          status: "connected",
          enabled: true,
          metadata: {},
          actions: ["refresh"]
        },
        {
          id: "workspace:discord",
          provider: "discord",
          scope: "workspace",
          display_name: "Discord workspace",
          status: "connected",
          enabled: true,
          metadata: {},
          actions: ["refresh"]
        },
        {
          id: "workspace:telegram",
          provider: "telegram",
          scope: "workspace",
          display_name: "Telegram bot",
          status: "needs_config",
          enabled: false,
          metadata: {},
          actions: ["configure"]
        }
      ]
    })
    mocks.getWorkspaceSlackPolicy.mockResolvedValue({
      provider: "slack",
      scope: "workspace",
      installation_ids: ["T-1"],
      uniform: true,
      policy: {
        allowed_commands: ["help"],
        channel_allowlist: [],
        channel_denylist: [],
        default_response_mode: "thread",
        strict_user_mapping: false,
        service_user_id: null,
        user_mappings: {},
        workspace_quota_per_minute: 10,
        user_quota_per_minute: 5,
        status_scope: "workspace"
      }
    })
    mocks.getWorkspaceDiscordPolicy.mockResolvedValue({
      provider: "discord",
      scope: "workspace",
      installation_ids: ["G-1"],
      uniform: true,
      policy: {
        allowed_commands: ["help"],
        channel_allowlist: [],
        channel_denylist: [],
        default_response_mode: "channel",
        strict_user_mapping: false,
        service_user_id: null,
        user_mappings: {},
        guild_quota_per_minute: 10,
        user_quota_per_minute: 5,
        status_scope: "guild"
      }
    })
    mocks.getWorkspaceTelegramBot.mockResolvedValue({
      ok: true,
      provider: "telegram",
      scope_type: "org",
      scope_id: 1,
      bot_username: "examplebot",
      enabled: true
    })
    mocks.listWorkspaceTelegramLinkedActors.mockResolvedValue({
      ok: true,
      scope_type: "org",
      scope_id: 1,
      items: []
    })

    renderWithQueryClient(<IntegrationManagementPage scope="workspace" />)

    expect(await screen.findByText("Slack")).toBeInTheDocument()
    expect(screen.getByText("Discord")).toBeInTheDocument()
    expect(screen.getByText("Telegram")).toBeInTheDocument()
    expect(screen.getByText("Slack policy")).toBeInTheDocument()
    expect(screen.getByText("Telegram bot")).toBeInTheDocument()
  })
})
