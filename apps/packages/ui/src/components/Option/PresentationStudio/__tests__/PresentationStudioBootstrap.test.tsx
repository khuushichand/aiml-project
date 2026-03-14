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

describe("PresentationStudioPage bootstrap", () => {
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

  it("creates a blank project only once in strict mode", async () => {
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
              transition: "fade",
              timing_mode: "auto",
              manual_duration_ms: null,
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

  it("leaves the loading state after a detail fetch resolves", async () => {
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
              transition: "fade",
              timing_mode: "auto",
              manual_duration_ms: null,
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
})
