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
          json: async () => ({ commands: [existingCommand, existingExternalCommand] })
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
})
