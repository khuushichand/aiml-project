// @vitest-environment jsdom

import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { MemoryRouter } from "react-router-dom"

import { CompanionHomeCardShell } from "../cards/CardShell"

describe("CompanionHomeCardShell", () => {
  it("uses the state subtitle when an empty card has a state", () => {
    render(
      <MemoryRouter>
        <CompanionHomeCardShell
          title="Inbox Preview"
          items={[]}
          emptyLabel="Inbox is clear"
          emptyDescription="Authoritative companion notifications will show up here first."
          state={{
            label: "Setup required",
            description: "Connect Companion Home before inbox items can appear."
          }}
        />
      </MemoryRouter>
    )

    expect(screen.queryByText("Nothing urgent right now.")).toBeNull()
    expect(screen.getAllByText("Setup required")).toHaveLength(2)
    expect(
      screen.getByText("Connect Companion Home before inbox items can appear.")
    ).toBeInTheDocument()
  })
})
