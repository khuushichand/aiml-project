// @vitest-environment jsdom

import React from "react"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  useCanonicalConnectionConfig: vi.fn(),
  getGovernorPolicy: vi.fn(),
  getGovernorCoverage: vi.fn(),
  listAdminRateLimits: vi.fn()
}))

vi.mock("@/hooks/useCanonicalConnectionConfig", () => ({
  useCanonicalConnectionConfig: (...args: unknown[]) => mocks.useCanonicalConnectionConfig(...args)
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getGovernorPolicy: (...args: unknown[]) => mocks.getGovernorPolicy(...args),
    getGovernorCoverage: (...args: unknown[]) => mocks.getGovernorCoverage(...args),
    listAdminRateLimits: (...args: unknown[]) => mocks.listAdminRateLimits(...args)
  }
}))

import RateLimitingPage from "../RateLimitingPage"

const fetchMock = vi.fn()
vi.stubGlobal("fetch", fetchMock)

describe("RateLimitingPage", () => {
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

    mocks.useCanonicalConnectionConfig.mockReturnValue({
      config: {
        serverUrl: "http://127.0.0.1:8000",
        authMode: "single-user",
        apiKey: "test-key"
      },
      loading: false
    })
    mocks.getGovernorPolicy.mockResolvedValue({
      status: "ok",
      store: "file",
      version: 1,
      policies_count: 0
    })
    mocks.getGovernorCoverage.mockResolvedValue({
      protected: [],
      unprotected: [],
      coverage_pct: 100
    })
  })

  it("shows an unsupported-state message without calling admin rate-limits when the route is absent", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        paths: {}
      })
    })

    render(<RateLimitingPage />)

    expect(
      await screen.findByText("Rate limits listing endpoint is not available on this server.")
    ).toBeInTheDocument()
    expect(mocks.listAdminRateLimits).not.toHaveBeenCalled()
  })
})
