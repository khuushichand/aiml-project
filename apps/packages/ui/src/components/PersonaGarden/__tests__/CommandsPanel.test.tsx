import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  fetchWithAuth: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    fetchWithAuth: (...args: unknown[]) =>
      (mocks.fetchWithAuth as (...args: unknown[]) => unknown)(...args)
  }
}))

import { CommandsPanel } from "../CommandsPanel"

const existingCommand = {
  id: "cmd-search",
  persona_id: "persona-1",
  name: "Search Notes",
  phrases: ["search notes for {topic}"],
  action_type: "mcp_tool",
  action_config: {
    tool_name: "notes.search",
    slot_to_param_map: { query: "topic" }
  },
  priority: 50,
  enabled: true,
  requires_confirmation: false
}

const existingExternalCommand = {
  id: "cmd-external",
  persona_id: "persona-1",
  connection_id: "conn-1",
  connection_status: "ok",
  connection_name: "Slack Alerts",
  name: "Search Slack Alerts",
  phrases: ["search slack alerts for {query}"],
  action_type: "custom",
  action_config: {
    action: "external_search",
    method: "POST",
    path: "alerts/search",
    slot_to_param_map: { query: "query" }
  },
  priority: 40,
  enabled: true,
  requires_confirmation: true
}

const missingConnectionCommand = {
  id: "cmd-missing-connection",
  persona_id: "persona-1",
  connection_id: "conn-missing",
  connection_status: "missing",
  connection_name: null,
  name: "Broken Alerts Command",
  phrases: ["send broken alert for {query}"],
  action_type: "custom",
  action_config: {
    action: "external_request",
    method: "POST",
    path: "alerts/send",
    slot_to_param_map: { query: "query" }
  },
  priority: 20,
  enabled: true,
  requires_confirmation: true
}

const connections = [
  {
    id: "conn-1",
    name: "Slack Alerts",
    auth_type: "bearer",
    secret_configured: true
  }
]

