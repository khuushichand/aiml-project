import React from "react"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  integrationPage: vi.fn(),
  adminIntegrationPage: vi.fn()
}))

vi.mock("@/components/Layouts/Layout", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="option-layout">{children}</div>
  )
}))

vi.mock("@/components/Common/RouteErrorBoundary", () => ({
  RouteErrorBoundary: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="route-error-boundary">{children}</div>
  )
}))

vi.mock("@/components/Option/Integrations/IntegrationManagementPage", () => ({
  IntegrationManagementPage: ({ scope }: { scope: string }) => {
    mocks.integrationPage(scope)
    return <div data-testid="integration-management-page" data-scope={scope} />
  }
}))

import OptionIntegrations from "../option-integrations"
import OptionAdminIntegrations from "../option-admin-integrations"

describe("integration routes", () => {
  beforeEach(() => {
    mocks.integrationPage.mockReset()
    mocks.adminIntegrationPage.mockReset()
  })

  it("renders the personal integrations page in the shared option layout", () => {
    render(<OptionIntegrations />)

    expect(screen.getByTestId("option-layout")).toBeInTheDocument()
    expect(screen.getByTestId("integration-management-page")).toHaveAttribute("data-scope", "personal")
  })

  it("renders the admin integrations page in the route error boundary", () => {
    render(<OptionAdminIntegrations />)

    expect(screen.getByTestId("route-error-boundary")).toBeInTheDocument()
    expect(screen.getByTestId("option-layout")).toBeInTheDocument()
    expect(screen.getByTestId("integration-management-page")).toHaveAttribute("data-scope", "workspace")
  })
})
