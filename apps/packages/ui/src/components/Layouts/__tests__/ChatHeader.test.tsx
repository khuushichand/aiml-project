import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { TFunction } from "i18next"
import { ChatHeader } from "../ChatHeader"

vi.mock("antd", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Input: ({ value, onChange, ...rest }: any) => (
    <input
      value={value}
      onChange={onChange}
      {...rest}
    />
  )
}))

vi.mock("~/assets/icon.png", () => ({
  default: "icon.png"
}))

vi.mock("../HeaderShortcuts", () => ({
  HeaderShortcuts: ({ expanded }: { expanded: boolean }) => (
    <div data-testid="header-shortcuts" data-expanded={expanded ? "true" : "false"} />
  )
}))

const t = ((key: string, fallback?: string) => fallback || key) as unknown as TFunction

const createProps = (overrides: Partial<React.ComponentProps<typeof ChatHeader>> = {}) => ({
  t,
  temporaryChat: false,
  historyId: "history-1",
  chatTitle: "Chat title",
  isEditingTitle: false,
  onTitleChange: vi.fn(),
  onTitleEditStart: vi.fn(),
  onTitleCommit: vi.fn(),
  onToggleSidebar: vi.fn(),
  sidebarCollapsed: false,
  onOpenCommandPalette: vi.fn(),
  onOpenShortcutsModal: vi.fn(),
  onOpenSettings: vi.fn(),
  onClearChat: vi.fn(),
  shortcutsExpanded: false,
  onToggleShortcuts: vi.fn(),
  commandKeyLabel: "Ctrl+",
  ...overrides
})

describe("ChatHeader shortcut toggle", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("shows signpost button with 'Show shortcuts' when collapsed and requests expand", () => {
    const props = createProps({ shortcutsExpanded: false })
    render(<ChatHeader {...props} />)

    const toggleButton = screen.getByRole("button", { name: "Show shortcuts" })
    expect(toggleButton).toHaveAttribute("aria-expanded", "false")
    fireEvent.click(toggleButton)

    expect(props.onToggleShortcuts).toHaveBeenCalledWith(true)
    expect(screen.getByTestId("header-shortcuts")).toHaveAttribute(
      "data-expanded",
      "false"
    )
  })

  it("shows signpost button with 'Hide shortcuts' when expanded and requests collapse", () => {
    const props = createProps({ shortcutsExpanded: true })
    render(<ChatHeader {...props} />)

    const toggleButton = screen.getByRole("button", { name: "Hide shortcuts" })
    expect(toggleButton).toHaveAttribute("aria-expanded", "true")
    fireEvent.click(toggleButton)

    expect(props.onToggleShortcuts).toHaveBeenCalledWith(false)
    expect(screen.getByTestId("header-shortcuts")).toHaveAttribute(
      "data-expanded",
      "true"
    )
  })

  it("applies focus-visible ring classes to key header controls", () => {
    const props = createProps()
    render(<ChatHeader {...props} />)

    const controls = [
      screen.getByRole("button", { name: "Collapse sidebar" }),
      screen.getByRole("button", { name: "Show shortcuts" }),
      screen.getByRole("button", { name: "New chat" }),
      screen.getByRole("button", { name: "Open settings" }),
      screen.getByRole("button", { name: "Show keyboard shortcuts" })
    ]

    for (const control of controls) {
      expect(control.className).toContain("focus-visible:ring-2")
      expect(control.className).toContain("focus-visible:ring-focus")
      expect(control.className).toContain("focus-visible:ring-offset-2")
      expect(control.className).toContain("focus-visible:ring-offset-bg")
    }
  })
})
