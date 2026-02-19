import React from "react"
import { fireEvent, render, waitFor } from "@testing-library/react"
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

describe("NotesDockHost stage 1 keyboard shortcut", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    responsiveState.isMobile = false
    useNotesDockStore.setState({
      isOpen: false,
      notes: [],
      activeNoteId: null
    })
  })

  it("opens dock with Ctrl+Shift+N on desktop", () => {
    render(<NotesDockHost />)

    fireEvent.keyDown(window, { key: "n", ctrlKey: true, shiftKey: true })
    expect(useNotesDockStore.getState().isOpen).toBe(true)
  })

  it("opens dock with Cmd+Shift+N on desktop", () => {
    render(<NotesDockHost />)

    fireEvent.keyDown(window, { key: "n", metaKey: true, shiftKey: true })
    expect(useNotesDockStore.getState().isOpen).toBe(true)
  })

  it("does not trigger shortcut while typing in form fields", () => {
    render(<NotesDockHost />)
    const input = document.createElement("input")
    document.body.appendChild(input)
    input.focus()

    fireEvent.keyDown(input, { key: "n", ctrlKey: true, shiftKey: true })
    expect(useNotesDockStore.getState().isOpen).toBe(false)

    input.remove()
  })

  it("dispatches close request event when shortcut is pressed while open", async () => {
    useNotesDockStore.setState({ isOpen: true })
    const closeHandler = vi.fn(() => {
      useNotesDockStore.getState().setOpen(false)
    })
    window.addEventListener("tldw:notes-dock-request-close", closeHandler as EventListener)
    render(<NotesDockHost />)

    fireEvent.keyDown(window, { key: "n", ctrlKey: true, shiftKey: true })

    await waitFor(() => {
      expect(closeHandler).toHaveBeenCalledTimes(1)
      expect(useNotesDockStore.getState().isOpen).toBe(false)
    })

    window.removeEventListener("tldw:notes-dock-request-close", closeHandler as EventListener)
  })

  it("tears down the global shortcut listener on unmount", () => {
    const { unmount } = render(<NotesDockHost />)
    unmount()

    fireEvent.keyDown(window, { key: "n", ctrlKey: true, shiftKey: true })
    expect(useNotesDockStore.getState().isOpen).toBe(false)
  })
})
