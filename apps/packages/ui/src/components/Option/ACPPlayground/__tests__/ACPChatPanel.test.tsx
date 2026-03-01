import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ACPChatPanel } from "../ACPChatPanel"
import { useACPSessionsStore } from "@/store/acp-sessions"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string },
      maybeOptions?: Record<string, unknown>
    ) => {
      if (typeof fallbackOrOptions === "string") {
        return fallbackOrOptions
      }
      if (
        fallbackOrOptions &&
        typeof fallbackOrOptions === "object" &&
        typeof fallbackOrOptions.defaultValue === "string"
      ) {
        return fallbackOrOptions.defaultValue
      }
      return maybeOptions?.defaultValue || key
    },
  }),
}))

describe("ACPChatPanel", () => {
  beforeEach(() => {
    useACPSessionsStore.getState().reset()
  })

  it("shows empty state when no session is active", () => {
    render(
      <ACPChatPanel
        state="disconnected"
        isConnected={false}
        updates={[]}
        connect={vi.fn().mockResolvedValue(undefined)}
        sendPrompt={vi.fn()}
        cancel={vi.fn()}
      />
    )

    expect(screen.getByText("Select or create a session to start")).toBeInTheDocument()
  })

  it("offers reconnect action and renders runtime error text", async () => {
    useACPSessionsStore.getState().createSession({ cwd: "/tmp/project" })
    const connect = vi.fn().mockResolvedValue(undefined)

    render(
      <ACPChatPanel
        state="disconnected"
        isConnected={false}
        updates={[]}
        connect={connect}
        sendPrompt={vi.fn()}
        cancel={vi.fn()}
        error="WebSocket connection error"
      />
    )

    expect(screen.getByText("Not connected to session")).toBeInTheDocument()
    expect(screen.getByText("WebSocket connection error")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Reconnect" }))
    await waitFor(() => {
      expect(connect).toHaveBeenCalledTimes(1)
    })
  })

  it("submits prompt on Enter when connected", () => {
    useACPSessionsStore.getState().createSession({ cwd: "/tmp/project" })
    const sendPrompt = vi.fn()

    render(
      <ACPChatPanel
        state="connected"
        isConnected={true}
        updates={[]}
        connect={vi.fn().mockResolvedValue(undefined)}
        sendPrompt={sendPrompt}
        cancel={vi.fn()}
      />
    )

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Hello ACP" } })
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter", code: "Enter" })

    expect(sendPrompt).toHaveBeenCalledWith([{ role: "user", content: "Hello ACP" }])
  })
})
