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
    let connections = [
      {
        id: "conn-existing",
        persona_id: "persona-1",
        name: "Existing API",
        base_url: "https://existing.example.com",
        auth_type: "bearer",
        headers_template: { "X-Client": "voice-builder" },
        timeout_ms: 12000,
        allowed_hosts: ["existing.example.com"],
        secret_configured: true,
        key_hint: "***1234"
      }
    ]

    mocks.fetchWithAuth.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
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
        path === "/api/v1/persona/profiles/persona-1/connections" &&
        init?.method === "POST"
      ) {
        const saved = {
          id: "conn-new",
          persona_id: "persona-1",
          name: init.body.name,
          base_url: init.body.base_url,
          auth_type: init.body.auth_type,
          headers_template: init.body.headers_template ?? {},
          timeout_ms: init.body.timeout_ms ?? 15000,
          allowed_hosts: ["api.example.com"],
          secret_configured: Boolean(init.body.secret),
          key_hint: "***9876"
        }
        connections = [saved, ...connections]
        return Promise.resolve({
          ok: true,
          json: async () => saved
        })
      }
      if (
        path === "/api/v1/persona/profiles/persona-1/connections/conn-existing" &&
        init?.method === "PUT"
      ) {
        const updated = {
          ...connections[0],
          name: init.body.name,
          base_url: init.body.base_url,
          auth_type: init.body.auth_type,
          headers_template: init.body.headers_template ?? {},
          timeout_ms: init.body.timeout_ms ?? 15000,
          allowed_hosts: ["hooks.example.net"]
        }
        connections = [updated]
        return Promise.resolve({
          ok: true,
          json: async () => updated
        })
      }
      if (
        path === "/api/v1/persona/profiles/persona-1/connections/conn-existing/test" &&
        init?.method === "POST"
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            ok: true,
            connection_id: "conn-existing",
            method: "GET",
            url: "https://existing.example.com",
            request_headers: { Authorization: "[redacted]" },
            request_payload: {},
            timeout_ms: 12000,
            status_code: 200,
            body_preview: { message: "Connection OK" },
            latency_ms: 42
          })
        })
      }
      if (
        path === "/api/v1/persona/profiles/persona-1/connections/conn-existing" &&
        init?.method === "DELETE"
      ) {
        connections = []
        return Promise.resolve({
          ok: true,
          json: async () => ({
            status: "deleted",
            persona_id: "persona-1",
            connection_id: "conn-existing"
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

  it("loads an existing connection into edit mode and saves updates", async () => {
    render(
      <ConnectionsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
      />
    )

    expect(await screen.findByText("Existing API")).toBeInTheDocument()
    fireEvent.click(screen.getByTestId("persona-connections-edit-conn-existing"))

    expect(screen.getByTestId("persona-connections-name-input")).toHaveValue("Existing API")
    expect(screen.getByTestId("persona-connections-base-url-input")).toHaveValue(
      "https://existing.example.com"
    )

    fireEvent.change(screen.getByTestId("persona-connections-name-input"), {
      target: { value: "Updated API" }
    })
    fireEvent.change(screen.getByTestId("persona-connections-base-url-input"), {
      target: { value: "https://hooks.example.net/incoming" }
    })
    fireEvent.change(screen.getByTestId("persona-connections-auth-type-select"), {
      target: { value: "custom_header" }
    })
    fireEvent.click(screen.getByTestId("persona-connections-save"))

    await waitFor(() =>
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
        "/api/v1/persona/profiles/persona-1/connections/conn-existing",
        expect.objectContaining({
          method: "PUT",
          body: expect.objectContaining({
            name: "Updated API",
            base_url: "https://hooks.example.net/incoming",
            auth_type: "custom_header"
          })
        })
      )
    )

    expect(await screen.findByText("Updated API")).toBeInTheDocument()
  })

  it("tests and deletes a saved connection", async () => {
    render(
      <ConnectionsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Garden Helper"
        isActive
      />
    )

    expect(await screen.findByText("Existing API")).toBeInTheDocument()
    fireEvent.click(screen.getByTestId("persona-connections-test-conn-existing"))

    await waitFor(() =>
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
        "/api/v1/persona/profiles/persona-1/connections/conn-existing/test",
        expect.objectContaining({
          method: "POST",
          body: {}
        })
      )
    )

    expect(await screen.findByText("Test passed (200)")).toBeInTheDocument()
    expect(screen.getByText("Connection OK")).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("persona-connections-delete-conn-existing"))

    await waitFor(() =>
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
        "/api/v1/persona/profiles/persona-1/connections/conn-existing",
        expect.objectContaining({
          method: "DELETE"
        })
      )
    )
    expect(await screen.findByTestId("persona-connections-empty")).toBeInTheDocument()
  })
})
