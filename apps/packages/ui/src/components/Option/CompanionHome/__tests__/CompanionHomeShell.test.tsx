// @vitest-environment jsdom

import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"

vi.mock("../CompanionHomePage", () => ({
  CompanionHomePage: ({ surface }: { surface: "options" | "sidepanel" }) => (
    <div data-testid="companion-home-page">{surface}</div>
  )
}))

import { CompanionHomeShell } from "../CompanionHomeShell"

describe("CompanionHomeShell", () => {
  it("renders functional quick actions for the options surface", () => {
    render(
      <MemoryRouter>
        <CompanionHomeShell surface="options" />
      </MemoryRouter>
    )

    expect(screen.getByTestId("companion-home-shell")).toBeInTheDocument()
    expect(screen.getByTestId("companion-home-page")).toHaveTextContent("options")
    expect(screen.getByRole("link", { name: /Open Chat/i })).toHaveAttribute(
      "href",
      "/chat"
    )
    expect(screen.getByRole("link", { name: /Open Knowledge/i })).toHaveAttribute(
      "href",
      "/knowledge"
    )
  })

  it("offers a forced-chat escape hatch on the sidepanel surface", () => {
    render(
      <MemoryRouter>
        <CompanionHomeShell surface="sidepanel" />
      </MemoryRouter>
    )

    expect(screen.getByTestId("companion-home-page")).toHaveTextContent("sidepanel")
    expect(screen.getByRole("link", { name: /Open Chat/i })).toHaveAttribute(
      "href",
      "/?view=chat"
    )
    expect(screen.getByRole("link", { name: /Open Settings/i })).toHaveAttribute(
      "href",
      "/settings"
    )
  })
})
