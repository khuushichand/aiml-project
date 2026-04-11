import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Form } from "antd"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        return fallbackOrOptions.defaultValue || key
      }
      return key
    }
  })
}))

// Mock the heavy EntryManager so we don't pull in its dependency tree
vi.mock("../WorldBookEntryManager", () => ({
  WorldBookEntryManager: (props: any) => (
    <div data-testid="mock-entry-manager">
      EntryManager for book {props.worldBookId}
    </div>
  ),
  DEFAULT_ENTRY_FILTER_PRESET: {
    enabledFilter: "all",
    matchFilter: "all",
    searchText: ""
  }
}))

// Mock WorldBookForm to avoid its internal complexity
vi.mock("../WorldBookForm", () => ({
  WorldBookForm: (props: any) => (
    <div data-testid="mock-world-book-form">
      WorldBookForm mode={props.mode}
    </div>
  )
}))

import { WorldBookDetailPanel } from "../WorldBookDetailPanel"

const mockWorldBook = {
  id: 1,
  name: "Fantasy Lore",
  description: "Magic systems and creatures",
  enabled: true,
  entry_count: 42,
  token_budget: 700,
  last_modified: Date.now() - 3600_000,
  scan_depth: 2,
  recursive_scanning: false
}

const mockAttachedCharacters = [
  { id: 10, name: "Gandalf" },
  { id: 20, name: "Frodo" }
]

const mockAllCharacters = [
  { id: 10, name: "Gandalf" },
  { id: 20, name: "Frodo" },
  { id: 30, name: "Aragorn" }
]

// Wrapper that provides a form instance
const TestWrapper: React.FC<{
  worldBook?: any
  attachedCharacters?: any[]
  allWorldBooks?: any[]
  allCharacters?: any[]
}> = ({
  worldBook = mockWorldBook,
  attachedCharacters = mockAttachedCharacters,
  allWorldBooks = [mockWorldBook],
  allCharacters = mockAllCharacters
}) => {
  const [entryForm] = Form.useForm()
  return (
    <WorldBookDetailPanel
      worldBook={worldBook}
      attachedCharacters={attachedCharacters}
      allWorldBooks={allWorldBooks}
      allCharacters={allCharacters}
      onUpdateWorldBook={vi.fn()}
      onAttachCharacter={vi.fn().mockResolvedValue(undefined)}
      onDetachCharacter={vi.fn().mockResolvedValue(undefined)}
      onOpenTestMatching={vi.fn()}
      maxRecursiveDepth={10}
      updating={false}
      entryFormInstance={entryForm}
    />
  )
}

describe("WorldBookDetailPanel", () => {
  it("renders the summary bar with key metadata (name, entries, enabled, characters)", () => {
    render(<TestWrapper />)

    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "Fantasy Lore"
    )
    expect(screen.getByText(/42/)).toBeInTheDocument()
    expect(screen.getByText(/enabled/i)).toBeInTheDocument()
    expect(screen.getByText(/2 characters/i)).toBeInTheDocument()
  })

  it("renders Entries tab as default active tab", () => {
    render(<TestWrapper />)

    const entriesTab = screen.getByRole("tab", { name: /entries/i })
    expect(entriesTab).toHaveAttribute("aria-selected", "true")
  })

  it("renders all four tabs (entries, attachments, stats, settings)", () => {
    render(<TestWrapper />)

    expect(screen.getByRole("tab", { name: /entries/i })).toBeInTheDocument()
    expect(
      screen.getByRole("tab", { name: /attachments/i })
    ).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /stats/i })).toBeInTheDocument()
    expect(
      screen.getByRole("tab", { name: /settings/i })
    ).toBeInTheDocument()
  })

  it("switches to Settings tab on click", async () => {
    const user = userEvent.setup()
    render(<TestWrapper />)

    const settingsTab = screen.getByRole("tab", { name: /settings/i })
    await user.click(settingsTab)

    await waitFor(() => {
      expect(settingsTab).toHaveAttribute("aria-selected", "true")
    })

    const entriesTab = screen.getByRole("tab", { name: /entries/i })
    expect(entriesTab).toHaveAttribute("aria-selected", "false")
  })

  it("has correct landmark role (main with aria-label)", () => {
    render(<TestWrapper />)

    const main = screen.getByRole("main")
    expect(main).toHaveAttribute("aria-label", "World book detail")
  })

  it("renders placeholder when worldBook is null", () => {
    render(<TestWrapper worldBook={null} />)

    expect(
      screen.getByText(/select a world book/i)
    ).toBeInTheDocument()

    const main = screen.getByRole("main")
    expect(main).toHaveAttribute("aria-label", "World book detail")
  })
})
