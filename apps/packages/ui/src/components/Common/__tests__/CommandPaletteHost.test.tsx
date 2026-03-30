import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import { CommandPaletteHost } from "../CommandPaletteHost"
import { isMac } from "@/hooks/useKeyboardShortcuts"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, defaultValue?: string) => defaultValue ?? key
  })
}))

vi.mock("@/hooks/keyboard/useShortcutConfig", () => ({
  useShortcutConfig: () => ({
    shortcuts: {},
    updateShortcut: vi.fn(),
    resetShortcuts: vi.fn(),
    resetShortcut: vi.fn()
  })
}))

describe("CommandPaletteHost", () => {
  beforeEach(() => {
    HTMLElement.prototype.scrollIntoView = vi.fn()
  })

  it("lazy-mounts and opens the palette in response to the global open event", async () => {
    render(
      <MemoryRouter>
        <CommandPaletteHost />
      </MemoryRouter>
    )

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()

    window.dispatchEvent(new CustomEvent("tldw:open-command-palette"))

    expect(await screen.findByRole("dialog")).toBeInTheDocument()
  })

  it("blocks the Cmd/Ctrl+K opener on the workspace playground route while still honoring the event API", async () => {
    render(
      <MemoryRouter initialEntries={["/workspace-playground"]}>
        <CommandPaletteHost />
      </MemoryRouter>
    )

    fireEvent.keyDown(
      document,
      isMac ? { key: "k", metaKey: true } : { key: "k", ctrlKey: true }
    )

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()

    window.dispatchEvent(new CustomEvent("tldw:open-command-palette"))

    expect(await screen.findByRole("dialog")).toBeInTheDocument()
  })
})
