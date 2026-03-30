import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import AgentTasksPage from "../index"

const storageMocks = vi.hoisted(() => ({
  useStorage: vi.fn()
}))

const configMocks = vi.hoisted(() => ({
  getConfig: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key
  })
}))

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (...args: unknown[]) => storageMocks.useStorage(...args)
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getConfig: (...args: unknown[]) => configMocks.getConfig(...args)
  }
}))

vi.mock("antd", () => {
  const formApi = {
    resetFields: vi.fn(),
    getFieldValue: vi.fn()
  }
  const Form = Object.assign(
    ({ children }: { children?: React.ReactNode }) => <form>{children}</form>,
    {
      useForm: () => [formApi],
      Item: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>
    }
  )

  return {
    Alert: ({
      message,
      description
    }: {
      message?: React.ReactNode
      description?: React.ReactNode
    }) => (
      <div>
        <div>{message}</div>
        {description ? <div>{description}</div> : null}
      </div>
    ),
    Badge: ({ count }: { count?: React.ReactNode }) => <span>{count}</span>,
    Button: ({
      children,
      onClick,
      disabled
    }: {
      children?: React.ReactNode
      onClick?: (event?: React.MouseEvent<HTMLButtonElement>) => void
      disabled?: boolean
    }) => (
      <button type="button" disabled={disabled} onClick={onClick}>
        {children}
      </button>
    ),
    Card: ({
      title,
      extra,
      children
    }: {
      title?: React.ReactNode
      extra?: React.ReactNode
      children?: React.ReactNode
    }) => (
      <section>
        {title}
        {extra}
        {children}
      </section>
    ),
    Collapse: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
    Empty: ({
      description,
      children
    }: {
      description?: React.ReactNode
      children?: React.ReactNode
    }) => (
      <div>
        <div>{description}</div>
        {children}
      </div>
    ),
    Form,
    Input: Object.assign(() => <input />, {
      TextArea: () => <textarea />
    }),
    Modal: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
    Select: () => <select aria-label="select" />,
    Spin: () => <div>Loading...</div>,
    Tag: ({ children }: { children?: React.ReactNode }) => <span>{children}</span>,
    Tooltip: ({ children }: { children?: React.ReactNode }) => <>{children}</>
  }
})

describe("AgentTasksPage connection and payload normalization", () => {
  beforeEach(() => {
    vi.clearAllMocks()

    storageMocks.useStorage.mockImplementation((key: string, fallback: string) => {
      if (key === "serverUrl") return ["http://localhost:8000", vi.fn()]
      if (key === "authMode") return ["single-user", vi.fn()]
      if (key === "apiKey") return ["", vi.fn()]
      if (key === "accessToken") return ["", vi.fn()]
      return [fallback, vi.fn()]
    })

    configMocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "real-key",
      accessToken: ""
    })

    let callCount = 0
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        callCount += 1
        const url = String(input)

        if (callCount === 1) {
          expect(url).toBe("http://127.0.0.1:8000/openapi.json")
          return {
            ok: true,
            json: async () => ({
              paths: {
                "/api/v1/agent-orchestration/projects": {},
              }
            })
          }
        }

        if (callCount === 2) {
          expect(url).toBe("http://127.0.0.1:8000/api/v1/agent-orchestration/projects")
          expect((init?.headers as Record<string, string>)?.["X-API-KEY"]).toBe("real-key")
          return {
            ok: true,
            json: async () => [
              {
                id: 7,
                name: "Research Project",
                user_id: 1,
                created_at: "2026-03-20T19:00:00Z",
                task_summary: {
                  total_tasks: 1,
                  status_counts: {
                    todo: 1
                  }
                }
              }
            ]
          }
        }

        expect(url).toBe(
          "http://127.0.0.1:8000/api/v1/agent-orchestration/projects/7/tasks"
        )
        expect((init?.headers as Record<string, string>)?.["X-API-KEY"]).toBe("real-key")
        return {
          ok: true,
          json: async () => [
            {
              id: 11,
              project_id: 7,
              title: "Draft spec",
              status: "todo",
              review_count: 0,
              max_review_attempts: 3,
              created_at: "2026-03-20T19:00:00Z",
              updated_at: "2026-03-20T19:00:00Z"
            }
          ]
        }
      })
    )
  })

  it("loads projects and tasks from canonical config-backed requests even when legacy storage is stale", async () => {
    render(<AgentTasksPage />)

    const projectButton = await screen.findByText("Research Project")
    expect(projectButton).toBeInTheDocument()

    fireEvent.click(projectButton)

    expect(await screen.findByText("Draft spec")).toBeInTheDocument()

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(3)
    })
  })

  it("shows an unsupported-state message instead of surfacing raw HTTP 404 when orchestration routes are absent", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 404,
        json: async () => ({
          detail: "Not Found"
        })
      }))
    )

    render(<AgentTasksPage />)

    expect(await screen.findByText("Agent orchestration unavailable")).toBeInTheDocument()
    expect(
      screen.getByText("This server does not expose agent orchestration endpoints.")
    ).toBeInTheDocument()
    expect(screen.queryByText("HTTP 404")).toBeNull()
  })

  it("uses the OpenAPI spec to suppress project probes when orchestration routes are absent", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url === "http://127.0.0.1:8000/openapi.json") {
        return {
          ok: true,
          json: async () => ({
            paths: {
              "/api/v1/health": {}
            }
          })
        }
      }
      throw new Error(`unexpected fetch: ${url}`)
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<AgentTasksPage />)

    expect(await screen.findByText("Agent orchestration unavailable")).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/openapi.json"
    )
  })
})
