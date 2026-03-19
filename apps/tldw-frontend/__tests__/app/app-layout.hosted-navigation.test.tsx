import React from "react"
import { afterAll, beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"

import App from "@web/pages/_app"

const mockRouter = {
  pathname: "/settings/tldw",
  asPath: "/settings/tldw",
  push: vi.fn(),
  replace: vi.fn(),
  prefetch: vi.fn(() => Promise.resolve(true))
}

const mockGetConfig = vi.fn()
const mockGetCurrentUser = vi.fn()
let currentConfig: Record<string, unknown> | null = null

vi.mock("next/router", () => ({
  useRouter: () => mockRouter
}))

vi.mock("next/dynamic", () => ({
  default: () =>
    ({
      children
    }: {
      children: React.ReactNode
    }) => <div data-testid="option-layout">{children}</div>
}))

vi.mock("@web/components/AppProviders", () => ({
  AppProviders: ({ children }: { children: React.ReactNode }) => <>{children}</>
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getConfig: (...args: unknown[]) => mockGetConfig(...args)
  }
}))

vi.mock("@/services/tldw/TldwAuth", () => ({
  tldwAuth: {
    getCurrentUser: (...args: unknown[]) => mockGetCurrentUser(...args)
  }
}))

const DummyPage = () => <div data-testid="page-content">Page</div>

const renderApp = (pathname: string) => {
  mockRouter.pathname = pathname
  mockRouter.asPath = pathname
  return render(<App Component={DummyPage} pageProps={{}} />)
}

const originalDeploymentMode = process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE

describe("App hosted navigation gating", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "hosted"
    currentConfig = {
      serverUrl: "",
      authMode: "multi-user"
    }
    mockGetConfig.mockImplementation(async () => currentConfig)
    mockGetCurrentUser.mockResolvedValue({ username: "hosted-user" })
  })

  it("redirects disallowed hosted routes back to the landing page", async () => {
    renderApp("/settings/tldw")

    await waitFor(() => {
      expect(mockRouter.replace).toHaveBeenCalledWith("/")
    })
  })

  it("keeps allowed hosted routes accessible", async () => {
    renderApp("/account")

    expect(await screen.findByTestId("option-layout")).toBeInTheDocument()
    await waitFor(() => {
      expect(mockGetCurrentUser).toHaveBeenCalled()
    })
    expect(mockRouter.replace).not.toHaveBeenCalled()
  })
})

afterAll(() => {
  process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = originalDeploymentMode
})
