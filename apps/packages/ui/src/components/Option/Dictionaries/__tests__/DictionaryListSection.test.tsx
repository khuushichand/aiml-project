import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { DictionaryListSection } from "../components/DictionaryListSection"

if (typeof window.ResizeObserver === "undefined") {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  ;(window as any).ResizeObserver = ResizeObserverMock
  ;(globalThis as any).ResizeObserver = ResizeObserverMock
}

if (!window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false
    })
  })
}

describe("DictionaryListSection", () => {
  const baseProps = {
    dictionarySearch: "",
    onDictionarySearchChange: vi.fn(),
    categoryFilter: "",
    onCategoryFilterChange: vi.fn(),
    tagFilters: [],
    onTagFiltersChange: vi.fn(),
    categoryFilterOptions: ["Clinical"],
    tagFilterOptions: ["urgent", "medical"],
    onOpenImport: vi.fn(),
    onOpenCreate: vi.fn(),
    status: "success" as const,
    dictionariesUnsupported: false,
    unsupportedTitle: "Unsupported",
    unsupportedDescription: "Unsupported description",
    unsupportedPrimaryActionLabel: "Health & diagnostics",
    onOpenHealthDiagnostics: vi.fn(),
    data: [
      {
        id: 1,
        name: "Clinical Terms",
        description: "Medical mapping"
      }
    ],
    filteredDictionaries: [
      {
        id: 1,
        name: "Clinical Terms",
        description: "Medical mapping"
      }
    ],
    columns: [
      {
        title: "Name",
        dataIndex: "name",
        key: "name"
      }
    ],
    error: null,
    onRetry: vi.fn()
  }

  it("routes search/create/import actions from the header controls", async () => {
    const user = userEvent.setup()
    const onDictionarySearchChange = vi.fn()
    const onCategoryFilterChange = vi.fn()
    const onTagFiltersChange = vi.fn()
    const onOpenImport = vi.fn()
    const onOpenCreate = vi.fn()

    render(
      <DictionaryListSection
        {...baseProps}
        onDictionarySearchChange={onDictionarySearchChange}
        onCategoryFilterChange={onCategoryFilterChange}
        onTagFiltersChange={onTagFiltersChange}
        onOpenImport={onOpenImport}
        onOpenCreate={onOpenCreate}
      />
    )

    await user.type(
      screen.getByRole("textbox", { name: "Search dictionaries" }),
      "clinical"
    )
    expect(onDictionarySearchChange).toHaveBeenCalled()

    await user.click(
      screen.getByRole("combobox", { name: "Filter dictionaries by category" })
    )
    await user.click(
      await screen.findByText("Clinical", {
        selector: ".ant-select-item-option-content"
      })
    )
    expect(onCategoryFilterChange).toHaveBeenCalled()

    await user.click(
      screen.getByRole("combobox", { name: "Filter dictionaries by tags" })
    )
    await user.click(
      await screen.findByText("urgent", {
        selector: ".ant-select-item-option-content"
      })
    )
    expect(onTagFiltersChange).toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "Import" }))
    expect(onOpenImport).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole("button", { name: "New Dictionary" }))
    expect(onOpenCreate).toHaveBeenCalledTimes(1)
  })

  it("renders unsupported-state action when dictionaries API is unavailable", async () => {
    const user = userEvent.setup()
    const onOpenHealthDiagnostics = vi.fn()

    render(
      <DictionaryListSection
        {...baseProps}
        dictionariesUnsupported
        unsupportedTitle="Chat dictionaries API not available on this server"
        unsupportedDescription="Upgrade server to use dictionaries."
        status="success"
        onOpenHealthDiagnostics={onOpenHealthDiagnostics}
      />
    )

    expect(
      screen.getByText("Chat dictionaries API not available on this server")
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole("button", { name: "Health & diagnostics" })
    )
    expect(onOpenHealthDiagnostics).toHaveBeenCalledTimes(1)
  })
})
