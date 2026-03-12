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

import { ConnectionsPanel } from "../ConnectionsPanel"

describe("ConnectionsPanel", () => {
  beforeEach(() => {
    mocks.fetchWithAuth.mockReset()
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
      if (
        path === "/api/v1/persona/profiles/persona-1/connections" &&
        (!init?.method || init.method === "GET")
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => [
            {
              id: "conn-existing",
              persona_id: "persona-1",
              name: "Existing API",
              base_url: "https://existing.example.com",
              auth_type: "bearer",
              allowed_hosts: ["existing.example.com"],
              secret_configured: true,
              key_hint: "***1234"
            }
          ]
        })
      }
      if (
        path === "/api/v1/persona/profiles/persona-1/connections" &&
        init?.method === "POST"
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "conn-new",
            persona_id: "persona-1",
            name: init.body.name,
            base_url: init.body.base_url,
            auth_type: init.body.auth_type,
            allowed_hosts: ["api.example.com"],
            secret_configured: Boolean(init.body.secret),
            key_hint: "***9876"
          })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `Unhandled path: ${path}`
      })
    })
  })

  it("lists saved connections and creates a new connection", async () => {
    render(
      <ConnectionsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
      />
    )

    expect(await screen.findByText("Existing API")).toBeInTheDocument()
    fireEvent.change(screen.getByTestId("persona-connections-name-input"), {
      target: { value: "Slack Alerts" }
    })
    fireEvent.change(screen.getByTestId("persona-connections-base-url-input"), {
      target: { value: "https://api.example.com/hooks" }
    })
    fireEvent.change(screen.getByTestId("persona-connections-auth-type-select"), {
      target: { value: "bearer" }
    })
    fireEvent.change(screen.getByTestId("persona-connections-secret-input"), {
      target: { value: "top-secret-token" }
    })
    fireEvent.click(screen.getByTestId("persona-connections-save"))

    await waitFor(() =>
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
        "/api/v1/persona/profiles/persona-1/connections",
        expect.objectContaining({
          method: "POST",
          body: expect.objectContaining({
            name: "Slack Alerts",
            base_url: "https://api.example.com/hooks",
            auth_type: "bearer",
            secret: "top-secret-token"
          })
        })
      )
    )
    expect(await screen.findByText("Slack Alerts")).toBeInTheDocument()
  })
})
