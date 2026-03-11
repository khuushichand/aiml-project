import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import OptionWritingPlayground from "../option-writing-playground"

vi.mock("~/components/Layouts/Layout", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="option-layout">{children}</div>
  )
}))

vi.mock("@/components/Option/WritingPlayground", () => ({
  WritingPlayground: () => <div data-testid="writing-playground">Writing</div>
}))

describe("option writing playground route", () => {
  it("uses flex sizing instead of a hardcoded header-height calc wrapper", () => {
    render(<OptionWritingPlayground />)

    const shell = screen.getByTestId("writing-playground-route-shell")
    expect(shell.className).toContain("flex")
    expect(shell.className).toContain("flex-1")
    expect(shell.className).toContain("min-h-0")
    expect(shell.className).toContain("overflow-hidden")
    expect(shell.className).not.toContain("64px")
    expect(screen.getByTestId("writing-playground")).toBeVisible()
  })
})
