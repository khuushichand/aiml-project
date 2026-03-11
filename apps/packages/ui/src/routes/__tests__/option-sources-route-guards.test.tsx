import React from "react"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import OptionSourcesNew from "../option-sources-new"
import OptionSourcesDetail from "../option-sources-detail"

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

vi.mock("@/components/Option/Sources/SourceForm", () => ({
  SourceForm: ({ mode }: { mode: string }) => <div data-testid={`source-form-${mode}`} />
}))

vi.mock("@/components/Option/Sources/SourceDetailPage", () => ({
  SourceDetailPage: ({ sourceId }: { sourceId: string }) => (
    <div data-testid="source-detail-page">{sourceId}</div>
  )
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        return fallbackOrOptions.defaultValue || key
      }
      return key
    }
  })
}))

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom")
  return {
    ...actual,
    useParams: () => ({ sourceId: "42" })
  }
})

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => onlineMocks.useServerOnline()
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => capabilityMocks.useServerCapabilities()
}))

describe("sources option route guards", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    onlineMocks.useServerOnline.mockReturnValue(true)
    capabilityMocks.useServerCapabilities.mockReturnValue({
      loading: false,
      capabilities: { hasIngestionSources: true }
    })
  })

  it("blocks the new route with an offline state when the server is unavailable", () => {
    onlineMocks.useServerOnline.mockReturnValue(false)

    render(<OptionSourcesNew />)

    expect(
      screen.getByText("Server is offline. Connect to manage ingestion sources.")
    ).toBeInTheDocument()
    expect(screen.queryByTestId("source-form-create")).not.toBeInTheDocument()
  })

  it("blocks the detail route when ingestion sources are unsupported", () => {
    capabilityMocks.useServerCapabilities.mockReturnValue({
      loading: false,
      capabilities: { hasIngestionSources: false }
    })

    render(<OptionSourcesDetail />)

    expect(
      screen.getByText("This server does not advertise ingestion source support.")
    ).toBeInTheDocument()
    expect(screen.queryByTestId("source-detail-page")).not.toBeInTheDocument()
  })

  it("renders the new and detail routes when ingestion sources are supported", () => {
    const { rerender } = render(<OptionSourcesNew />)

    expect(screen.getByTestId("route-boundary-sources-new")).toBeVisible()
    expect(screen.getByTestId("source-form-create")).toBeVisible()

    rerender(<OptionSourcesDetail />)

    expect(screen.getByTestId("route-boundary-sources-detail")).toBeVisible()
    expect(screen.getByTestId("source-detail-page")).toHaveTextContent("42")
  })
})
