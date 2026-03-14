import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { PersonaSetupHandoffCard } from "../PersonaSetupHandoffCard"

describe("PersonaSetupHandoffCard", () => {
  it("renders a target-tab-aware handoff and supports dismissing it", () => {
    const onDismiss = vi.fn()
    const onOpenProfiles = vi.fn()

    render(
      <PersonaSetupHandoffCard
        targetTab="profiles"
        completionType="dry_run"
        onDismiss={onDismiss}
        onOpenProfiles={onOpenProfiles}
        onOpenTestLab={vi.fn()}
        onOpenLive={vi.fn()}
        onOpenCommands={vi.fn()}
      />
    )

    expect(screen.getByText("Assistant setup complete")).toBeInTheDocument()
    expect(screen.getByText(/Completed with dry run/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Adjust assistant defaults" }))
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }))
    expect(onOpenProfiles).toHaveBeenCalledTimes(1)
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })
})
