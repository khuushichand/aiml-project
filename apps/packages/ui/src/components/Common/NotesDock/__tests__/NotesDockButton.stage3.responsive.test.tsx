import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { NotesDockButton } from "../NotesDockButton"
import { useNotesDockStore } from "@/store/notes-dock"

const responsiveState = vi.hoisted(() => ({
  isMobile: false
}))

vi.mock("@/hooks/useMediaQuery", () => ({
  useMobile: () => responsiveState.isMobile
}))

describe("NotesDockButton stage 3 responsive behavior", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useNotesDockStore.setState({
      isOpen: false,
      notes: [],
      activeNoteId: null
    })
  })

  it("hides dock trigger on mobile viewports", () => {
    responsiveState.isMobile = true
    render(<NotesDockButton />)

    expect(screen.queryByRole("button", { name: "Open Notes Dock" })).not.toBeInTheDocument()
  })

  it("shows dock trigger on desktop and toggles open", () => {
    responsiveState.isMobile = false
    render(<NotesDockButton />)

    const button = screen.getByRole("button", { name: "Open Notes Dock" })
    expect(button).toHaveAttribute("aria-keyshortcuts", "Control+Shift+N Meta+Shift+N")
    fireEvent.click(button)

    expect(useNotesDockStore.getState().isOpen).toBe(true)
  })
})
