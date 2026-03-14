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

  it("blocks continue when the base url is malformed", () => {
    render(
      <SetupSafetyConnectionsStep
        saving={false}
        currentConfirmationMode="destructive_only"
        onContinue={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Never ask" }))
    fireEvent.click(screen.getByRole("button", { name: "Add one connection now" }))
    fireEvent.change(screen.getByLabelText("Connection name"), {
      target: { value: "Slack Alerts" }
    })
    fireEvent.change(screen.getByLabelText("Base URL"), {
      target: { value: "not-a-url" }
    })

    expect(screen.getByText("Enter a valid http or https URL.")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Save safety and connection" })).toBeDisabled()
  })

  it("shows a non-blocking endpoint note for urls with a path", () => {
    render(
      <SetupSafetyConnectionsStep
        saving={false}
        currentConfirmationMode="destructive_only"
        onContinue={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Never ask" }))
    fireEvent.click(screen.getByRole("button", { name: "Add one connection now" }))
    fireEvent.change(screen.getByLabelText("Connection name"), {
      target: { value: "Slack Alerts" }
    })
    fireEvent.change(screen.getByLabelText("Base URL"), {
      target: { value: "https://hooks.example.com/incoming?source=setup" }
    })

    expect(
      screen.getByText(
        "This endpoint includes a path, query, or fragment, which is common for webhook-style integrations."
      )
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Save safety and connection" })).toBeEnabled()
  })

  it("warns when bearer auth has no secret but still allows continue", () => {
    render(
      <SetupSafetyConnectionsStep
        saving={false}
        currentConfirmationMode="destructive_only"
        onContinue={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Never ask" }))
    fireEvent.click(screen.getByRole("button", { name: "Add one connection now" }))
    fireEvent.change(screen.getByLabelText("Connection name"), {
      target: { value: "Slack Alerts" }
    })
    fireEvent.change(screen.getByLabelText("Base URL"), {
      target: { value: "https://hooks.example.com/incoming" }
    })
    fireEvent.change(screen.getByLabelText("Authentication"), {
      target: { value: "bearer" }
    })

    expect(
      screen.getByText(
        "This connection will be created without a bearer token. You can add one later in Connections."
      )
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Save safety and connection" })).toBeEnabled()
  })

  it("does not offer custom header auth in setup", () => {
    render(
      <SetupSafetyConnectionsStep
        saving={false}
        currentConfirmationMode="destructive_only"
        onContinue={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Never ask" }))
    fireEvent.click(screen.getByRole("button", { name: "Add one connection now" }))

    expect(screen.getByRole("option", { name: "None" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "Bearer token" })).toBeInTheDocument()
    expect(
      screen.queryByRole("option", { name: "Custom header" })
    ).not.toBeInTheDocument()
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

  it("renders a step-local safety error while keeping the explicit skip path available", () => {
    const onContinue = vi.fn()

    render(
      <SetupSafetyConnectionsStep
        saving={false}
        error="Failed to save assistant safety settings"
        currentConfirmationMode="destructive_only"
        onContinue={onContinue}
      />
    )

    expect(screen.getByText("Failed to save assistant safety settings")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Ask for destructive actions" }))
    fireEvent.click(screen.getByRole("button", { name: "No external connections for now" }))
    fireEvent.click(screen.getByRole("button", { name: "Save safety choices" }))

    expect(onContinue).toHaveBeenCalledWith({
      confirmationMode: "destructive_only",
      connectionMode: "none"
    })
  })
})
