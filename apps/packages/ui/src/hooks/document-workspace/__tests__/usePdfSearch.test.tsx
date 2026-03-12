import React from "react"
import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { usePdfSearch, type PdfDocumentProxy } from "@/hooks/document-workspace/usePdfSearch"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"

type MockPdfDocument = PdfDocumentProxy & {
  numPages: number
  getPage: (pageNumber: number) => Promise<{
    getTextContent: () => Promise<{
      items: Array<{ str: string; transform: number[] }>
    }>
  }>
}

const createPdfDocument = (pages: string[][]): MockPdfDocument =>
  ({
    numPages: pages.length,
    getPage: vi.fn(async (pageNumber: number) => ({
      getTextContent: vi.fn(async () => ({
        items: pages[pageNumber - 1].map((text) => ({ str: text, transform: [] }))
      }))
    }))
  }) as unknown as MockPdfDocument

describe("usePdfSearch", () => {
  let initialStore: ReturnType<typeof useDocumentWorkspaceStore.getState>

  beforeEach(() => {
    initialStore = useDocumentWorkspaceStore.getState()
    useDocumentWorkspaceStore.setState({
      searchOpen: false,
      searchQuery: "",
      searchResults: [],
      activeSearchIndex: 0,
      searchMatchCase: false,
      searchWordBoundary: false
    })

    document.body.innerHTML = `
      <div data-page-number="1">
        <div class="react-pdf__Page__textContent">
          <span>Cat</span>
          <span>catalog</span>
          <span>cat</span>
        </div>
      </div>
    `

    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn()
    })
  })

  afterEach(() => {
    useDocumentWorkspaceStore.setState(initialStore, true)
    document.body.innerHTML = ""
    vi.restoreAllMocks()
  })

  it("keeps highlighted spans aligned with case-sensitive whole-word search results", async () => {
    const pdfDocumentRef = {
      current: createPdfDocument([["Cat", "catalog", "cat"]])
    } as React.RefObject<PdfDocumentProxy | null>

    const { result } = renderHook(() => usePdfSearch(pdfDocumentRef))

    await act(async () => {
      result.current.openSearch()
      await Promise.resolve()
    })

    act(() => {
      useDocumentWorkspaceStore.setState({
        searchMatchCase: true,
        searchWordBoundary: true
      })
      result.current.setSearchQuery("Cat")
    })

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 350))
    })

    await waitFor(() => {
      expect(useDocumentWorkspaceStore.getState().searchResults).toHaveLength(1)
    })

    const spans = Array.from(document.querySelectorAll(".react-pdf__Page__textContent span"))
    const highlightedTexts = spans
      .filter((span) => span.classList.contains("pdf-search-match"))
      .map((span) => span.textContent)

    expect(highlightedTexts).toEqual(["Cat"])
  })
})
