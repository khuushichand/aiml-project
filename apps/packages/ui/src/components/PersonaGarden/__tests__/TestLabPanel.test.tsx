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

describe("TestLabPanel", () => {
  beforeEach(() => {
    mocks.fetchWithAuth.mockReset()
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
      if (
        path === "/api/v1/persona/profiles/persona-1/voice-commands/test" &&
        init?.method === "POST"
      ) {
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
})
