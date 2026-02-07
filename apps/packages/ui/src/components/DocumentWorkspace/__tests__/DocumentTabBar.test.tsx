import { describe, it, expect, beforeEach, afterEach, vi } from "vitest"
import { render, screen, cleanup, within } from "@testing-library/react"
import type { ReactNode } from "react"
import { DocumentTabBar } from "../DocumentTabBar"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import type { OpenDocument } from "../types"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: string) => defaultValue || _key
  })
}))

vi.mock("antd", () => ({
  Tooltip: ({ children }: { children: ReactNode }) => <>{children}</>
}))

describe("DocumentTabBar accessibility", () => {
  beforeEach(() => {
    if (!Element.prototype.scrollIntoView) {
      Element.prototype.scrollIntoView = vi.fn()
    }
  })

  afterEach(() => {
    cleanup()
    useDocumentWorkspaceStore.getState().reset()
    vi.clearAllMocks()
  })

  it("keeps the open button outside the tablist", () => {
    const openDocuments: OpenDocument[] = [
      { id: 1, title: "First Doc", type: "pdf" },
      { id: 2, title: "Second Doc", type: "epub" }
    ]

    useDocumentWorkspaceStore.setState({
      openDocuments,
      activeDocumentId: 1
    })

    render(<DocumentTabBar onOpenPicker={vi.fn()} />)

    const tablist = screen.getByRole("tablist", { name: "Open documents" })
    const openButton = screen.getByRole("button", { name: "Open document" })

    expect(within(tablist).getAllByRole("tab")).toHaveLength(openDocuments.length)
    expect(tablist.contains(openButton)).toBe(false)
  })
})
