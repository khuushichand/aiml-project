import React from "react"
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import {
  BuddyShellRenderContextProvider
} from "../BuddyShellRenderContext"
import { PERSONA_BUDDY_SHELL_ENABLED_SETTING } from "@/services/settings/ui-settings"
import {
  DEFAULT_PERSONA_BUDDY_SHELL_POSITIONS,
  usePersonaBuddyShellStore
} from "@/store/persona-buddy-shell"
import { BuddyShellHost } from "../BuddyShellHost"

const mocks = vi.hoisted(() => ({
  isDesktop: true,
  selectedAssistant: null as Record<string, unknown> | null,
  buddyShellEnabled: true
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

vi.mock("@/hooks/useSetting", () => ({
  useSetting: (setting: { key?: string; defaultValue: unknown }) => {
    if (setting?.key === PERSONA_BUDDY_SHELL_ENABLED_SETTING.key) {
      return [mocks.buddyShellEnabled, vi.fn(), { isLoading: false }]
    }
    return [setting.defaultValue, vi.fn(), { isLoading: false }]
  }
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

const buildBuddySummary = (id: string, hasBuddy = true) => ({
  has_buddy: hasBuddy,
  persona_name: `Persona ${id}`,
  role_summary: hasBuddy ? "Keeps the route on track" : null,
  visual: hasBuddy
    ? {
        species_id: "owl",
        silhouette_id: "perch",
        palette_id: "dawn"
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
    buddy_summary?: {
      has_buddy: boolean
      persona_name: string
      role_summary: string | null
      visual: {
        species_id: string
        silhouette_id: string
        palette_id: string
      } | null
    } | null
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
    mocks.buddyShellEnabled = true
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

  it("unmounts the shell when the global buddy setting is disabled", () => {
    mocks.buddyShellEnabled = false
    usePersonaBuddyShellStore.setState((state) => ({
      ...state,
      isOpen: true
    }))

    renderHost({
      context: {
        surface_id: "chat",
        surface_active: true,
        active_persona_id: "persona-1",
        position_bucket: "web-desktop",
        persona_source: "route-local",
        buddy_summary: buildBuddySummary("persona-1")
      }
    })

    expect(screen.queryByTestId("persona-buddy-dock")).not.toBeInTheDocument()
    expect(usePersonaBuddyShellStore.getState().isOpen).toBe(true)
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
        persona_source: "route-local",
        buddy_summary: buildBuddySummary("persona-1")
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

  it("does not use selected-assistant fallback for route-local surfaces without an explicit fallback source", () => {
    renderHost({
      context: {
        surface_id: "persona-garden",
        surface_active: true,
        active_persona_id: null,
        position_bucket: "web-desktop",
        persona_source: "route-local"
      },
      selectedAssistant: buildPersonaSelection({ id: "persona-1" })
    })

    expect(screen.queryByTestId("persona-buddy-dock")).not.toBeInTheDocument()
  })

  it("ignores malformed persona selections that do not include a name", () => {
    renderHost({
      context: {
        surface_id: "chat",
        surface_active: true,
        active_persona_id: null,
        position_bucket: "web-desktop",
        persona_source: "selected-assistant-fallback"
      },
      selectedAssistant: {
        kind: "persona",
        id: "persona-1"
      }
    })

    expect(screen.queryByTestId("persona-buddy-dock")).not.toBeInTheDocument()
  })

  it("prefers route-local buddy summary over stale selected-assistant persona data", () => {
    renderHost({
      context: {
        surface_id: "persona-garden",
        surface_active: true,
        active_persona_id: "persona-2",
        position_bucket: "sidepanel-desktop",
        persona_source: "route-local",
        buddy_summary: buildBuddySummary("persona-2")
      },
      root: "sidepanel",
      selectedAssistant: buildPersonaSelection({ id: "persona-1" })
    })

    expect(screen.getByTestId("persona-buddy-dock")).toHaveTextContent(
      "Persona persona-2"
    )
    expect(screen.getByTestId("persona-buddy-dock")).toHaveTextContent("owl")
  })

  it("treats an explicit null surface summary as authoritative over cached assistant buddy data", () => {
    renderHost({
      context: {
        surface_id: "sidepanel-chat",
        surface_active: true,
        active_persona_id: "persona-1",
        position_bucket: "sidepanel-desktop",
        persona_source: "catalog",
        buddy_summary: null
      },
      root: "sidepanel",
      selectedAssistant: buildPersonaSelection({ id: "persona-1" })
    })

    expect(screen.getByTestId("persona-buddy-dock")).toHaveAttribute(
      "data-dormant",
      "true"
    )
    expect(screen.getByTestId("persona-buddy-dock")).toHaveTextContent(
      "buddy unavailable"
    )
    expect(screen.getByTestId("persona-buddy-dock")).not.toHaveTextContent("owl")
  })

  it("renders a dormant shell when the resolved persona has no buddy summary", () => {
    renderHost({
      context: {
        surface_id: "chat",
        surface_active: true,
        active_persona_id: "persona-1",
        position_bucket: "web-desktop",
        persona_source: "route-local",
        buddy_summary: null
      }
    })

    expect(screen.getByTestId("persona-buddy-dock")).toHaveAttribute(
      "data-dormant",
      "true"
    )
    expect(
      screen.queryByTestId("persona-buddy-popover")
    ).not.toBeInTheDocument()
  })

  it("clamps persisted positions back into the viewport after mount", async () => {
    const rectSpy = vi
      .spyOn(HTMLDivElement.prototype, "getBoundingClientRect")
      .mockReturnValue({
        x: 0,
        y: 0,
        left: 0,
        top: 0,
        right: 200,
        bottom: 120,
        width: 200,
        height: 120,
        toJSON: () => ({})
      } as DOMRect)

    const originalWidth = window.innerWidth
    const originalHeight = window.innerHeight

    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 320
    })
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 240
    })

    usePersonaBuddyShellStore.setState((state) => ({
      ...state,
      positions: {
        ...state.positions,
        "web-desktop": {
          x: 9999,
          y: 9999
        }
      }
    }))

    renderHost({
      context: {
        surface_id: "chat",
        surface_active: true,
        active_persona_id: "persona-1",
        position_bucket: "web-desktop",
        persona_source: "route-local",
        buddy_summary: buildBuddySummary("persona-1")
      }
    })

    await waitFor(() => {
      expect(
        usePersonaBuddyShellStore.getState().positions["web-desktop"]
      ).toEqual({
        x: 104,
        y: 104
      })
    })

    rectSpy.mockRestore()
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: originalWidth
    })
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: originalHeight
    })
  })

  it("stays dormant when an active chat surface does not have a persona selected", () => {
    renderHost({
      root: "sidepanel",
      context: {
        surface_id: "sidepanel-chat",
        surface_active: true,
        active_persona_id: null,
        position_bucket: "sidepanel-desktop",
        persona_source: null
      },
      selectedAssistant: {
        kind: "character",
        id: "character-1",
        name: "Narrator"
      }
    })

    expect(screen.queryByTestId("persona-buddy-dock")).not.toBeInTheDocument()
  })
})
