import React from "react"
import { fireEvent, render, screen, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { HeaderShortcuts } from "../HeaderShortcuts"

/* ------------------------------------------------------------------ */
/*  Mocks                                                              */
/* ------------------------------------------------------------------ */

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
    i18n: { language: "en" }
  })
}))

vi.mock("@/hooks/useKeyboardShortcuts", () => ({
  useShortcut: vi.fn(),
  formatShortcut: vi.fn(() => ""),
  isMac: false
}))

vi.mock("@/hooks/useSetting", () => ({
  useSetting: (setting: { key: string }) => {
    if (setting.key === "header_shortcuts_expanded") {
      return [false, vi.fn().mockResolvedValue(undefined)]
    }
    // shortcut selection: return all IDs so all items are visible
    return [
      [
        "chat", "prompts", "prompt-studio", "characters",
        "chat-dictionaries", "world-books", "workspace-playground",
        "knowledge-qa", "media", "document-workspace",
        "multi-item-review", "content-review", "collections",
        "watchlists", "notes", "chatbooks-playground", "flashcards",
        "quizzes", "evaluations", "chunking-playground",
        "stt-playground", "tts-playground", "audiobook-studio",
        "workflows", "writing-playground", "acp-playground",
        "skills", "kanban-playground",
        "model-playground", "data-tables",
        "admin-server", "documentation", "moderation-playground",
        "admin-llamacpp", "admin-mlx", "settings"
      ],
      vi.fn().mockResolvedValue(undefined)
    ]
  }
}))

vi.mock("@/services/settings/ui-settings", () => ({
  HEADER_SHORTCUTS_EXPANDED_SETTING: { key: "header_shortcuts_expanded", defaultValue: false },
  HEADER_SHORTCUT_SELECTION_SETTING: { key: "header_shortcut_selection", defaultValue: [] }
}))

