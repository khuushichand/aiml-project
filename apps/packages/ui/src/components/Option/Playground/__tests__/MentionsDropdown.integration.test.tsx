// @vitest-environment jsdom
import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { MentionsDropdown } from "../MentionsDropdown"
import type { TabInfo } from "~/hooks/useTabMentions"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key
  })
}))

const createTabs = (): TabInfo[] => [
  {
    id: 1,
    title: "Design doc",
    url: "https://docs.example.com/design"
  },
  {
    id: 2,
    title: "API reference",
    url: "https://api.example.com/reference"
  },
  {
    id: 3,
    title: "Release notes",
    url: "https://docs.example.com/release"
  }
]

const renderDropdown = (
  overrides: Partial<React.ComponentProps<typeof MentionsDropdown>> = {}
) => {
  const textarea = document.createElement("textarea")
  document.body.appendChild(textarea)
  const textareaRef = { current: textarea } as React.RefObject<HTMLTextAreaElement>
  const props: React.ComponentProps<typeof MentionsDropdown> = {
    show: true,
    tabs: createTabs(),
    mentionPosition: { start: 0, end: 3, query: "doc" },
    onSelectTab: vi.fn(),
    onClose: vi.fn(),
    textareaRef,
    refetchTabs: vi.fn().mockResolvedValue(undefined),
    onMentionsOpen: vi.fn().mockResolvedValue(undefined),
    ...overrides
  }
  const view = render(<MentionsDropdown {...props} />)
  return { ...view, props }
}

describe("MentionsDropdown integration", () => {
  it("groups tabs by hostname category and renders listbox semantics", () => {
    renderDropdown()

    expect(screen.getByRole("listbox", { name: "Tab mention suggestions" })).toBeInTheDocument()
    expect(screen.getByTestId("mentions-category-docs.example.com")).toBeInTheDocument()
    expect(screen.getByTestId("mentions-category-api.example.com")).toBeInTheDocument()
  })

  it("supports keyboard traversal, selection, and escape close", () => {
    const onSelectTab = vi.fn()
    const onClose = vi.fn()
    renderDropdown({ onSelectTab, onClose })

    fireEvent.keyDown(document, { key: "ArrowDown" })
    fireEvent.keyDown(document, { key: "Enter" })

    expect(onSelectTab).toHaveBeenCalledWith(
      expect.objectContaining({ id: 2, title: "API reference" })
    )

    fireEvent.keyDown(document, { key: "Escape" })
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
