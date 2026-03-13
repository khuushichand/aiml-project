import React from "react"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import OptionPresentationStudio from "../option-presentation-studio"

const onlineMocks = vi.hoisted(() => ({
  useServerOnline: vi.fn()
}))

const capabilityMocks = vi.hoisted(() => ({
  useServerCapabilities: vi.fn()
}))

vi.mock("@/components/Layouts/Layout", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="option-layout">{children}</div>
  )
}))

vi.mock("@/components/Common/RouteErrorBoundary", () => ({
  RouteErrorBoundary: ({
    routeId,
    children
  }: {
    routeId: string
    children: React.ReactNode
  }) => <div data-testid={`route-boundary-${routeId}`}>{children}</div>
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => onlineMocks.useServerOnline()
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => capabilityMocks.useServerCapabilities()
}))

describe("presentation studio option route guards", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    onlineMocks.useServerOnline.mockReturnValue(true)
    capabilityMocks.useServerCapabilities.mockReturnValue({
      loading: false,
      capabilities: {
        hasSlides: true,
        hasPresentationStudio: true,
        hasPresentationRender: true
      }
    })
  })

  it("blocks the route when presentation studio is unsupported", () => {
    capabilityMocks.useServerCapabilities.mockReturnValue({
      loading: false,
      capabilities: {
        hasSlides: true,
        hasPresentationStudio: false,
        hasPresentationRender: false
      }
    })

    render(
      <MemoryRouter>
        <OptionPresentationStudio />
      </MemoryRouter>
    )

    expect(
      screen.getByText("Presentation Studio is not available on this server.")
    ).toBeInTheDocument()
  })

  it("renders the editor shell when presentation studio is supported", () => {
    render(
      <MemoryRouter>
        <OptionPresentationStudio />
      </MemoryRouter>
    )

    expect(screen.getByTestId("route-boundary-presentation-studio")).toBeVisible()
    expect(screen.getByText("Presentation Studio")).toBeInTheDocument()
  })
})
