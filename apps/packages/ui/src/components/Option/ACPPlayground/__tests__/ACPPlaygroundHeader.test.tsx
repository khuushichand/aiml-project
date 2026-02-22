import React from "react"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ACPPlaygroundHeader } from "../ACPPlaygroundHeader"
import { useACPSessionsStore } from "@/store/acp-sessions"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      _key: string,
      fallbackOrOptions?: string | { defaultValue?: string }
    ) => {
      if (typeof fallbackOrOptions === "string") {
        return fallbackOrOptions
      }
      if (fallbackOrOptions?.defaultValue) {
        return fallbackOrOptions.defaultValue
      }
      return ""
    },
  }),
}))

describe("ACPPlaygroundHeader", () => {
  beforeEach(() => {
    useACPSessionsStore.getState().reset()
  })

  it("shows active session state and metadata counters", () => {
    const sessionId = useACPSessionsStore.getState().createSession({
      cwd: "/workspace/demo",
      name: "Demo Session",
    })

    useACPSessionsStore.setState((state) => ({
      sessions: {
        ...state.sessions,
        [sessionId]: {
          ...state.sessions[sessionId],
          state: "running",
          updates: [
            { timestamp: new Date("2024-01-01T00:00:00.000Z"), type: "user_text", data: { text: "Hi" } },
            {
              timestamp: new Date("2024-01-01T00:00:01.000Z"),
              type: "assistant_text",
              data: { text: "Hello", total_tokens: 128 },
            },
          ],
          pendingPermissions: [
            {
              request_id: "perm-1",
              tool_name: "fs.write",
              tool_arguments: {},
              tier: "batch",
              timeout_seconds: 30,
              requestedAt: new Date("2024-01-01T00:00:02.000Z"),
            },
          ],
        },
      },
      activeSessionId: sessionId,
    }))

    render(
      <ACPPlaygroundHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    expect(screen.getByText("Running")).toBeInTheDocument()
    expect(screen.getByText("Msgs 2")).toBeInTheDocument()
    expect(screen.getByText("Tokens 128")).toBeInTheDocument()
    expect(screen.getByText("Perm 1")).toBeInTheDocument()
  })
})
