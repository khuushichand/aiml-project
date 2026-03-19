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

import { TestLabPanel } from "../TestLabPanel"

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
  live_voice: {
    total_committed_turns: 8,
    vad_auto_commit_count: 5,
    manual_commit_count: 3,
    vad_auto_rate: 63,
    manual_commit_rate: 38,
    degraded_session_count: 1
  },
  commands: [
    {
      command_id: "cmd-alert",
      command_name: "Send Alert",
      total_invocations: 6,
      success_count: 4,
      error_count: 2,
      avg_response_time_ms: 210,
      last_used: "2026-03-12T18:00:00Z"
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

describe("TestLabPanel", () => {
  beforeEach(() => {
    mocks.fetchWithAuth.mockReset()
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
      if (
        path === "/api/v1/persona/profiles/persona-1/voice-commands/test" &&
        init?.method === "POST"
      ) {
        if (init.body.heard_text === "start a focused research sprint") {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              heard_text: init.body.heard_text,
              matched: false,
              match_reason: "no_direct_match",
              command_id: null,
              command_name: null,
              extracted_params: {},
              planned_action: {
                target_type: "llm_chat",
                target_name: "persona planner",
                payload_preview: { heard_text: init.body.heard_text }
              },
              safety_gate: {
                classification: "planner_fallback",
                requires_confirmation: false,
                reason: "persona_fallback"
              },
              fallback_to_persona_planner: true,
              failure_phase: null
            })
          })
        }
        if (init.body.heard_text === "send alert repaired") {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              heard_text: init.body.heard_text,
              matched: true,
              match_reason: "phrase_pattern",
              command_id: "cmd-alert",
              command_name: "Send Alert",
              connection_id: "conn-1",
              connection_status: "ok",
              connection_name: "Slack Alerts",
              extracted_params: { query: "repaired" },
              planned_action: {
                target_type: "custom",
                target_name: "external_request",
                payload_preview: { query: "repaired" }
              },
              safety_gate: {
                classification: "write_external",
                requires_confirmation: true,
                reason: "command_requires_confirmation"
              },
              fallback_to_persona_planner: false,
              failure_phase: null
            })
          })
        }
        if (init.body.heard_text === "send alert for model drift") {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              heard_text: init.body.heard_text,
              matched: true,
              match_reason: "phrase_pattern",
              command_id: "cmd-alert",
              command_name: "Send Alert",
              connection_id: "conn-missing",
              connection_status: "missing",
              connection_name: null,
              extracted_params: { query: "model drift" },
              planned_action: {
                target_type: "custom",
                target_name: "external_request",
                payload_preview: { query: "model drift" }
              },
              safety_gate: {
                classification: "write_external",
                requires_confirmation: true,
                reason: "command_requires_confirmation"
              },
              fallback_to_persona_planner: false,
              failure_phase: "missing_connection"
            })
          })
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({
            heard_text: init.body.heard_text,
            matched: true,
            match_reason: "slot_pattern",
            command_name: "Search Notes",
            extracted_params: { topic: "model context protocol" },
            planned_action: {
              target_type: "mcp_tool",
              target_name: "notes.search",
              payload_preview: { query: "model context protocol" }
            },
            safety_gate: {
              classification: "read_only",
              requires_confirmation: false,
              reason: "persona_default"
            },
            fallback_to_persona_planner: false
          })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `Unhandled path: ${path}`
      })
    })
  })

  it("runs a dry-run and renders the matching pipeline", async () => {
    render(
      <TestLabPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
        analytics={analytics}
      />
    )

    fireEvent.change(screen.getByTestId("persona-test-lab-heard-input"), {
      target: { value: "search notes for model context protocol" }
    })
    fireEvent.click(screen.getByTestId("persona-test-lab-run"))

    await waitFor(() =>
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
        "/api/v1/persona/profiles/persona-1/voice-commands/test",
        expect.objectContaining({
          method: "POST",
          body: { heard_text: "search notes for model context protocol" }
        })
      )
    )
    expect(await screen.findByTestId("persona-test-lab-match-status")).toHaveTextContent(
      "direct command"
    )
    expect(screen.getByText("mcp_tool -> notes.search")).toBeInTheDocument()
    expect(screen.getByTestId("persona-test-lab-payload-preview")).toHaveTextContent(
      "\"query\": \"model context protocol\""
    )
  })

  it("surfaces broken connection dependencies for matched commands", async () => {
    const onOpenCommand = vi.fn()

    render(
      <TestLabPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
        onOpenCommand={onOpenCommand}
      />
    )

    fireEvent.change(screen.getByTestId("persona-test-lab-heard-input"), {
      target: { value: "send alert for model drift" }
    })
    fireEvent.click(screen.getByTestId("persona-test-lab-run"))

    expect(await screen.findByTestId("persona-test-lab-match-status")).toHaveTextContent(
      "direct command"
    )
    expect(screen.getByText("broken connection")).toBeInTheDocument()
    expect(
      screen.getByText(
        "This command matched, but its saved connection was deleted. Edit the command in Commands to choose a replacement connection."
      )
    ).toBeInTheDocument()
    expect(screen.getByText("Connection missing: conn-missing")).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("persona-test-lab-open-command"))
    expect(onOpenCommand).toHaveBeenCalledWith(
      "cmd-alert",
      "send alert for model drift"
    )
  })

  it("offers a create-command handoff when no direct command matches", async () => {
    const onCreateCommandDraft = vi.fn()

    render(
      <TestLabPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
        onCreateCommandDraft={onCreateCommandDraft}
        analytics={analytics}
      />
    )

    fireEvent.change(screen.getByTestId("persona-test-lab-heard-input"), {
      target: { value: "start a focused research sprint" }
    })
    fireEvent.click(screen.getByTestId("persona-test-lab-run"))

    expect(await screen.findByTestId("persona-test-lab-match-status")).toHaveTextContent(
      "persona fallback"
    )
    expect(
      screen.getByText(
        "No direct command matched. Open this phrase in Commands to register it as a saved shortcut and add placeholders if needed."
      )
    ).toBeInTheDocument()
    expect(screen.getByTestId("persona-test-lab-fallback-health")).toHaveTextContent(
      "2 planner fallbacks"
    )

    fireEvent.click(screen.getByTestId("persona-test-lab-create-command"))
    expect(onCreateCommandDraft).toHaveBeenCalledWith(
      "start a focused research sprint"
    )
  })

  it("reports unmatched dry-runs through the completion callback without treating them as success", async () => {
    const onDryRunCompleted = vi.fn()

    render(
      <TestLabPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
        onDryRunCompleted={onDryRunCompleted}
      />
    )

    fireEvent.change(screen.getByTestId("persona-test-lab-heard-input"), {
      target: { value: "start a focused research sprint" }
    })
    fireEvent.click(screen.getByTestId("persona-test-lab-run"))

    await screen.findByTestId("persona-test-lab-match-status")

    expect(onDryRunCompleted).toHaveBeenCalledWith({ matched: false })
  })

  it("shows recent health for the matched command from live analytics", async () => {
    render(
      <TestLabPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
        analytics={analytics}
      />
    )

    fireEvent.change(screen.getByTestId("persona-test-lab-heard-input"), {
      target: { value: "send alert repaired" }
    })
    fireEvent.click(screen.getByTestId("persona-test-lab-run"))

    expect(await screen.findByTestId("persona-test-lab-match-status")).toHaveTextContent(
      "direct command"
    )
    expect(screen.getByTestId("persona-test-lab-command-health")).toHaveTextContent(
      "6 runs"
    )
    expect(screen.getByTestId("persona-test-lab-command-health")).toHaveTextContent(
      "2 failures"
    )
  })

  it("reruns the last phrase automatically when requested by the route", async () => {
    const onOpenCommand = vi.fn()

    render(
      <TestLabPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
        initialHeardText="send alert repaired"
        rerunRequestToken={1}
        onOpenCommand={onOpenCommand}
      />
    )

    expect(screen.getByText("Rerunning last phrase...")).toBeInTheDocument()
    await waitFor(() =>
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
        "/api/v1/persona/profiles/persona-1/voice-commands/test",
        expect.objectContaining({
          method: "POST",
          body: { heard_text: "send alert repaired" }
        })
      )
    )
    expect(mocks.fetchWithAuth).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId("persona-test-lab-heard-input")).toHaveValue(
      "send alert repaired"
    )
    await waitFor(() =>
      expect(
        screen.queryByText("Rerunning last phrase...")
      ).not.toBeInTheDocument()
    )
    expect(
      screen.getByText("Repair confirmed. The last phrase now resolves cleanly.")
    ).toBeInTheDocument()
    fireEvent.click(screen.getByTestId("persona-test-lab-repair-open-command"))
    expect(onOpenCommand).toHaveBeenCalledWith(
      "cmd-alert",
      "send alert repaired"
    )
  })

  it("does not rerun again when the heard text changes after a rerun token is handled", async () => {
    const view = render(
      <TestLabPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
        rerunRequestToken={0}
      />
    )

    fireEvent.change(screen.getByTestId("persona-test-lab-heard-input"), {
      target: { value: "send alert repaired" }
    })

    view.rerender(
      <TestLabPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
        rerunRequestToken={1}
      />
    )

    await waitFor(() => {
      expect(mocks.fetchWithAuth).toHaveBeenCalledTimes(1)
    })

    fireEvent.change(screen.getByTestId("persona-test-lab-heard-input"), {
      target: { value: "send alert repaired again" }
    })

    await waitFor(() => {
      expect(mocks.fetchWithAuth).toHaveBeenCalledTimes(1)
    })
  })

  it("focuses the dry-run form for setup handoff requests", async () => {
    const onSetupHandoffFocusConsumed = vi.fn()

    render(
      <TestLabPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
        handoffFocusRequest={{ section: "dry_run_form", token: 1 }}
        onSetupHandoffFocusConsumed={onSetupHandoffFocusConsumed}
      />
    )

    await waitFor(() =>
      expect(screen.getByTestId("persona-test-lab-heard-input")).toHaveFocus()
    )
    expect(onSetupHandoffFocusConsumed).toHaveBeenCalledWith(1)
  })
})
