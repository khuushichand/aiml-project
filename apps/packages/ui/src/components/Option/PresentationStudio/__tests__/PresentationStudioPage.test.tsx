import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
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
  createPresentation: vi.fn(),
  getPresentation: vi.fn()
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
    createPresentation: (...args: unknown[]) => clientMocks.createPresentation(...args),
    getPresentation: (...args: unknown[]) => clientMocks.getPresentation(...args)
  }
}))

describe("PresentationStudioPage", () => {
  beforeEach(() => {
    usePresentationStudioStore.getState().reset()
    routerMocks.navigate.mockReset()
    clientMocks.createPresentation.mockReset()
    clientMocks.getPresentation.mockReset()
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

  it("creates a blank project and redirects to its detail route in new mode", async () => {
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
        title: "Untitled Presentation",
        theme: "black",
        studio_data: { origin: "blank", entry_surface: "webui_new" }
      })
    )
    expect(routerMocks.navigate).toHaveBeenCalledWith("/presentation-studio/presentation-1", {
      replace: true
    })
    expect(usePresentationStudioStore.getState().projectId).toBe("presentation-1")
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
