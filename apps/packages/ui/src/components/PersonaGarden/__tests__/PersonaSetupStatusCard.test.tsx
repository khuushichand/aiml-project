import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { PersonaSetupStatusCard } from "../PersonaSetupStatusCard"

describe("PersonaSetupStatusCard", () => {
  it("shows a not-started state with a start setup action", () => {
    const onStartSetup = vi.fn()

    render(
      <PersonaSetupStatusCard
        setup={null}
        progressItems={[]}
        onStartSetup={onStartSetup}
      />
    )

    expect(screen.getByText("Not started")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Start setup" }))
    expect(onStartSetup).toHaveBeenCalledTimes(1)
  })

  it("shows an in-progress state with resume and reset actions", () => {
    const onResumeSetup = vi.fn()
    const onResetSetup = vi.fn()

    render(
      <PersonaSetupStatusCard
        setup={{
          status: "in_progress",
          version: 1,
          current_step: "commands",
          completed_steps: ["persona", "voice"],
          completed_at: null,
          last_test_type: null
        }}
        progressItems={[
          {
            step: "commands",
            label: "Starter commands",
            status: "current",
            summary: "Starter commands selected"
          }
        ]}
        onResumeSetup={onResumeSetup}
        onResetSetup={onResetSetup}
      />
    )

    expect(screen.getByText("In progress")).toBeInTheDocument()
    expect(screen.getByText("Current step: Starter commands")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Resume setup" }))
    fireEvent.click(screen.getByRole("button", { name: "Reset setup" }))
    expect(onResumeSetup).toHaveBeenCalledTimes(1)
    expect(onResetSetup).toHaveBeenCalledTimes(1)
  })

  it("shows a completed state with completion path and rerun action", () => {
    const onRerunSetup = vi.fn()

    render(
      <PersonaSetupStatusCard
        setup={{
          status: "completed",
          version: 1,
          current_step: "test",
          completed_steps: ["persona", "voice", "commands", "safety", "test"],
          completed_at: "2026-03-13T10:00:00Z",
          last_test_type: "dry_run"
        }}
        progressItems={[]}
        onRerunSetup={onRerunSetup}
      />
    )

    expect(screen.getByText("Completed")).toBeInTheDocument()
    expect(screen.getByText("Completed with dry run")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Rerun setup" }))
    expect(onRerunSetup).toHaveBeenCalledTimes(1)
  })
})
