import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import OptionMediaMulti from "../option-media-multi"
import OptionMediaTrash from "../option-media-trash"

vi.mock("~/components/Layouts/Layout", () => ({
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

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      _key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      return defaultValueOrOptions?.defaultValue ?? ""
    }
  })
}))

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn()
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    loading: false,
    capabilities: {
      hasMedia: true
    }
  })
}))

vi.mock("@/context/demo-mode", () => ({
  useDemoMode: () => ({
    demoEnabled: false
  })
}))

vi.mock("@/components/Common/FeatureEmptyState", () => ({
  __esModule: true,
  default: () => <div data-testid="feature-empty-state" />
}))

vi.mock("@/components/Review/MediaReviewPage", () => ({
  __esModule: true,
  default: () => <div data-testid="media-review-page">Media review</div>
}))

vi.mock("@/components/Review/MediaTrashPage", () => ({
  __esModule: true,
  default: () => <div data-testid="media-trash-page">Media trash</div>
}))

describe("media option route guards", () => {
  it("wraps /media-multi route with route error boundary", () => {
    render(<OptionMediaMulti />)
    expect(screen.getByTestId("route-boundary-media-multi")).toBeVisible()
    expect(screen.getByTestId("media-review-page")).toBeVisible()
  })

  it("wraps /media-trash route with route error boundary", () => {
    render(<OptionMediaTrash />)
    expect(screen.getByTestId("route-boundary-media-trash")).toBeVisible()
    expect(screen.getByTestId("media-trash-page")).toBeVisible()
  })
})
