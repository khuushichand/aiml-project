import React from "react"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { NotesDockHost } from "../NotesDockHost"
import { useNotesDockStore } from "@/store/notes-dock"

const responsiveState = vi.hoisted(() => ({
  isMobile: false
}))

vi.mock("@/hooks/useMediaQuery", () => ({
  useMobile: () => responsiveState.isMobile
}))

vi.mock("../NotesDockPanel", () => ({
  NotesDockPanel: () => <div data-testid="notes-dock-panel-mock">Notes dock panel</div>
}))

describe("NotesDockHost stage 3 responsive behavior", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useNotesDockStore.setState({
      isOpen: false,
      notes: [],
      activeNoteId: null
    })
  })

  it("does not render dock panel on mobile and preserves open state for desktop return", async () => {
    responsiveState.isMobile = true
    useNotesDockStore.setState({ isOpen: true })

    const { rerender } = render(<NotesDockHost />)

    expect(screen.queryByTestId("notes-dock-panel-mock")).not.toBeInTheDocument()
    expect(useNotesDockStore.getState().isOpen).toBe(true)

    responsiveState.isMobile = false
    rerender(<NotesDockHost />)
    expect(await screen.findByTestId("notes-dock-panel-mock")).toBeInTheDocument()
  })

  it("renders dock panel when open on desktop", async () => {
    responsiveState.isMobile = false
    useNotesDockStore.setState({ isOpen: true })

    render(<NotesDockHost />)

    expect(await screen.findByTestId("notes-dock-panel-mock")).toBeInTheDocument()
  })
})