describe("CommandsPanel", () => {
  beforeEach(() => {
    mocks.fetchWithAuth.mockReset()
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
      if (
        path === "/api/v1/persona/profiles/persona-1/voice-commands" &&
        (!init?.method || init.method === "GET")
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            commands: [existingCommand, existingExternalCommand, missingConnectionCommand]
          })
        })
      }
      if (
        path === "/api/v1/persona/profiles/persona-1/connections" &&
        (!init?.method || init.method === "GET")
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => connections
        })
      }
      if (
        path === "/api/v1/persona/profiles/persona-1/voice-commands" &&
        init?.method === "POST"
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "cmd-created",
            persona_id: "persona-1",
            name: init.body.name,
            phrases: init.body.phrases,
            action_type: init.body.action_type,
            action_config: init.body.action_config,
            priority: init.body.priority,
            enabled: init.body.enabled,
            requires_confirmation: init.body.requires_confirmation,
            connection_id: init.body.connection_id
          })
        })
      }
      if (
        path === "/api/v1/persona/profiles/persona-1/voice-commands/cmd-search" &&
        init?.method === "PUT"
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            ...existingCommand,
            name: init.body.name,
            description: init.body.description
          })
        })
      }
      if (
        path === "/api/v1/persona/profiles/persona-1/voice-commands/cmd-external" &&
        init?.method === "PUT"
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            ...existingExternalCommand,
            name: init.body.name,
            description: init.body.description,
            action_config: init.body.action_config,
            connection_id: init.body.connection_id,
            requires_confirmation: init.body.requires_confirmation
          })
        })
      }
      if (
        path ===
          "/api/v1/persona/profiles/persona-1/voice-commands/cmd-missing-connection" &&
        init?.method === "PUT"
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            ...missingConnectionCommand,
            name: init.body.name,
            description: init.body.description,
            action_config: init.body.action_config,
            connection_id: init.body.connection_id,
            connection_status: "ok",
            connection_name: "Slack Alerts",
            requires_confirmation: init.body.requires_confirmation
          })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `Unhandled path: ${path}`
      })
    })
  })

  it("loads existing commands and creates a templated command", async () => {
    render(
      <CommandsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
      />
    )

    expect(await screen.findByText("Search Notes")).toBeInTheDocument()
    fireEvent.click(screen.getByTestId("persona-commands-template-media-search"))
    fireEvent.change(screen.getByTestId("persona-commands-connection-select"), {
      target: { value: "conn-1" }
    })
    fireEvent.click(screen.getByTestId("persona-commands-save"))

    await waitFor(() =>
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
        "/api/v1/persona/profiles/persona-1/voice-commands",
        expect.objectContaining({
          method: "POST",
          body: expect.objectContaining({
            name: "Search Library",
            connection_id: "conn-1",
            phrases: [
              "search library for {query}",
              "find media about {query}"
            ],
            action_type: "mcp_tool",
            action_config: expect.objectContaining({
              tool_name: "media.search",
              slot_to_param_map: { query: "query" }
            })
          })
        })
      )
    )
    expect(
      await screen.findByTestId("persona-commands-edit-cmd-created")
    ).toBeInTheDocument()
  })

  it("creates a connection-backed external command with method and path", async () => {
    render(
      <CommandsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
      />
    )

    await screen.findByText("Search Notes")
    fireEvent.change(screen.getByTestId("persona-commands-name-input"), {
      target: { value: "Call Slack Alerts API" }
    })
    fireEvent.change(screen.getByTestId("persona-commands-phrases-input"), {
      target: { value: "search slack alerts for {query}" }
    })
    fireEvent.change(screen.getByTestId("persona-commands-action-type-select"), {
      target: { value: "custom" }
    })
    fireEvent.change(screen.getByTestId("persona-commands-connection-select"), {
      target: { value: "conn-1" }
    })
    fireEvent.change(screen.getByTestId("persona-commands-custom-action-input"), {
      target: { value: "external_search" }
    })
    fireEvent.change(screen.getByTestId("persona-commands-http-method-select"), {
      target: { value: "POST" }
    })
    fireEvent.change(screen.getByTestId("persona-commands-request-path-input"), {
      target: { value: "alerts/search" }
    })
    fireEvent.click(screen.getByTestId("persona-commands-save"))

    await waitFor(() =>
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
        "/api/v1/persona/profiles/persona-1/voice-commands",
        expect.objectContaining({
          method: "POST",
          body: expect.objectContaining({
            name: "Call Slack Alerts API",
            connection_id: "conn-1",
            action_type: "custom",
            action_config: expect.objectContaining({
              action: "external_search",
              method: "POST",
              path: "alerts/search"
            })
          })
        })
      )
    )
  })

  it("applies the external api template with connection-ready defaults", async () => {
    render(
      <CommandsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
      />
    )

    await screen.findByText("Search Notes")
    fireEvent.click(screen.getByTestId("persona-commands-template-external-api"))

    expect(screen.getByTestId("persona-commands-name-input")).toHaveValue(
      "Call External API"
    )
    expect(screen.getByTestId("persona-commands-action-type-select")).toHaveValue(
      "custom"
    )
    expect(screen.getByTestId("persona-commands-custom-action-input")).toHaveValue(
      "external_request"
    )

    fireEvent.change(screen.getByTestId("persona-commands-connection-select"), {
      target: { value: "conn-1" }
    })

    expect(screen.getByTestId("persona-commands-http-method-select")).toHaveValue(
      "POST"
    )
    expect(screen.getByTestId("persona-commands-request-path-input")).toHaveValue(
      ""
    )

    fireEvent.click(screen.getByTestId("persona-commands-save"))

    await waitFor(() =>
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
        "/api/v1/persona/profiles/persona-1/voice-commands",
        expect.objectContaining({
          method: "POST",
          body: expect.objectContaining({
            name: "Call External API",
            connection_id: "conn-1",
            action_type: "custom",
            action_config: expect.objectContaining({
              action: "external_request",
              method: "POST"
            })
          })
        })
      )
    )
  })

  it("loads a command into the editor and updates it", async () => {
    render(
      <CommandsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
      />
    )

    await screen.findByText("Search Notes")
    fireEvent.click(screen.getByTestId("persona-commands-edit-cmd-search"))
    fireEvent.change(screen.getByTestId("persona-commands-description-input"), {
      target: { value: "Updated description" }
    })
    fireEvent.click(screen.getByTestId("persona-commands-save"))

    await waitFor(() =>
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
        "/api/v1/persona/profiles/persona-1/voice-commands/cmd-search",
        expect.objectContaining({
          method: "PUT",
          body: expect.objectContaining({
            name: "Search Notes",
            description: "Updated description"
          })
        })
      )
    )
  })

  it("loads external request fields when editing a connection-backed custom command", async () => {
    render(
      <CommandsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
      />
    )

    await screen.findByText("Search Slack Alerts")
    fireEvent.click(screen.getByTestId("persona-commands-edit-cmd-external"))

    expect(screen.getByTestId("persona-commands-custom-action-input")).toHaveValue(
      "external_search"
    )
    expect(screen.getByTestId("persona-commands-http-method-select")).toHaveValue(
      "POST"
    )
    expect(screen.getByTestId("persona-commands-request-path-input")).toHaveValue(
      "alerts/search"
    )
  })

  it("surfaces missing connection commands and requires a valid replacement before saving", async () => {
    render(
      <CommandsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
      />
    )

    expect(await screen.findByText("Broken Alerts Command")).toBeInTheDocument()
    expect(screen.getByText("missing connection")).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("persona-commands-edit-cmd-missing-connection"))

    expect(screen.getByTestId("persona-commands-connection-select")).toHaveValue(
      "conn-missing"
    )
    expect(
      screen.getAllByText(
        "Selected connection no longer exists. Choose another connection or clear it."
      )
    ).toHaveLength(1)

    fireEvent.click(screen.getByTestId("persona-commands-save"))

    expect(
      await screen.findAllByText(
        "Selected connection no longer exists. Choose another connection or clear it."
      )
    ).toHaveLength(2)
    expect(
      mocks.fetchWithAuth.mock.calls.filter(
        ([path, init]: [string, { method?: string } | undefined]) =>
          path ===
            "/api/v1/persona/profiles/persona-1/voice-commands/cmd-missing-connection" &&
          init?.method === "PUT"
      )
    ).toHaveLength(0)

    fireEvent.change(screen.getByTestId("persona-commands-connection-select"), {
      target: { value: "conn-1" }
    })
    fireEvent.click(screen.getByTestId("persona-commands-save"))

    await waitFor(() =>
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
        "/api/v1/persona/profiles/persona-1/voice-commands/cmd-missing-connection",
        expect.objectContaining({
          method: "PUT",
          body: expect.objectContaining({
            connection_id: "conn-1"
          })
        })
      )
    )
  })

  it("opens a requested command in the editor when routed from test lab", async () => {
    const onOpenCommandHandled = vi.fn()

    render(
      <CommandsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
        openCommandId="cmd-missing-connection"
        onOpenCommandHandled={onOpenCommandHandled}
      />
    )

    await screen.findByText("Broken Alerts Command")
    await waitFor(() =>
      expect(screen.getByTestId("persona-commands-name-input")).toHaveValue(
        "Broken Alerts Command"
      )
    )
    expect(screen.getByTestId("persona-commands-connection-select")).toHaveValue(
      "conn-missing"
    )
    expect(onOpenCommandHandled).toHaveBeenCalledWith("cmd-missing-connection")
  })
})
