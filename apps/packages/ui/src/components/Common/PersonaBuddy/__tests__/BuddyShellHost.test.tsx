import React from "react"
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import {
  BuddyShellRenderContextProvider
} from "../BuddyShellRenderContext"
import {
  DEFAULT_PERSONA_BUDDY_SHELL_POSITIONS,
  usePersonaBuddyShellStore
} from "@/store/persona-buddy-shell"
import { BuddyShellHost } from "../BuddyShellHost"

const mocks = vi.hoisted(() => ({
  isDesktop: true,
  selectedAssistant: null as Record<string, unknown> | null
}))

vi.mock("@/hooks/useMediaQuery", () => ({
  useDesktop: () => mocks.isDesktop
}))

vi.mock("@/hooks/useSelectedAssistant", () => ({
  useSelectedAssistant: () => [
    mocks.selectedAssistant,
    vi.fn(),
    {
      isLoading: false,
      setRenderValue: vi.fn()
    }
  ]
}))

const buildPersonaSelection = ({
  id = "persona-1",
  hasBuddy = true
}: {
  id?: string
  hasBuddy?: boolean
} = {}) => ({
  kind: "persona",
  id,
  name: `Persona ${id}`,
  buddy_summary: hasBuddy
    ? {
        has_buddy: true,
        persona_name: `Persona ${id}`,
        role_summary: "Keeps the route on track",
        visual: {
          species_id: "owl",
          silhouette_id: "perch",
          palette_id: "dawn"
        }
      }
    : null
})

const renderHost = ({
  root = "web",
  context,
  selectedAssistant = buildPersonaSelection(),
  isDesktop = true
}: {
  root?: "web" | "sidepanel"
  context?: {
    surface_id: string
    surface_active: boolean
    active_persona_id: string | null
    position_bucket: "web-desktop" | "sidepanel-desktop"
    persona_source:
      | "route-local"
      | "route-bootstrap"
      | "catalog"
      | "selected-assistant-fallback"
      | null
  }
  selectedAssistant?: Record<string, unknown> | null
  isDesktop?: boolean
} = {}) => {
  mocks.isDesktop = isDesktop
  mocks.selectedAssistant = selectedAssistant

  return render(
    <BuddyShellRenderContextProvider initialContext={context ?? null}>
      <BuddyShellHost root={root} />
    </BuddyShellRenderContextProvider>
  )
}

describe("BuddyShellHost", () => {
  beforeEach(() => {
    mocks.isDesktop = true
    mocks.selectedAssistant = null
    document.body.innerHTML = ""
    const portalRoot = document.createElement("div")
    portalRoot.id = "tldw-portal-root"
    document.body.appendChild(portalRoot)
    localStorage.clear()
    usePersonaBuddyShellStore.setState({
      isOpen: false,
      positions: {
        "web-desktop": {
          ...DEFAULT_PERSONA_BUDDY_SHELL_POSITIONS["web-desktop"]
        },
        "sidepanel-desktop": {
          ...DEFAULT_PERSONA_BUDDY_SHELL_POSITIONS["sidepanel-desktop"]
        }
      }
    })
  })

  afterEach(() => {
    cleanup()
  })

  it("stays dormant until the current surface explicitly activates buddy rendering", () => {
    renderHost({
      context: {
        surface_id: "chat",
        surface_active: false,
        active_persona_id: "persona-1",
        position_bucket: "web-desktop",
        persona_source: "route-local"
      }
    })

    expect(screen.queryByTestId("persona-buddy-dock")).not.toBeInTheDocument()
  })

  it("suppresses the web host below the desktop breakpoint", () => {
    renderHost({
      isDesktop: false,
      context: {
        surface_id: "chat",
        surface_active: true,
        active_persona_id: "persona-1",
        position_bucket: "web-desktop",
        persona_source: "route-local"
      }
    })

    expect(screen.queryByTestId("persona-buddy-dock")).not.toBeInTheDocument()
  })

  it("allows the sidepanel host even when the viewport is narrow", () => {
    renderHost({
      root: "sidepanel",
      isDesktop: false,
      context: {
        surface_id: "chat",
        surface_active: true,
        active_persona_id: "persona-1",
        position_bucket: "sidepanel-desktop",
        persona_source: "route-local"
      }
    })

    expect(screen.getByTestId("persona-buddy-dock")).toBeInTheDocument()
  })

  it("requires the render-context persona match before using selected-assistant fallback", () => {
    const fallbackPersona = buildPersonaSelection({ id: "persona-1" })

    const firstRender = renderHost({
      context: {
        surface_id: "chat",
        surface_active: true,
        active_persona_id: "persona-2",
        position_bucket: "web-desktop",
        persona_source: "route-local"
      },
      selectedAssistant: fallbackPersona
    })

    expect(screen.queryByTestId("persona-buddy-dock")).not.toBeInTheDocument()

    firstRender.unmount()
    mocks.selectedAssistant = fallbackPersona
    renderHost({
      context: {
        surface_id: "chat",
        surface_active: true,
        active_persona_id: null,
        position_bucket: "web-desktop",
        persona_source: "selected-assistant-fallback"
      },
      selectedAssistant: fallbackPersona
    })

    expect(screen.getByTestId("persona-buddy-dock")).toBeInTheDocument()
  })

  it("stays dormant when the resolved persona has no buddy summary", () => {
    renderHost({
      context: {
        surface_id: "chat",
        surface_active: true,
        active_persona_id: "persona-1",
        position_bucket: "web-desktop",
        persona_source: "route-local"
      },
      selectedAssistant: buildPersonaSelection({
        id: "persona-1",
        hasBuddy: false
      })
    })

    expect(screen.queryByTestId("persona-buddy-dock")).not.toBeInTheDocument()
  })
})
