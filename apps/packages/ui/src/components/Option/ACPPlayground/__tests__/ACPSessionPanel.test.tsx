import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ACPSessionPanel } from "../ACPSessionPanel"
import { useACPSessionsStore } from "@/store/acp-sessions"

const { useStorageMock } = vi.hoisted(() => ({
  useStorageMock: vi.fn(),
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string }
    ) => {
      if (typeof fallbackOrOptions === "string") {
        return fallbackOrOptions
      }
      if (fallbackOrOptions?.defaultValue) {
        return fallbackOrOptions.defaultValue
      }
      return key
    },
  }),
}))

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: useStorageMock,
}))

vi.mock("../ACPSessionCreateModal", () => ({
  ACPSessionCreateModal: () => null,
}))

describe("ACPSessionPanel filters and sorting", () => {
  beforeEach(() => {
    useACPSessionsStore.getState().reset()
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) }))

    const clipboard = {
      writeText: vi.fn().mockResolvedValue(undefined),
    }
    Object.defineProperty(navigator, "clipboard", {
      value: clipboard,
      configurable: true,
      writable: true,
    })

    useStorageMock.mockImplementation((_key: string, defaultValue: unknown) => {
      return [defaultValue, vi.fn(), { isLoading: false }] as const
    })
  })

  const seedSessions = () => {
    const store = useACPSessionsStore.getState()
    const alphaId = store.createSession({ cwd: "/workspace/alpha", name: "Alpha Session" })
    const betaId = store.createSession({ cwd: "/workspace/beta", name: "Beta Session" })
    const gammaId = store.createSession({ cwd: "/workspace/gamma", name: "Gamma Session" })

    useACPSessionsStore.setState((state) => ({
      sessions: {
        ...state.sessions,
        [alphaId]: {
          ...state.sessions[alphaId],
          state: "error",
          updatedAt: new Date("2024-01-01T00:00:00.000Z"),
        },
        [betaId]: {
          ...state.sessions[betaId],
          state: "running",
          updatedAt: new Date("2024-01-03T00:00:00.000Z"),
        },
        [gammaId]: {
          ...state.sessions[gammaId],
          state: "error",
          updatedAt: new Date("2024-01-02T00:00:00.000Z"),
        },
      },
    }))

    return { alphaId, betaId, gammaId }
  }

  it("filters sessions by search text", () => {
    seedSessions()
    render(<ACPSessionPanel />)

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "beta" } })

    expect(screen.getByText("Beta Session")).toBeInTheDocument()
    expect(screen.queryByText("Alpha Session")).toBeNull()
    expect(screen.queryByText("Gamma Session")).toBeNull()
  })

  it("filters by state and sorts by name", () => {
    const { alphaId, gammaId } = seedSessions()
    render(<ACPSessionPanel />)

    fireEvent.change(screen.getByTestId("acp-session-filter-state"), { target: { value: "error" } })
    fireEvent.change(screen.getByTestId("acp-session-sort"), { target: { value: "name_asc" } })

    const sessionIdsInOrder = screen
      .getAllByTestId("acp-session-item")
      .map((item) => item.getAttribute("data-session-id"))

    expect(sessionIdsInOrder).toEqual([alphaId, gammaId])
  })

  it("shows empty filtered state and clears filters", () => {
    seedSessions()
    render(<ACPSessionPanel />)

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "does-not-exist" } })

    expect(screen.getByText("No sessions match the current filters")).toBeInTheDocument()

    fireEvent.click(screen.getAllByRole("button", { name: "Clear" })[0])

    expect(screen.getByText("Alpha Session")).toBeInTheDocument()
    expect(screen.getByText("Beta Session")).toBeInTheDocument()
    expect(screen.getByText("Gamma Session")).toBeInTheDocument()
  })

  it("renders session metadata counters with token fallback", () => {
    const { alphaId, betaId } = seedSessions()

    useACPSessionsStore.setState((state) => ({
      sessions: {
        ...state.sessions,
        [alphaId]: {
          ...state.sessions[alphaId],
          updates: [
            { timestamp: new Date("2024-01-01T00:00:00.000Z"), type: "user_text", data: { text: "hi" } },
            {
              timestamp: new Date("2024-01-01T00:00:01.000Z"),
              type: "assistant_text",
              data: { text: "hello", total_tokens: 42 },
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
        [betaId]: {
          ...state.sessions[betaId],
          updates: [],
          pendingPermissions: [],
        },
      },
    }))

    render(<ACPSessionPanel />)

    expect(screen.getByText("Msgs 2")).toBeInTheDocument()
    expect(screen.getByText("Tokens 42")).toBeInTheDocument()
    expect(screen.getByText("Perm 1")).toBeInTheDocument()
    expect(screen.getAllByText("Tokens --").length).toBeGreaterThan(0)
  })

  it("copies session id from quick action", async () => {
    const { alphaId } = seedSessions()
    render(<ACPSessionPanel />)

    fireEvent.click(screen.getByTestId(`acp-session-copy-${alphaId}`))

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(alphaId)
    })
  })

  it("calls backend fork with message_index from session detail", async () => {
    const store = useACPSessionsStore.getState()
    const alphaId = store.createSession({ cwd: "/workspace/alpha", name: "Alpha Session" })

    let forkRequestBody: Record<string, unknown> | null = null

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
        const urlString = String(url)

        if (urlString.includes(`/api/v1/acp/sessions/${alphaId}/detail`)) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              session_id: alphaId,
              user_id: 1,
              agent_type: "custom",
              name: "Alpha Session",
              status: "active",
              created_at: "2024-01-01T00:00:00.000Z",
              last_activity_at: "2024-01-01T00:00:05.000Z",
              message_count: 3,
              usage: { prompt_tokens: 10, completion_tokens: 20, total_tokens: 30 },
              tags: [],
              has_websocket: false,
              messages: [{ id: 1 }, { id: 2 }, { id: 3 }],
              cwd: "/workspace/alpha",
            }),
          })
        }

        if (urlString.includes(`/api/v1/acp/sessions/${alphaId}/fork`)) {
          forkRequestBody = JSON.parse(String(init?.body || "{}"))
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              session_id: "fork-session-1",
              name: "Alpha Session (fork)",
              forked_from: alphaId,
              message_count: 3,
            }),
          })
        }

        if (urlString.includes("/api/v1/acp/sessions/fork-session-1/usage")) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              session_id: "fork-session-1",
              user_id: 1,
              agent_type: "custom",
              usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
              message_count: 3,
              created_at: "2024-01-01T00:00:00.000Z",
              last_activity_at: "2024-01-01T00:00:06.000Z",
            }),
          })
        }

        return Promise.resolve({ ok: true, status: 200, json: async () => ({}) })
      })
    )

    render(<ACPSessionPanel />)

    fireEvent.click(screen.getByTestId(`acp-session-fork-${alphaId}`))

    await waitFor(() => {
      expect(screen.getByText("Alpha Session (fork)")).toBeInTheDocument()
    })

    expect(forkRequestBody).toMatchObject({ message_index: 2 })
  })

  it("falls back to local fork when backend fork endpoint is unavailable", async () => {
    const store = useACPSessionsStore.getState()
    const alphaId = store.createSession({ cwd: "/workspace/alpha", name: "Alpha Session" })

    useACPSessionsStore.setState((state) => ({
      sessions: {
        ...state.sessions,
        [alphaId]: {
          ...state.sessions[alphaId],
          updates: [
            { timestamp: new Date("2024-01-01T00:00:00.000Z"), type: "user_text", data: { text: "seed" } },
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
    }))

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: RequestInfo | URL) => {
        const urlString = String(url)
        if (urlString.includes("/fork")) {
          return Promise.resolve({ ok: false, status: 404, json: async () => ({}) })
        }
        return Promise.resolve({ ok: true, status: 200, json: async () => ({}) })
      })
    )

    render(<ACPSessionPanel />)

    fireEvent.click(screen.getByTestId(`acp-session-fork-${alphaId}`))

    await waitFor(() => {
      expect(screen.getByText("Alpha Session (fork)")).toBeInTheDocument()
    })

    expect(screen.getAllByTestId("acp-session-item").length).toBe(2)
    expect(screen.getAllByText("Msgs 1").length).toBeGreaterThan(1)
    expect(screen.getAllByText("Perm 0").length).toBeGreaterThan(0)
    expect(screen.getByText(`Fork ${alphaId.slice(0, 8)}`)).toBeInTheDocument()
  })

  it("does not silently local-fork server-backed sessions when the backend fork fails", async () => {
    const store = useACPSessionsStore.getState()
    const alphaId = store.createSession({ cwd: "/workspace/alpha", name: "Alpha Session" })

    useACPSessionsStore.setState((state) => ({
      sessions: {
        ...state.sessions,
        [alphaId]: {
          ...state.sessions[alphaId],
          backendStatus: "active",
        },
      },
    }))

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: RequestInfo | URL) => {
        const urlString = String(url)
        if (urlString.includes(`/api/v1/acp/sessions/${alphaId}/detail`)) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              session_id: alphaId,
              user_id: 1,
              agent_type: "custom",
              name: "Alpha Session",
              status: "active",
              created_at: "2024-01-01T00:00:00.000Z",
              last_activity_at: "2024-01-01T00:00:05.000Z",
              message_count: 2,
              usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
              tags: [],
              has_websocket: false,
              forked_from: null,
              messages: [{ id: 1 }, { id: 2 }],
              cwd: "/workspace/alpha",
            }),
          })
        }
        if (urlString.includes(`/api/v1/acp/sessions/${alphaId}/fork`)) {
          return Promise.resolve({
            ok: false,
            status: 409,
            json: async () => ({ detail: "fork_not_resumable" }),
          })
        }
        return Promise.resolve({ ok: true, status: 200, json: async () => ({}) })
      })
    )

    render(<ACPSessionPanel />)

    fireEvent.click(screen.getByTestId(`acp-session-fork-${alphaId}`))

    await waitFor(() => {
      expect(useACPSessionsStore.getState().globalError).toBe("fork_not_resumable")
    })

    expect(useACPSessionsStore.getState().getSessions()).toHaveLength(1)
    expect(screen.queryByText("Alpha Session (fork)")).toBeNull()
  })
})
