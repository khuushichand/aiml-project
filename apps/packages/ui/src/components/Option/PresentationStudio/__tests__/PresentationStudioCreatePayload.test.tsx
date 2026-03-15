import React from "react"
import { render, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { PresentationStudioPage } from "../PresentationStudioPage"
import { usePresentationStudioStore } from "@/store/presentation-studio"

const onlineMocks = vi.hoisted(() => ({
  useServerOnline: vi.fn()
}))

const capabilityMocks = vi.hoisted(() => ({
  useServerCapabilities: vi.fn()
}))

const routerMocks = vi.hoisted(() => ({
  navigate: vi.fn()
}))

const clientMocks = vi.hoisted(() => ({
  createPresentation: vi.fn()
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => onlineMocks.useServerOnline()
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => capabilityMocks.useServerCapabilities()
}))

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom")
  return {
    ...actual,
    useNavigate: () => routerMocks.navigate
  }
})

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    createPresentation: (...args: unknown[]) => clientMocks.createPresentation(...args)
  }
}))

describe("PresentationStudioPage create payload", () => {
  beforeEach(() => {
    usePresentationStudioStore.getState().reset()
    routerMocks.navigate.mockReset()
    clientMocks.createPresentation.mockReset()
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

  it("sends explicit slide timing and transition defaults for new projects", async () => {
    clientMocks.createPresentation.mockResolvedValue({
      id: "presentation-1",
      title: "Untitled Presentation",
      description: null,
      theme: "black",
      slides: [
        {
          order: 0,
          layout: "title",
          title: "Title slide",
          content: "",
          speaker_notes: "",
          metadata: {
            studio: {
              slideId: "slide-1",
              audio: { status: "missing" },
              image: { status: "missing" }
            }
          }
        }
      ],
      studio_data: { origin: "blank" },
      created_at: "2026-03-13T00:00:00Z",
      last_modified: "2026-03-13T00:00:00Z",
      deleted: false,
      client_id: "1",
      version: 1
    })

    render(<PresentationStudioPage mode="new" />)

    await waitFor(() => {
      expect(clientMocks.createPresentation).toHaveBeenCalledTimes(1)
    })

    expect(clientMocks.createPresentation).toHaveBeenCalledWith(
      expect.objectContaining({
        slides: [
          expect.objectContaining({
            metadata: {
              studio: expect.objectContaining({
                transition: "fade",
                timing_mode: "auto",
                manual_duration_ms: null
              })
            }
          })
        ]
      })
    )
  })
})
