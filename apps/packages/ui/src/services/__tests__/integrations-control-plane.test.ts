import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args)
}))

import {
  connectPersonalIntegration,
  createWorkspaceTelegramPairingCode,
  deletePersonalIntegration,
  getWorkspaceDiscordPolicy,
  getWorkspaceSlackPolicy,
  getWorkspaceTelegramBot,
  listPersonalIntegrations,
  listWorkspaceIntegrations,
  listWorkspaceTelegramLinkedActors,
  revokeWorkspaceTelegramLinkedActor,
  updatePersonalIntegration,
  updateWorkspaceDiscordPolicy,
  updateWorkspaceSlackPolicy,
  updateWorkspaceTelegramBot,
  type DiscordWorkspacePolicyUpdate,
  type PersonalIntegrationUpdatePayload,
  type SlackWorkspacePolicyUpdate,
  type TelegramBotConfigUpdate
} from "@/services/integrations-control-plane"

describe("integrations control-plane contract", () => {
  beforeEach(() => {
    mocks.bgRequest.mockReset()
  })

  it("lists personal integrations via the normalized endpoint", async () => {
    mocks.bgRequest.mockResolvedValue({
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
        }
      ]
    })

    const response = await listPersonalIntegrations()

    expect(response.scope).toBe("personal")
    expect(response.items[0]?.provider).toBe("slack")
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "GET",
        path: "/api/v1/integrations/personal"
      })
    )
  })

  it("starts the normalized personal slack connect flow", async () => {
    mocks.bgRequest.mockResolvedValue({
      provider: "slack",
      connection_id: "personal:slack",
      status: "ready",
      auth_url: "https://slack.example.test/oauth",
      auth_session_id: "session-123",
      expires_at: "2026-03-20T22:00:00Z"
    })

    const response = await connectPersonalIntegration("slack")

    expect(response.provider).toBe("slack")
    expect(response.auth_url).toBe("https://slack.example.test/oauth")
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "POST",
        path: "/api/v1/integrations/personal/slack/connect"
      })
    )
  })

  it("updates a personal integration using the normalized provider-level id", async () => {
    const payload: PersonalIntegrationUpdatePayload = {
      enabled: false
    }
    mocks.bgRequest.mockResolvedValue({
      id: "personal:slack",
      provider: "slack",
      scope: "personal",
      display_name: "Slack",
      status: "disabled",
      enabled: false,
      metadata: {
        installation_count: 2,
        active_installation_count: 0
      },
      actions: ["reconnect", "enable", "remove"]
    })

    const response = await updatePersonalIntegration("slack", "personal:slack", payload)

    expect(response.status).toBe("disabled")
    expect(response.enabled).toBe(false)
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "PATCH",
        path: "/api/v1/integrations/personal/slack/personal%3Aslack",
        body: {
          enabled: false
        }
      })
    )
  })

  it("deletes a personal integration using the normalized provider-level id", async () => {
    mocks.bgRequest.mockResolvedValue({
      deleted: true,
      provider: "discord",
      connection_id: "personal:discord"
    })

    const response = await deletePersonalIntegration("discord", "personal:discord")

    expect(response.deleted).toBe(true)
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "DELETE",
        path: "/api/v1/integrations/personal/discord/personal%3Adiscord"
      })
    )
  })

  it("updates slack workspace policy with the typed payload", async () => {
    const payload: SlackWorkspacePolicyUpdate = {
      allowed_commands: ["help", "status"],
      default_response_mode: "thread",
      status_scope: "workspace_and_user"
    }
    mocks.bgRequest.mockResolvedValue({
      provider: "slack",
      scope: "workspace",
      installation_ids: ["T-11"],
      uniform: true,
      policy: {
        allowed_commands: ["help", "status"],
        channel_allowlist: [],
        channel_denylist: [],
        default_response_mode: "thread",
        strict_user_mapping: false,
        service_user_id: null,
        user_mappings: {},
        workspace_quota_per_minute: 10,
        user_quota_per_minute: 5,
        status_scope: "workspace_and_user"
      }
    })

    const response = await updateWorkspaceSlackPolicy(payload)

    expect(response.policy.allowed_commands).toEqual(["help", "status"])
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "PUT",
        path: "/api/v1/integrations/workspace/slack/policy",
        body: expect.objectContaining({
          allowed_commands: ["help", "status"],
          default_response_mode: "thread",
          status_scope: "workspace_and_user"
        })
      })
    )
  })

  it("round-trips telegram bot config payloads", async () => {
    const payload: TelegramBotConfigUpdate = {
      bot_token: "token-123",
      webhook_secret: "webhook-secret",
      bot_username: "@ExampleBot",
      enabled: true
    }
    mocks.bgRequest.mockResolvedValue({
      ok: true,
      provider: "telegram",
      scope_type: "org",
      scope_id: 22,
      bot_username: "examplebot",
      enabled: true
    })

    const response = await updateWorkspaceTelegramBot(payload)

    expect(response.bot_username).toBe("examplebot")
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "PUT",
        path: "/api/v1/integrations/workspace/telegram/bot",
        body: expect.objectContaining({
          bot_token: "token-123",
          webhook_secret: "webhook-secret",
          bot_username: "@ExampleBot",
          enabled: true
        })
      })
    )
  })

  it("covers telegram pairing code and linked-actor routes", async () => {
    mocks.bgRequest
      .mockResolvedValueOnce({
        ok: true,
        pairing_code: "ABCD1234",
        scope_type: "team",
        scope_id: 7,
        expires_at: "2026-03-20T22:00:00Z"
      })
      .mockResolvedValueOnce({
        ok: true,
        scope_type: "team",
        scope_id: 7,
        items: [{ id: 9, scope_type: "team", scope_id: 7, telegram_user_id: 12, auth_user_id: 34 }]
      })
      .mockResolvedValueOnce({
        ok: true,
        deleted: true,
        id: 9,
        scope_type: "team",
        scope_id: 7
      })

    const pairing = await createWorkspaceTelegramPairingCode()
    const linked = await listWorkspaceTelegramLinkedActors()
    const revoked = await revokeWorkspaceTelegramLinkedActor(9)

    expect(pairing.pairing_code).toBe("ABCD1234")
    expect(linked.items[0]?.id).toBe(9)
    expect(revoked.deleted).toBe(true)
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        method: "POST",
        path: "/api/v1/integrations/workspace/telegram/pairing-code"
      })
    )
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        method: "GET",
        path: "/api/v1/integrations/workspace/telegram/linked-actors"
      })
    )
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({
        method: "DELETE",
        path: "/api/v1/integrations/workspace/telegram/linked-actors/9"
      })
    )
  })

  it("targets the discord workspace policy endpoint", async () => {
    const payload: DiscordWorkspacePolicyUpdate = {
      allowed_commands: ["help"],
      default_response_mode: "channel",
      status_scope: "guild_and_user"
    }
    mocks.bgRequest.mockResolvedValue({
      provider: "discord",
      scope: "workspace",
      installation_ids: [],
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
        status_scope: "guild_and_user"
      }
    })

    const response = await updateWorkspaceDiscordPolicy(payload)

    expect(response.provider).toBe("discord")
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "PUT",
        path: "/api/v1/integrations/workspace/discord/policy",
        body: expect.objectContaining({
          allowed_commands: ["help"],
          default_response_mode: "channel",
          status_scope: "guild_and_user"
        })
      })
    )
  })

  it("rejects personal integration mutations when the connection id does not match the provider", async () => {
    await expect(
      updatePersonalIntegration("slack", "personal:discord", {
        enabled: false
      })
    ).rejects.toThrow("connectionId must target personal:slack")

    await expect(
      deletePersonalIntegration("discord", "personal:slack")
    ).rejects.toThrow("connectionId must target personal:discord")

    expect(mocks.bgRequest).not.toHaveBeenCalled()
  })

  it("requires an explicit enabled flag when updating the telegram bot", async () => {
    await expect(
      updateWorkspaceTelegramBot(
        {
          bot_token: "token-123",
          webhook_secret: "webhook-secret",
          bot_username: "@ExampleBot"
        } as unknown as TelegramBotConfigUpdate
      )
    ).rejects.toThrow("enabled must be set explicitly")

    expect(mocks.bgRequest).not.toHaveBeenCalled()
  })

  it("rejects null clear payloads that the workspace policy backend currently ignores", async () => {
    await expect(
      updateWorkspaceSlackPolicy(
        {
          service_user_id: null
        } as unknown as SlackWorkspacePolicyUpdate
      )
    ).rejects.toThrow("Null policy fields are not supported")

    await expect(
      updateWorkspaceDiscordPolicy(
        {
          user_mappings: null
        } as unknown as DiscordWorkspacePolicyUpdate
      )
    ).rejects.toThrow("Null policy fields are not supported")

    expect(mocks.bgRequest).not.toHaveBeenCalled()
  })

  it("reads the workspace integrations overview", async () => {
    mocks.bgRequest.mockResolvedValue({
      scope: "workspace",
      items: []
    })

    const response = await listWorkspaceIntegrations()
    await getWorkspaceSlackPolicy()
    await getWorkspaceDiscordPolicy()
    await getWorkspaceTelegramBot()

    expect(response.scope).toBe("workspace")
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        method: "GET",
        path: "/api/v1/integrations/workspace"
      })
    )
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        method: "GET",
        path: "/api/v1/integrations/workspace/slack/policy"
      })
    )
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({
        method: "GET",
        path: "/api/v1/integrations/workspace/discord/policy"
      })
    )
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      4,
      expect.objectContaining({
        method: "GET",
        path: "/api/v1/integrations/workspace/telegram/bot"
      })
    )
  })
})
