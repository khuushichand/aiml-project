import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("../McpToolPicker", () => ({
  McpToolPicker: ({
    value,
    onChange
  }: {
    value: string
    onChange: (value: string) => void
  }) => (
    <input
      aria-label="MCP tool"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}))

import { SetupStarterCommandsStep } from "../SetupStarterCommandsStep"

describe("SetupStarterCommandsStep", () => {
  it("renders starter templates and an explicit skip action", () => {
    render(
      <SetupStarterCommandsStep
        saving={false}
        onCreateFromTemplate={vi.fn()}
        onCreateMcpStarter={vi.fn()}
        onSkip={vi.fn()}
      />
    )

    expect(screen.getByText("Starter commands")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Search Notes" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Create Note" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Search Library" })).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Continue without starter commands" })
    ).toBeInTheDocument()
  })

  it("creates a starter command from a shared template", () => {
    const onCreateFromTemplate = vi.fn()

    render(
      <SetupStarterCommandsStep
        saving={false}
        onCreateFromTemplate={onCreateFromTemplate}
        onCreateMcpStarter={vi.fn()}
        onSkip={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Search Notes" }))

    expect(onCreateFromTemplate).toHaveBeenCalledWith("notes-search")
  })

  it("creates an MCP-backed starter command from an explicit tool and phrase", () => {
    const onCreateMcpStarter = vi.fn()

    render(
      <SetupStarterCommandsStep
        saving={false}
        onCreateFromTemplate={vi.fn()}
        onCreateMcpStarter={onCreateMcpStarter}
        onSkip={vi.fn()}
      />
    )

    fireEvent.change(screen.getByLabelText("MCP tool"), {
      target: { value: "notes.search" }
    })
    fireEvent.change(screen.getByPlaceholderText("Phrase users can say"), {
      target: { value: "search notes for {topic}" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Add MCP starter" }))

    expect(onCreateMcpStarter).toHaveBeenCalledWith(
      "notes.search",
      "search notes for {topic}"
    )
  })
})
