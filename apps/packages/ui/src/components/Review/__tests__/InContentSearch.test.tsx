import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { InContentSearch, findMatches } from "../InContentSearch"

const t = (key: string, fallback: string) => fallback

describe("findMatches", () => {
  it("returns empty array for empty query", () => {
    expect(findMatches("hello world", "")).toEqual([])
    expect(findMatches("hello world", "  ")).toEqual([])
  })

  it("finds all case-insensitive matches", () => {
    const matches = findMatches("Hello hello HELLO", "hello")
    expect(matches).toHaveLength(3)
    expect(matches[0]).toEqual({ index: 0, start: 0, end: 5 })
    expect(matches[1]).toEqual({ index: 1, start: 6, end: 11 })
    expect(matches[2]).toEqual({ index: 2, start: 12, end: 17 })
  })

  it("returns empty for no matches", () => {
    expect(findMatches("hello world", "xyz")).toEqual([])
  })
})

describe("InContentSearch", () => {
  it("does not render when not visible", () => {
    const { container } = render(
      <InContentSearch
        content="test content"
        onQueryChange={vi.fn()}
        visible={false}
        onClose={vi.fn()}
        t={t}
      />
    )
    expect(container.innerHTML).toBe("")
  })

  it("renders search bar when visible", () => {
    render(
      <InContentSearch
        content="test content"
        onQueryChange={vi.fn()}
        visible={true}
        onClose={vi.fn()}
        t={t}
      />
    )
    expect(screen.getByTestId("in-content-search")).toBeInTheDocument()
    expect(screen.getByRole("textbox")).toBeInTheDocument()
  })

  it("shows match count when query entered", () => {
    render(
      <InContentSearch
        content="hello world hello again hello"
        onQueryChange={vi.fn()}
        visible={true}
        onClose={vi.fn()}
        t={t}
      />
    )
    const input = screen.getByRole("textbox")
    fireEvent.change(input, { target: { value: "hello" } })
    expect(screen.getByTestId("in-content-search-count").textContent).toBe("1/3")
  })

  it("shows 'No matches' when query has no results", () => {
    render(
      <InContentSearch
        content="hello world"
        onQueryChange={vi.fn()}
        visible={true}
        onClose={vi.fn()}
        t={t}
      />
    )
    const input = screen.getByRole("textbox")
    fireEvent.change(input, { target: { value: "xyz" } })
    expect(screen.getByTestId("in-content-search-count").textContent).toBe("No matches")
  })

  it("calls onQueryChange when typing", () => {
    const onQueryChange = vi.fn()
    render(
      <InContentSearch
        content="hello world"
        onQueryChange={onQueryChange}
        visible={true}
        onClose={vi.fn()}
        t={t}
      />
    )
    const input = screen.getByRole("textbox")
    fireEvent.change(input, { target: { value: "hello" } })
    expect(onQueryChange).toHaveBeenCalledWith("hello")
  })

  it("closes on Escape key", () => {
    const onClose = vi.fn()
    render(
      <InContentSearch
        content="hello"
        onQueryChange={vi.fn()}
        visible={true}
        onClose={onClose}
        t={t}
      />
    )
    const input = screen.getByRole("textbox")
    fireEvent.keyDown(input, { key: "Escape" })
    expect(onClose).toHaveBeenCalled()
  })

  it("navigates with Enter and Shift+Enter", () => {
    render(
      <InContentSearch
        content="aaa aaa aaa"
        onQueryChange={vi.fn()}
        visible={true}
        onClose={vi.fn()}
        t={t}
      />
    )
    const input = screen.getByRole("textbox")
    fireEvent.change(input, { target: { value: "aaa" } })
    // Initially at 1/3
    expect(screen.getByTestId("in-content-search-count").textContent).toBe("1/3")
    // Enter goes to next
    fireEvent.keyDown(input, { key: "Enter" })
    expect(screen.getByTestId("in-content-search-count").textContent).toBe("2/3")
    // Shift+Enter goes back
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true })
    expect(screen.getByTestId("in-content-search-count").textContent).toBe("1/3")
  })

  it("close button resets query and calls onClose", () => {
    const onClose = vi.fn()
    const onQueryChange = vi.fn()
    render(
      <InContentSearch
        content="hello"
        onQueryChange={onQueryChange}
        visible={true}
        onClose={onClose}
        t={t}
      />
    )
    const closeBtn = screen.getByRole("button", { name: "Close search" })
    fireEvent.click(closeBtn)
    expect(onClose).toHaveBeenCalled()
    expect(onQueryChange).toHaveBeenCalledWith("")
  })
})
