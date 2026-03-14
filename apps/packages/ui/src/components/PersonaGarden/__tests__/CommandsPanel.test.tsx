import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  fetchWithAuth: vi.fn(),
  serverCapabilities: {
    capabilities: { hasMcp: true },
    loading: false
  },
  fetchMcpToolCatalogs: vi.fn(),
  fetchMcpTools: vi.fn(),
  fetchMcpToolCatalogsViaDiscovery: vi.fn(),
  fetchMcpModulesViaDiscovery: vi.fn(),
  fetchMcpToolsViaDiscovery: vi.fn()
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

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => mocks.serverCapabilities
}))

vi.mock("@/services/tldw/mcp", () => ({
  fetchMcpToolCatalogs: (...args: unknown[]) =>
    (mocks.fetchMcpToolCatalogs as (...args: unknown[]) => unknown)(...args),
  fetchMcpTools: (...args: unknown[]) =>
    (mocks.fetchMcpTools as (...args: unknown[]) => unknown)(...args),
  fetchMcpToolCatalogsViaDiscovery: (...args: unknown[]) =>
    (mocks.fetchMcpToolCatalogsViaDiscovery as (...args: unknown[]) => unknown)(...args),
  fetchMcpModulesViaDiscovery: (...args: unknown[]) =>
    (mocks.fetchMcpModulesViaDiscovery as (...args: unknown[]) => unknown)(...args),
  fetchMcpToolsViaDiscovery: (...args: unknown[]) =>
    (mocks.fetchMcpToolsViaDiscovery as (...args: unknown[]) => unknown)(...args)
}))

import { CommandsPanel } from "../CommandsPanel"

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const renderWithQueryClient = (ui: React.ReactNode) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  })

  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  )
}

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

const analytics = {
  persona_id: "persona-1",
  summary: {
    total_events: 8,
    direct_command_count: 6,
    planner_fallback_count: 2,
    success_rate: 75,
    fallback_rate: 25,
    avg_response_time_ms: 180
  },
  commands: [
    {
      command_id: "cmd-search",
      command_name: "Search Notes",
      total_invocations: 6,
      success_count: 4,
      error_count: 2,
      avg_response_time_ms: 150,
      last_used: "2026-03-12T18:00:00Z"
    },
    {
      command_id: "cmd-external",
      command_name: "Search Slack Alerts",
      total_invocations: 1,
      success_count: 1,
      error_count: 0,
      avg_response_time_ms: 220,
      last_used: "2026-03-12T17:30:00Z"
    }
  ],
  fallbacks: {
    total_invocations: 2,
    success_count: 2,
    error_count: 0,
    avg_response_time_ms: 240,
    last_used: "2026-03-12T18:15:00Z"
  }
}

