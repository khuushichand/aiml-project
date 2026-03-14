import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { SetupSafetyConnectionsStep } from "../SetupSafetyConnectionsStep"

describe("SetupSafetyConnectionsStep", () => {
  it("requires an explicit confirmation and connection choice before continuing", () => {
    render(
      <SetupSafetyConnectionsStep
        saving={false}
        currentConfirmationMode="destructive_only"
        onContinue={vi.fn()}
      />
    )

    expect(screen.getByRole("button", { name: "Save safety choices" })).toBeDisabled()

    fireEvent.click(screen.getByRole("button", { name: "Ask for destructive actions" }))
    expect(screen.getByRole("button", { name: "Save safety choices" })).toBeDisabled()

    fireEvent.click(screen.getByRole("button", { name: "No external connections for now" }))
    expect(screen.getByRole("button", { name: "Save safety choices" })).toBeEnabled()
  })

  it("submits an explicit no-connection safety choice", () => {
    const onContinue = vi.fn()

    render(
      <SetupSafetyConnectionsStep
        saving={false}
        currentConfirmationMode="destructive_only"
        onContinue={onContinue}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Always ask before actions" }))
    fireEvent.click(screen.getByRole("button", { name: "No external connections for now" }))
    fireEvent.click(screen.getByRole("button", { name: "Save safety choices" }))

    expect(onContinue).toHaveBeenCalledWith({
      confirmationMode: "always",
      connectionMode: "none"
    })
  })

  it("submits a lightweight connection draft when requested", () => {
    const onContinue = vi.fn()

    render(
      <SetupSafetyConnectionsStep
        saving={false}
        currentConfirmationMode="destructive_only"
        onContinue={onContinue}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Never ask" }))
    fireEvent.click(screen.getByRole("button", { name: "Add one connection now" }))
    fireEvent.change(screen.getByPlaceholderText("Connection name"), {
      target: { value: "Slack Alerts" }
    })
    fireEvent.change(screen.getByPlaceholderText("Base URL"), {
      target: { value: "https://hooks.example.com/incoming" }
    })
    fireEvent.change(screen.getByLabelText("Authentication"), {
      target: { value: "bearer" }
    })
    fireEvent.change(screen.getByPlaceholderText("Secret (optional)"), {
      target: { value: "token-123" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Save safety and connection" }))

    expect(onContinue).toHaveBeenCalledWith({
      confirmationMode: "never",
      connectionMode: "create",
      connection: {
        name: "Slack Alerts",
        baseUrl: "https://hooks.example.com/incoming",
        authType: "bearer",
        secret: "token-123"
      }
    })
  })

  it("exposes labeled fields and masks connection secrets", () => {
    render(
      <SetupSafetyConnectionsStep
        saving={false}
        currentConfirmationMode="destructive_only"
        onContinue={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Never ask" }))
    fireEvent.click(screen.getByRole("button", { name: "Add one connection now" }))

    expect(screen.getByLabelText("Connection name")).toHaveAttribute("type", "text")
    expect(screen.getByLabelText("Base URL")).toHaveAttribute("type", "text")
    expect(screen.getByLabelText("Connection secret")).toHaveAttribute(
      "type",
      "password"
    )
  })
})
