import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { WritingPlaygroundShell } from "../WritingPlaygroundShell"

vi.mock("antd", () => ({
  Drawer: ({
    title,
    open,
    onClose,
    children
  }: {
    title: string
    open: boolean
    onClose: () => void
    children: React.ReactNode
  }) => (
    <div data-testid={`drawer-${title.toLowerCase()}`} data-open={String(open)}>
      <button type="button" onClick={onClose}>
        Close {title}
      </button>
      {children}
    </div>
  )
}))

const originalInnerWidth = window.innerWidth

const setViewportWidth = (width: number) => {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: width
  })
}

describe("WritingPlaygroundShell", () => {
  beforeEach(() => {
    setViewportWidth(960)
  })

  afterEach(() => {
    setViewportWidth(originalInnerWidth)
  })

  it("uses explicit close handlers for compact drawers instead of toggle callbacks", () => {
    const onLibraryToggle = vi.fn()
    const onInspectorToggle = vi.fn()
    const onLibraryClose = vi.fn()
    const onInspectorClose = vi.fn()

    render(
      <WritingPlaygroundShell
        libraryOpen
        inspectorOpen
        onLibraryToggle={onLibraryToggle}
        onInspectorToggle={onInspectorToggle}
        onLibraryClose={onLibraryClose}
        onInspectorClose={onInspectorClose}
        libraryContent={<div>Library</div>}
        inspectorContent={<div>Inspector</div>}>
        <div>Editor</div>
      </WritingPlaygroundShell>
    )

    fireEvent.click(screen.getByRole("button", { name: "Close Sessions" }))
    fireEvent.click(screen.getByRole("button", { name: "Close Settings" }))

    expect(onLibraryClose).toHaveBeenCalledTimes(1)
    expect(onInspectorClose).toHaveBeenCalledTimes(1)
    expect(onLibraryToggle).not.toHaveBeenCalled()
    expect(onInspectorToggle).not.toHaveBeenCalled()
  })
})
