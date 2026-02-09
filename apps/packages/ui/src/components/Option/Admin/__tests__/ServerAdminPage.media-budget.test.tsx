import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import ServerAdminPage from "../ServerAdminPage"

const apiMock = vi.hoisted(() => ({
  getConfig: vi.fn(),
  getSystemStats: vi.fn(),
  listAdminUsers: vi.fn(),
  listAdminRoles: vi.fn(),
  getMediaIngestionBudgetDiagnostics: vi.fn()
}))

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
    }
  })
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: apiMock
}))

vi.mock("@/components/Common/PageShell", () => ({
  PageShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>
}))

describe("ServerAdminPage media budget diagnostics", () => {
  beforeEach(() => {
    vi.clearAllMocks()

    if (!window.matchMedia) {
      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: vi.fn().mockImplementation((query: string) => ({
          matches: false,
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn()
        }))
      })
    }

    apiMock.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user"
    })
    apiMock.getSystemStats.mockResolvedValue({
      users: { total: 1, active: 1, admins: 1, verified: 1, new_last_30d: 0 },
      storage: { total_used_mb: 10, total_quota_mb: 100, average_used_mb: 10, max_used_mb: 10 },
      sessions: { active: 1, unique_users: 1 }
    })
    apiMock.listAdminUsers.mockResolvedValue({
      users: [
        {
          id: 11,
          uuid: "user-11",
          username: "admin",
          email: "admin@example.com",
          role: "admin",
          is_active: true,
          is_verified: true,
          created_at: "2026-02-01T00:00:00Z",
          storage_quota_mb: 1024,
          storage_used_mb: 128
        }
      ],
      total: 1,
      page: 1,
      limit: 20,
      pages: 1
    })
    apiMock.listAdminRoles.mockResolvedValue([])
    apiMock.getMediaIngestionBudgetDiagnostics.mockResolvedValue({
      status: "ok",
      entity: "user:11",
      policy_id: "media.default",
      limits: {
        jobs_max_concurrent: 4,
        ingestion_bytes_daily_cap: 4000
      },
      usage: {
        jobs_active: 1,
        jobs_remaining: 3,
        ingestion_bytes_daily_used: 1024,
        ingestion_bytes_daily_remaining: 2976
      },
      retry_after: null
    })
  })

  it("loads and renders media ingestion budget diagnostics for selected user", async () => {
    render(<ServerAdminPage />)

    await waitFor(() => {
      expect(apiMock.getMediaIngestionBudgetDiagnostics).toHaveBeenCalledWith({
        userId: 11,
        policyId: "media.default"
      })
    })

    expect(await screen.findByText("Media ingestion budget")).toBeTruthy()
    expect(await screen.findByText("user:11")).toBeTruthy()
    expect(await screen.findByText("4000")).toBeTruthy()
    expect(await screen.findByText("2976")).toBeTruthy()
  })
})
