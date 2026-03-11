// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("antd", () => ({
  Select: ({ placeholder, ...props }: any) => (
    <div data-testid="categories-select">{placeholder}</div>
  ),
  Modal: { confirm: vi.fn() },
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>
}))

vi.mock("lucide-react", () => ({
  Trash2: ({ size }: any) => <span data-testid="trash-icon">trash</span>
}))

vi.mock("../components/BlocklistSyntaxRef", () => ({
  BlocklistSyntaxRef: () => <div data-testid="syntax-ref">Blocklist Syntax Reference</div>
}))

// ---------------------------------------------------------------------------
// Helper — mock blocklist object
// ---------------------------------------------------------------------------

function makeBlocklist(overrides: Partial<ReturnType<typeof import("../hooks/useBlocklist").useBlocklist>> = {}) {
  return {
    rawText: "",
    setRawText: vi.fn(),
    rawLint: null,
    loading: false,
    loadRaw: vi.fn().mockResolvedValue(undefined),
    saveRaw: vi.fn().mockResolvedValue(undefined),
    lintRaw: vi.fn().mockResolvedValue(undefined),
    managedItems: [],
    managedVersion: "",
    managedLine: "",
    setManagedLine: vi.fn(),
    managedLint: null,
    loadManaged: vi.fn().mockResolvedValue(undefined),
    appendManaged: vi.fn().mockResolvedValue(undefined),
    deleteManaged: vi.fn().mockResolvedValue(undefined),
    lintManagedLine: vi.fn().mockResolvedValue(undefined),
    ...overrides
  }
}

function makeMessageApi() {
  return {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn()
  }
}

// ---------------------------------------------------------------------------
// Import component under test (after mocks)
// ---------------------------------------------------------------------------

import BlocklistStudioPanel from "../BlocklistStudioPanel"

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BlocklistStudioPanel", () => {
  let messageApi: ReturnType<typeof makeMessageApi>

  beforeEach(() => {
    vi.clearAllMocks()
    messageApi = makeMessageApi()
  })

  it("renders Managed Rules tab by default", () => {
    const blocklist = makeBlocklist()
    render(<BlocklistStudioPanel blocklist={blocklist as any} messageApi={messageApi} />)

    const managedTab = screen.getByRole("tab", { name: /managed rules/i })
    expect(managedTab).toHaveAttribute("aria-selected", "true")
  })

  it("renders Raw Editor tab and can switch to it", async () => {
    const blocklist = makeBlocklist()
    render(<BlocklistStudioPanel blocklist={blocklist as any} messageApi={messageApi} />)

    const rawTab = screen.getByRole("tab", { name: /raw editor/i })
    expect(rawTab).toHaveAttribute("aria-selected", "false")

    await userEvent.click(rawTab)
    expect(rawTab).toHaveAttribute("aria-selected", "true")
  })

  it("renders add rule form with pattern input and action selector", () => {
    const blocklist = makeBlocklist()
    render(<BlocklistStudioPanel blocklist={blocklist as any} messageApi={messageApi} />)

    expect(screen.getByTestId("pattern-input")).toBeInTheDocument()
    expect(screen.getByTestId("action-select")).toBeInTheDocument()
    expect(screen.getByText("Add Rule")).toBeInTheDocument()
  })

  it("renders syntax reference", () => {
    const blocklist = makeBlocklist()
    render(<BlocklistStudioPanel blocklist={blocklist as any} messageApi={messageApi} />)

    expect(screen.getByTestId("syntax-ref")).toBeInTheDocument()
  })

  it("shows empty state message when no rules loaded", () => {
    const blocklist = makeBlocklist({ managedItems: [] })
    render(<BlocklistStudioPanel blocklist={blocklist as any} messageApi={messageApi} />)

    expect(screen.getByTestId("empty-rules")).toBeInTheDocument()
    expect(screen.getByText(/no rules loaded/i)).toBeInTheDocument()
  })

  it("auto-loads managed rules on mount", () => {
    const blocklist = makeBlocklist()
    render(<BlocklistStudioPanel blocklist={blocklist as any} messageApi={messageApi} />)

    expect(blocklist.loadManaged).toHaveBeenCalledTimes(1)
  })

  it("renders rules table when managedItems are present", () => {
    const blocklist = makeBlocklist({
      managedItems: [
        { id: 1, line: "badword -> block #violence" },
        { id: 2, line: "/nsfw/i -> redact" }
      ]
    })
    render(<BlocklistStudioPanel blocklist={blocklist as any} messageApi={messageApi} />)

    expect(screen.getByTestId("rules-table")).toBeInTheDocument()
    expect(screen.getByText("badword")).toBeInTheDocument()
  })

  it("renders raw editor warning banner when in raw tab", async () => {
    const blocklist = makeBlocklist()
    render(<BlocklistStudioPanel blocklist={blocklist as any} messageApi={messageApi} />)

    await userEvent.click(screen.getByRole("tab", { name: /raw editor/i }))

    expect(screen.getByText(/raw file editing replaces all existing rules/i)).toBeInTheDocument()
    expect(screen.getByTestId("raw-editor")).toBeInTheDocument()
  })

  it("renders validate and add rule buttons", () => {
    const blocklist = makeBlocklist()
    render(<BlocklistStudioPanel blocklist={blocklist as any} messageApi={messageApi} />)

    expect(screen.getByRole("button", { name: /validate/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /add rule/i })).toBeInTheDocument()
  })

  it("renders syntax reference in raw editor tab too", async () => {
    const blocklist = makeBlocklist()
    render(<BlocklistStudioPanel blocklist={blocklist as any} messageApi={messageApi} />)

    await userEvent.click(screen.getByRole("tab", { name: /raw editor/i }))

    expect(screen.getByTestId("syntax-ref")).toBeInTheDocument()
  })
})
