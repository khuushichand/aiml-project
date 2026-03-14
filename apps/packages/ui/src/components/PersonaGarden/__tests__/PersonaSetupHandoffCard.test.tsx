import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { PersonaSetupHandoffCard } from "../PersonaSetupHandoffCard"

const defaultReviewSummary = {
  starterCommands: { mode: "added" as const, count: 3 },
  confirmationMode: "destructive_only" as const,
  connection: { mode: "created" as const, name: "Slack Alerts" }
}

describe("PersonaSetupHandoffCard", () => {
  it("prioritizes trying a live turn after dry-run completion", () => {
    render(
      <PersonaSetupHandoffCard
        targetTab="profiles"
        completionType="dry_run"
        reviewSummary={defaultReviewSummary}
        recommendedAction="try_live"
        onDismiss={vi.fn()}
        onOpenProfiles={vi.fn()}
        onOpenTestLab={vi.fn()}
        onOpenLive={vi.fn()}
        onOpenCommands={vi.fn()}
        onOpenConnections={vi.fn()}
      />
    )

    expect(screen.getByText("Recommended next step")).toBeInTheDocument()
    expect(screen.getByText("Try your first live turn")).toBeInTheDocument()
  })

  it("renders starter pack review details and target-tab-aware actions", () => {
    const onDismiss = vi.fn()
    const onOpenProfiles = vi.fn()
    const onOpenCommands = vi.fn()
    const onOpenConnections = vi.fn()

    render(
      <PersonaSetupHandoffCard
        targetTab="profiles"
        completionType="dry_run"
        reviewSummary={defaultReviewSummary}
        recommendedAction="add_connection"
        onDismiss={onDismiss}
        onOpenProfiles={onOpenProfiles}
        onOpenTestLab={vi.fn()}
        onOpenLive={vi.fn()}
        onOpenCommands={onOpenCommands}
        onOpenConnections={onOpenConnections}
      />
    )

    expect(screen.getByText("Assistant setup complete")).toBeInTheDocument()
    expect(screen.getByText(/Completed with dry run/i)).toBeInTheDocument()
    expect(screen.getByText("Starter pack review")).toBeInTheDocument()
    expect(screen.getByText("Added 3 starter commands")).toBeInTheDocument()
    expect(screen.getByText("Ask for destructive actions")).toBeInTheDocument()
    expect(screen.getByText("Connection added: Slack Alerts")).toBeInTheDocument()
    expect(screen.getByText("Add a connection")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Review commands" }))
    fireEvent.click(screen.getByRole("button", { name: "Open connections" }))
    fireEvent.click(screen.getByRole("button", { name: "Review safety defaults" }))
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }))
    expect(onOpenCommands).toHaveBeenCalledTimes(1)
    expect(onOpenConnections).toHaveBeenCalledTimes(1)
    expect(onOpenProfiles).toHaveBeenCalledTimes(1)
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it("renders skipped starter pack items for live-session completion", () => {
    render(
      <PersonaSetupHandoffCard
        targetTab="live"
        completionType="live_session"
        reviewSummary={{
          starterCommands: { mode: "skipped" },
          confirmationMode: "never",
          connection: { mode: "skipped" }
        }}
        recommendedAction="add_command"
        onDismiss={vi.fn()}
        onOpenProfiles={vi.fn()}
        onOpenTestLab={vi.fn()}
        onOpenLive={vi.fn()}
        onOpenCommands={vi.fn()}
        onOpenConnections={vi.fn()}
      />
    )

    expect(screen.getByText(/Completed with live session/i)).toBeInTheDocument()
    expect(screen.getByText("Skipped starter commands")).toBeInTheDocument()
    expect(screen.getByText("Never ask")).toBeInTheDocument()
    expect(screen.getByText("No external connection yet")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Open Commands" })).toBeInTheDocument()
  })

  it("renders a compact variant with the recommended next step", () => {
    const onOpenCommands = vi.fn()

    render(
      <PersonaSetupHandoffCard
        targetTab="test-lab"
        completionType="dry_run"
        reviewSummary={defaultReviewSummary}
        recommendedAction="review_commands"
        compact
        onDismiss={vi.fn()}
        onOpenProfiles={vi.fn()}
        onOpenTestLab={vi.fn()}
        onOpenLive={vi.fn()}
        onOpenCommands={onOpenCommands}
        onOpenConnections={vi.fn()}
      />
    )

    expect(screen.getByText("Setup complete")).toBeInTheDocument()
    expect(screen.getByText("Review starter commands")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Review Commands" }))

    expect(onOpenCommands).toHaveBeenCalledTimes(1)
  })
})