const renderWithRouter = (ui: React.ReactElement, initialRoute = "/") =>
  render(<MemoryRouter initialEntries={[initialRoute]}>{ui}</MemoryRouter>)

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe("HeaderShortcuts launcher modal", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders nothing when closed (expanded=false)", () => {
    const { container } = renderWithRouter(
      <HeaderShortcuts expanded={false} onExpandedChange={vi.fn()} />
    )
    expect(container.innerHTML).toBe("")
  })

  it("renders a dialog when open (expanded=true)", () => {
    renderWithRouter(
      <HeaderShortcuts expanded={true} onExpandedChange={vi.fn()} />
    )
    expect(screen.getByRole("dialog")).toBeInTheDocument()
  })

  it("shows search input placeholder", () => {
    renderWithRouter(
      <HeaderShortcuts expanded={true} onExpandedChange={vi.fn()} />
    )
    expect(screen.getByPlaceholderText("Search pages...")).toBeInTheDocument()
  })

  it("shows 'All' category in sidebar", () => {
    renderWithRouter(
      <HeaderShortcuts expanded={true} onExpandedChange={vi.fn()} />
    )
    expect(screen.getByText("All")).toBeInTheDocument()
  })

  it("shows category names in sidebar", () => {
    renderWithRouter(
      <HeaderShortcuts expanded={true} onExpandedChange={vi.fn()} />
    )
    const nav = screen.getByLabelText("Categories")
    expect(within(nav).getByText("Chat & Characters")).toBeInTheDocument()
    expect(within(nav).getByText("Library & Research")).toBeInTheDocument()
    expect(within(nav).getByText("Audio & Speech")).toBeInTheDocument()
    expect(within(nav).getByText("Creation & Automation")).toBeInTheDocument()
    expect(within(nav).getByText("Tools & Playgrounds")).toBeInTheDocument()
    expect(within(nav).getByText("Admin & Settings")).toBeInTheDocument()
  })

  it("shows items with group headers in All mode", () => {
    renderWithRouter(
      <HeaderShortcuts expanded={true} onExpandedChange={vi.fn()} />
    )
    // Items should be visible
    expect(screen.getByText("Chat")).toBeInTheDocument()
    expect(screen.getByText("Prompts")).toBeInTheDocument()
    expect(screen.getByText("Settings")).toBeInTheDocument()
  })

  it("filters items when category is clicked", () => {
    renderWithRouter(
      <HeaderShortcuts expanded={true} onExpandedChange={vi.fn()} />
    )

    // Click "Audio & Speech" category in the sidebar
    const nav = screen.getByLabelText("Categories")
    fireEvent.click(within(nav).getByText("Audio & Speech"))

    // Audio items should be visible
    expect(screen.getByText("STT Playground")).toBeInTheDocument()
    expect(screen.getByText("TTS Playground")).toBeInTheDocument()

    // Non-audio items should NOT be visible (in the listbox)
    const listbox = screen.getByRole("listbox")
    expect(within(listbox).queryByText("Chat")).not.toBeInTheDocument()
  })

  it("filters items by search query", () => {
    renderWithRouter(
      <HeaderShortcuts expanded={true} onExpandedChange={vi.fn()} />
    )

    const input = screen.getByPlaceholderText("Search pages...")
    fireEvent.change(input, { target: { value: "Media" } })

    const listbox = screen.getByRole("listbox")
    expect(within(listbox).getByText("Media")).toBeInTheDocument()
    // "Chat" shouldn't match "Media"
    expect(within(listbox).queryByText("Chat")).not.toBeInTheDocument()
  })

  it("shows empty state when search has no results", () => {
    renderWithRouter(
      <HeaderShortcuts expanded={true} onExpandedChange={vi.fn()} />
    )

    const input = screen.getByPlaceholderText("Search pages...")
    fireEvent.change(input, { target: { value: "xyznonexistent" } })

    expect(screen.getByText("No pages match your search")).toBeInTheDocument()
  })

  it("calls onExpandedChange(false) when Escape is pressed", () => {
    const onExpandedChange = vi.fn()
    renderWithRouter(
      <HeaderShortcuts expanded={true} onExpandedChange={onExpandedChange} />
    )

    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" })
    expect(onExpandedChange).toHaveBeenCalledWith(false)
  })

  it("calls onExpandedChange(false) when backdrop is clicked", () => {
    const onExpandedChange = vi.fn()
    const { container } = renderWithRouter(
      <HeaderShortcuts expanded={true} onExpandedChange={onExpandedChange} />
    )

    // The backdrop is the first fixed overlay element
    const backdrop = container.parentElement!.querySelector(".fixed.inset-0")
    expect(backdrop).toBeInTheDocument()
    fireEvent.click(backdrop!)
    expect(onExpandedChange).toHaveBeenCalledWith(false)
  })

  it("shows keyboard shortcut badges for items with shortcutIndex", () => {
    renderWithRouter(
      <HeaderShortcuts expanded={true} onExpandedChange={vi.fn()} />
    )

    // Chat has shortcutIndex: 1, so should display "Ctrl+1" (isMac is false in mock)
    expect(screen.getByText("Ctrl+1")).toBeInTheDocument()
    expect(screen.getByText("Ctrl+2")).toBeInTheDocument()
  })

  it("displays match count badges in sidebar when searching", () => {
    renderWithRouter(
      <HeaderShortcuts expanded={true} onExpandedChange={vi.fn()} />
    )

    const input = screen.getByPlaceholderText("Search pages...")
    fireEvent.change(input, { target: { value: "Playground" } })

    // Multiple items have "Playground" in their name, sidebar should show counts
    const nav = screen.getByLabelText("Categories")
    // All category should show total count
    const allButton = within(nav).getByText("All")
    // The count is a sibling span within the same button
    expect(allButton.closest("button")!.querySelector(".text-xs")).toBeInTheDocument()
  })

  it("renders items as NavLink elements with role=option", () => {
    renderWithRouter(
      <HeaderShortcuts expanded={true} onExpandedChange={vi.fn()} />
    )

    const options = screen.getAllByRole("option")
    expect(options.length).toBeGreaterThan(0)
  })

  it("has aria-modal and role=dialog on the modal container", () => {
    renderWithRouter(
      <HeaderShortcuts expanded={true} onExpandedChange={vi.fn()} />
    )

    const dialog = screen.getByRole("dialog")
    expect(dialog).toHaveAttribute("aria-modal", "true")
  })

  it("shows footer with keyboard navigation hints", () => {
    renderWithRouter(
      <HeaderShortcuts expanded={true} onExpandedChange={vi.fn()} />
    )

    expect(screen.getByText("navigate")).toBeInTheDocument()
    expect(screen.getByText("select")).toBeInTheDocument()
    expect(screen.getByText("toggle")).toBeInTheDocument()
  })
})