describe("CommandsPanel", () => {
  beforeEach(() => {
    mocks.fetchWithAuth.mockReset()
    mocks.serverCapabilities = {
      capabilities: { hasMcp: true },
      loading: false
    }
    mocks.fetchMcpToolCatalogs.mockReset()
    mocks.fetchMcpTools.mockReset()
    mocks.fetchMcpToolCatalogsViaDiscovery.mockReset()
    mocks.fetchMcpModulesViaDiscovery.mockReset()
    mocks.fetchMcpToolsViaDiscovery.mockReset()
    mocks.fetchMcpToolCatalogsViaDiscovery.mockResolvedValue([
      { id: 1, name: "Global Notes" }
    ])
    mocks.fetchMcpModulesViaDiscovery.mockResolvedValue(["alerts", "media", "notes"])
    mocks.fetchMcpToolsViaDiscovery.mockResolvedValue([
      { name: "notes.search", module: "notes", canExecute: true },
      { name: "notes.create", module: "notes", canExecute: true },
      { name: "media.search", module: "media", canExecute: true }
    ])
    mocks.fetchMcpToolCatalogs.mockResolvedValue([])
    mocks.fetchMcpTools.mockResolvedValue([])
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
    renderWithQueryClient(
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
    renderWithQueryClient(
      <CommandsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
      />
    )

    await screen.findByTestId("persona-commands-row-cmd-search")
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
    renderWithQueryClient(
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
    renderWithQueryClient(
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

  it("clears stale command data and editor state when switching personas", async () => {
    const persona2Commands = createDeferred<{ commands: unknown[] }>()
    const persona2Connections = createDeferred<unknown[]>()

    mocks.fetchWithAuth.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
      if (
        path === "/api/v1/persona/profiles/persona-1/voice-commands" &&
        (!init?.method || init.method === "GET")
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            commands: [existingCommand]
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
        path === "/api/v1/persona/profiles/persona-2/voice-commands" &&
        (!init?.method || init.method === "GET")
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => persona2Commands.promise
        })
      }
      if (
        path === "/api/v1/persona/profiles/persona-2/connections" &&
        (!init?.method || init.method === "GET")
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => persona2Connections.promise
        })
      }
      return Promise.resolve({
        ok: false,
        error: `Unhandled path: ${path}`
      })
    })

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false
        }
      }
    })
    const view = render(
      <QueryClientProvider client={queryClient}>
        <CommandsPanel
          selectedPersonaId="persona-1"
          selectedPersonaName="Garden Helper"
          isActive
        />
      </QueryClientProvider>
    )

    await screen.findByText("Search Notes")
    fireEvent.click(screen.getByTestId("persona-commands-edit-cmd-search"))
    fireEvent.change(screen.getByTestId("persona-commands-name-input"), {
      target: { value: "Stale edited name" }
    })
    expect(screen.getByTestId("persona-commands-name-input")).toHaveValue(
      "Stale edited name"
    )

    view.rerender(
      <QueryClientProvider client={queryClient}>
        <CommandsPanel
          selectedPersonaId="persona-2"
          selectedPersonaName="Other Helper"
          isActive
        />
      </QueryClientProvider>
    )

    await waitFor(() => {
      expect(screen.queryByTestId("persona-commands-row-cmd-search")).not.toBeInTheDocument()
      expect(screen.getByTestId("persona-commands-name-input")).toHaveValue("")
    })

    persona2Commands.resolve({ commands: [] })
    persona2Connections.resolve([])

    await waitFor(() =>
      expect(screen.getByTestId("persona-commands-empty")).toBeInTheDocument()
    )
  })

  it("loads external request fields when editing a connection-backed custom command", async () => {
    renderWithQueryClient(
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
    renderWithQueryClient(
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

    renderWithQueryClient(
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
    expect(
      screen.getByTestId("persona-commands-row-cmd-missing-connection")
    ).toHaveAttribute("data-selected", "true")
    expect(onOpenCommandHandled).toHaveBeenCalledWith("cmd-missing-connection")
  })

  it("prefills a new command draft from a test lab phrase", async () => {
    const onDraftCommandPhraseHandled = vi.fn()

    renderWithQueryClient(
      <CommandsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
        draftCommandPhrase="start a focused research sprint"
        onDraftCommandPhraseHandled={onDraftCommandPhraseHandled}
      />
    )

    await screen.findByText("Search Notes")
    expect(screen.getByTestId("persona-commands-name-input")).toHaveValue(
      "Start a focused research sprint"
    )
    expect(screen.getByTestId("persona-commands-phrases-input")).toHaveValue(
      "start a focused research sprint"
    )
    expect(
      screen.getByText(
        "Drafted from Test Lab. Adjust the phrase, add placeholders like {topic} if needed, then choose a target."
      )
    ).toBeInTheDocument()
    expect(onDraftCommandPhraseHandled).toHaveBeenCalledWith(
      "start a focused research sprint"
    )
  })

  it("applies phrase-to-slot assist suggestions for drafted commands", async () => {
    renderWithQueryClient(
      <CommandsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
        draftCommandPhrase="search notes for model context protocol"
      />
    )

    await screen.findByText("Search Notes")
    expect(
      screen.getByTestId("persona-commands-draft-assist-chip-topic")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("persona-commands-draft-assist-chip-topic"))

    expect(screen.getByTestId("persona-commands-phrases-input")).toHaveValue(
      "search notes for {topic}"
    )
    expect(screen.getByTestId("persona-commands-slot-map-input")).toHaveValue(
      '{\n  "query": "topic"\n}'
    )
  })

  it("requests a test-lab rerun after saving a repaired command", async () => {
    const onOpenCommandHandled = vi.fn()
    const onRerunAfterSave = vi.fn()

    renderWithQueryClient(
      <CommandsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
        openCommandId="cmd-missing-connection"
        onOpenCommandHandled={onOpenCommandHandled}
        rerunAfterSaveCommandId="cmd-missing-connection"
        onRerunAfterSave={onRerunAfterSave}
      />
    )

    await screen.findByText("Broken Alerts Command")
    await waitFor(() =>
      expect(screen.getByTestId("persona-commands-name-input")).toHaveValue(
        "Broken Alerts Command"
      )
    )

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
    expect(onRerunAfterSave).toHaveBeenCalledWith("cmd-missing-connection")
  })

  it("creates an mcp tool command from picker selection instead of raw tool text", async () => {
    renderWithQueryClient(
      <CommandsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
      />
    )

    await screen.findByText("Search Notes")
    fireEvent.change(screen.getByTestId("persona-commands-name-input"), {
      target: { value: "Search Notes Picker" }
    })
    fireEvent.change(screen.getByTestId("persona-commands-phrases-input"), {
      target: { value: "search notes with picker" }
    })
    fireEvent.change(screen.getByTestId("persona-mcp-tool-picker-module-select"), {
      target: { value: "notes" }
    })
    fireEvent.change(screen.getByTestId("persona-mcp-tool-picker-tool-select"), {
      target: { value: "notes.search" }
    })
    fireEvent.click(screen.getByTestId("persona-commands-save"))

    await waitFor(() =>
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
        "/api/v1/persona/profiles/persona-1/voice-commands",
        expect.objectContaining({
          method: "POST",
          body: expect.objectContaining({
            name: "Search Notes Picker",
            action_type: "mcp_tool",
            action_config: expect.objectContaining({
              tool_name: "notes.search"
            })
          })
        })
      )
    )
  })

  it("rehydrates an existing mcp tool command into the picker", async () => {
    renderWithQueryClient(
      <CommandsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
      />
    )

    await screen.findByText("Search Notes")
    fireEvent.click(screen.getByTestId("persona-commands-edit-cmd-search"))

    await waitFor(() =>
      expect(screen.getByTestId("persona-mcp-tool-picker-tool-select")).toHaveValue(
        "notes.search"
      )
    )
    expect(screen.getByTestId("persona-mcp-tool-picker-module-select")).toHaveValue(
      "notes"
    )
  })

  it("shows persona voice analytics summary and per-command health badges", async () => {
    renderWithQueryClient(
      <CommandsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
        analytics={analytics}
      />
    )

    await screen.findByText("Search Notes")

    expect(screen.getByTestId("persona-command-analytics-summary")).toBeInTheDocument()
    expect(screen.getByTestId("persona-command-analytics-total-events")).toHaveTextContent(
      "8"
    )
    expect(screen.getByTestId("persona-command-analytics-success-rate")).toHaveTextContent(
      "75%"
    )
    expect(screen.getByTestId("persona-command-analytics-fallback-rate")).toHaveTextContent(
      "25%"
    )

    expect(screen.getByTestId("persona-commands-analytics-cmd-search")).toHaveTextContent(
      "6 runs"
    )
    expect(screen.getByTestId("persona-commands-analytics-cmd-search")).toHaveTextContent(
      "2 failures"
    )
    expect(screen.getByTestId("persona-commands-analytics-cmd-external")).toHaveTextContent(
      "1 run"
    )
  })
})
