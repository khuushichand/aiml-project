// @vitest-environment jsdom

import { fireEvent, render, screen, within } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import {
  DEFAULT_COMPANION_HOME_LAYOUT
} from "@/store/companion-home-layout"
import { CustomizeHomeDrawer } from "../CustomizeHomeDrawer"

describe("CustomizeHomeDrawer", () => {
  it("shows pinned system cards as always visible and non-removable", () => {
    render(
      <CustomizeHomeDrawer
        open
        layout={DEFAULT_COMPANION_HOME_LAYOUT}
        onClose={vi.fn()}
        onLayoutChange={vi.fn()}
      />
    )

    const inboxRow = screen.getByTestId("companion-home-layout-row-inbox-preview")
    expect(within(inboxRow).getByText("Always shown")).toBeInTheDocument()
    expect(
      within(inboxRow).queryByRole("button", { name: /hide inbox preview/i })
    ).not.toBeInTheDocument()
  })

  it("toggles visibility for customizable cards", () => {
    const handleLayoutChange = vi.fn()

    render(
      <CustomizeHomeDrawer
        open
        layout={DEFAULT_COMPANION_HOME_LAYOUT}
        onClose={vi.fn()}
        onLayoutChange={handleLayoutChange}
      />
    )

    fireEvent.click(
      within(
        screen.getByTestId("companion-home-layout-row-goals-focus")
      ).getByRole("button", { name: /hide goals \/ focus/i })
    )

    expect(handleLayoutChange).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          id: "goals-focus",
          visible: false
        })
      ])
    )
  })

  it("reorders customizable cards with button-based controls", () => {
    const handleLayoutChange = vi.fn()

    render(
      <CustomizeHomeDrawer
        open
        layout={DEFAULT_COMPANION_HOME_LAYOUT}
        onClose={vi.fn()}
        onLayoutChange={handleLayoutChange}
      />
    )

    fireEvent.click(
      within(
        screen.getByTestId("companion-home-layout-row-reading-queue")
      ).getByRole("button", { name: /move reading queue up/i })
    )

    const updatedLayout = handleLayoutChange.mock.calls[0]?.[0]
    expect(updatedLayout.map((card: { id: string }) => card.id)).toEqual([
      "inbox-preview",
      "needs-attention",
      "resume-work",
      "goals-focus",
      "reading-queue",
      "recent-activity"
    ])
  })

  it("focuses the dialog and closes on Escape", () => {
    const handleClose = vi.fn()

    render(
      <CustomizeHomeDrawer
        open
        layout={DEFAULT_COMPANION_HOME_LAYOUT}
        onClose={handleClose}
        onLayoutChange={vi.fn()}
      />
    )

    expect(screen.getByRole("dialog")).toHaveFocus()

    fireEvent.keyDown(document, { key: "Escape" })

    expect(handleClose).toHaveBeenCalledTimes(1)
  })
})
