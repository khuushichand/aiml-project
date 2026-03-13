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

  it("shows stale audio and ready image badges for seeded slide media state", () => {
    usePresentationStudioStore.getState().loadProject(
      {
        id: "presentation-1",
        title: "Seeded deck",
        description: null,
        theme: "black",
        slides: [
          {
            order: 0,
            layout: "content",
            title: "Opening",
            content: "",
            speaker_notes: "Narration seed",
            metadata: {
              studio: {
                slideId: "slide-1",
                audio: { status: "stale" },
                image: { status: "ready", asset_ref: "output:123" }
              }
            }
          }
        ],
        studio_data: { origin: "extension_capture" },
        created_at: "2026-03-13T00:00:00Z",
        last_modified: "2026-03-13T00:00:00Z",
        deleted: false,
        client_id: "1",
        version: 2
      },
      { etag: 'W/"v2"' }
    )

    render(<PresentationStudioPage mode="detail" projectId="presentation-1" />)

    expect(screen.getByText("Audio status")).toBeInTheDocument()
    expect(screen.getByText("stale")).toBeInTheDocument()
    expect(screen.getByText("Image status")).toBeInTheDocument()
    expect(screen.getByText("ready")).toBeInTheDocument()
  })
})
