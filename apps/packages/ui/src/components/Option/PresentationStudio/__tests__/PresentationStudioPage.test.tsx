import React from "react"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { PresentationStudioPage } from "../PresentationStudioPage"
import { usePresentationStudioStore } from "@/store/presentation-studio"

const onlineMocks = vi.hoisted(() => ({
  useServerOnline: vi.fn()
}))

const capabilityMocks = vi.hoisted(() => ({
  useServerCapabilities: vi.fn()
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => onlineMocks.useServerOnline()
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => capabilityMocks.useServerCapabilities()
}))

describe("PresentationStudioPage", () => {
  beforeEach(() => {
    usePresentationStudioStore.getState().reset()
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

  it("renders the three-pane editor shell for a blank project", () => {
    render(<PresentationStudioPage mode="new" />)

    expect(screen.getByTestId("presentation-studio-slide-rail")).toBeInTheDocument()
    expect(screen.getByTestId("presentation-studio-slide-editor")).toBeInTheDocument()
    expect(screen.getByTestId("presentation-studio-media-rail")).toBeInTheDocument()
  })
})
