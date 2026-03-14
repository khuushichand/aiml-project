import React from "react"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
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
        studio_data: { origin: "blank", entry_surface: "webui_new" },
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
    expect(routerMocks.navigate).toHaveBeenCalledWith("/presentation-studio/presentation-1", {
      replace: true
    })
    expect(usePresentationStudioStore.getState().projectId).toBe("presentation-1")
  })

  it("completes blank project creation in strict mode", async () => {
    let resolveCreate: ((value: any) => void) | null = null
    clientMocks.createPresentation.mockReturnValue(
      new Promise((resolve) => {
        resolveCreate = resolve
      })
    )

    render(
      <React.StrictMode>
        <PresentationStudioPage mode="new" />
      </React.StrictMode>
    )

    await waitFor(() => {
      expect(clientMocks.createPresentation).toHaveBeenCalledTimes(1)
    })

    resolveCreate?.({
      id: "presentation-strict",
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
              slideId: "slide-strict",
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

    await waitFor(() => {
      expect(routerMocks.navigate).toHaveBeenCalledWith(
        "/presentation-studio/presentation-strict",
        {
          replace: true
        }
      )
    })
  })

  it("loads a detail project and leaves the loading state", async () => {
    clientMocks.getPresentation.mockResolvedValue({
      id: "presentation-load",
      title: "Loaded Presentation",
      description: null,
      theme: "black",
      slides: [
        {
          order: 0,
          layout: "title",
          title: "Loaded slide",
          content: "",
          speaker_notes: "",
          metadata: {
            studio: {
              slideId: "slide-load",
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

    render(
      <React.StrictMode>
        <PresentationStudioPage mode="detail" projectId="presentation-load" />
      </React.StrictMode>
    )

    expect(screen.getByText("Loading presentation…")).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByTestId("presentation-studio-slide-rail")).toBeInTheDocument()
    })
    expect(screen.queryByText("Loading presentation…")).not.toBeInTheDocument()
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

    const mediaRail = screen.getByTestId("presentation-studio-media-rail")
    expect(within(mediaRail).getByText("Audio status")).toBeInTheDocument()
    expect(within(mediaRail).getByText("Image status")).toBeInTheDocument()
    expect(within(mediaRail).getAllByText("stale").length).toBeGreaterThan(0)
    expect(within(mediaRail).getAllByText("ready").length).toBeGreaterThan(0)
  })

  it("explains readiness issues and narration timing for the selected slide", () => {
    usePresentationStudioStore.getState().loadProject(
      {
        id: "presentation-readiness",
        title: "Readiness deck",
        description: null,
        theme: "black",
        slides: [
          {
            order: 0,
            layout: "content",
            title: "Problem framing",
            content: "Summarize the core problem.",
            speaker_notes: "Open with the core problem.",
            metadata: {
              studio: {
                slideId: "slide-readiness",
                audio: { status: "stale", duration_ms: 92_000 },
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
        version: 3
      },
      { etag: 'W/"v3"' }
    )

    render(<PresentationStudioPage mode="detail" projectId="presentation-readiness" />)

    const mediaRail = screen.getByTestId("presentation-studio-media-rail")
    expect(within(mediaRail).getByText("Narration timing")).toBeInTheDocument()
    expect(within(mediaRail).getAllByText("1m 32s").length).toBeGreaterThan(0)
    expect(
      within(mediaRail).getAllByText("Refresh narration to match the latest script changes.")
        .length
    ).toBeGreaterThan(0)
    expect(
      within(mediaRail).getAllByText("Add or generate a slide image before publishing.").length
    ).toBeGreaterThan(0)
    expect(within(mediaRail).getByText("Slides with stale narration")).toBeInTheDocument()
    expect(within(mediaRail).getByText("Estimated narration length")).toBeInTheDocument()
  })

  it("surfaces task-oriented editing guidance and slide controls for the active slide", () => {
    usePresentationStudioStore.getState().loadProject(
      {
        id: "presentation-ux",
        title: "Narrated deck",
        description: null,
        theme: "black",
        slides: [
          {
            order: 0,
            layout: "content",
            title: "Intro",
            content: "Frame the talk in a single sentence.",
            speaker_notes: "Set up the presentation.",
            metadata: {
              studio: {
                slideId: "slide-ux-1",
                audio: { status: "ready", asset_ref: "output:1" },
                image: { status: "ready", asset_ref: "output:2" }
              }
            }
          },
          {
            order: 1,
            layout: "content",
            title: "Problem framing",
            content: "Summarize the core problem, constraints, and target audience.",
            speaker_notes:
              "Open with the core problem, then explain who the presentation is for.",
            metadata: {
              studio: {
                slideId: "slide-ux-2",
                audio: { status: "stale" },
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
        version: 2
      },
      { etag: 'W/"v2"' }
    )
    usePresentationStudioStore.getState().selectSlide("slide-ux-2")

    render(<PresentationStudioPage mode="detail" projectId="presentation-ux" />)

    expect(screen.getByRole("button", { name: "Duplicate slide" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Move earlier" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Move later" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Delete slide" })).toBeEnabled()
    expect(screen.getByRole("heading", { name: "On-slide copy" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Narration" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Preview" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Deck readiness" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Draft sync" })).toBeInTheDocument()
    expect(screen.getAllByText("Ready to render").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Needs attention").length).toBeGreaterThan(0)
    expect(
      screen.getByRole("button", { name: "Drag to reorder slide 1" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Drag to reorder slide 2" })
    ).toBeInTheDocument()
    expect(
      screen.getByText("This text is visible on the slide itself.")
    ).toBeInTheDocument()
    expect(
      screen.getByText("This script is spoken in the generated narration audio.")
    ).toBeInTheDocument()
  })

  it("lets the editor configure transition and manual slide timing", () => {
    usePresentationStudioStore.getState().loadProject(
      {
        id: "presentation-timing",
        title: "Timed deck",
        description: null,
        theme: "black",
        slides: [
          {
            order: 0,
            layout: "content",
            title: "Intro",
            content: "Frame the opening.",
            speaker_notes: "Open the deck.",
            metadata: {
              studio: {
                slideId: "slide-timing",
                audio: { status: "ready", duration_ms: 18_000, asset_ref: "output:1" },
                image: { status: "ready", asset_ref: "output:2" }
              }
            }
          }
        ],
        studio_data: { origin: "blank" },
        created_at: "2026-03-13T00:00:00Z",
        last_modified: "2026-03-13T00:00:00Z",
        deleted: false,
        client_id: "1",
        version: 2
      },
      { etag: 'W/"v2"' }
    )

    render(<PresentationStudioPage mode="detail" projectId="presentation-timing" />)

    expect(screen.getByRole("heading", { name: "Transitions & timing" })).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText("Transition"), {
      target: { value: "wipe" }
    })
    fireEvent.change(screen.getByLabelText("Duration mode"), {
      target: { value: "manual" }
    })
    fireEvent.change(screen.getByLabelText("Manual duration (seconds)"), {
      target: { value: "45" }
    })

    const mediaRail = screen.getByTestId("presentation-studio-media-rail")
    expect(within(mediaRail).getByText("Transition")).toBeInTheDocument()
    expect(within(mediaRail).getByText("Wipe")).toBeInTheDocument()
    expect(within(mediaRail).getByText("Effective duration")).toBeInTheDocument()
    expect(within(mediaRail).getAllByText("45s").length).toBeGreaterThan(0)
  })
})
