import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { SetupTestAndFinishStep } from "../SetupTestAndFinishStep"

describe("SetupTestAndFinishStep", () => {
  it("runs a dry-run test and exposes a finish action after a result is present", () => {
    const onRunDryRun = vi.fn()
    const onFinishWithDryRun = vi.fn()

    const { rerender } = render(
      <SetupTestAndFinishStep
        saving={false}
        dryRunLoading={false}
        liveConnected={false}
        outcome={null}
        onRunDryRun={onRunDryRun}
        onConnectLive={vi.fn()}
        onSendLive={vi.fn()}
        onFinishWithDryRun={onFinishWithDryRun}
        onFinishWithLiveSession={vi.fn()}
      />
    )

    fireEvent.change(screen.getByPlaceholderText("Try a spoken phrase"), {
      target: { value: "search notes for embeddings" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Run dry-run test" }))

    expect(onRunDryRun).toHaveBeenCalledWith("search notes for embeddings")

    rerender(
      <SetupTestAndFinishStep
        saving={false}
        dryRunLoading={false}
        liveConnected={false}
        outcome={{
          kind: "dry_run_match",
          heardText: "search notes for embeddings",
          commandName: "Search Notes"
        }}
        onRunDryRun={onRunDryRun}
        onConnectLive={vi.fn()}
        onSendLive={vi.fn()}
        onFinishWithDryRun={onFinishWithDryRun}
        onFinishWithLiveSession={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Finish with dry-run test" }))
    expect(onFinishWithDryRun).toHaveBeenCalled()
  })

  it("supports the live-session path and finish action once a response has arrived", () => {
    const onConnectLive = vi.fn()
    const onSendLive = vi.fn()
    const onFinishWithLiveSession = vi.fn()

    const { rerender } = render(
      <SetupTestAndFinishStep
        saving={false}
        dryRunLoading={false}
        liveConnected={false}
        outcome={null}
        onRunDryRun={vi.fn()}
        onConnectLive={onConnectLive}
        onSendLive={onSendLive}
        onFinishWithDryRun={vi.fn()}
        onFinishWithLiveSession={onFinishWithLiveSession}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Connect live session" }))
    expect(onConnectLive).toHaveBeenCalled()

    rerender(
      <SetupTestAndFinishStep
        saving={false}
        dryRunLoading={false}
        liveConnected
        outcome={{
          kind: "live_success",
          text: "summarize my assistant setup",
          responseText: "Here is the answer from the live session."
        }}
        onRunDryRun={vi.fn()}
        onConnectLive={onConnectLive}
        onSendLive={onSendLive}
        onFinishWithDryRun={vi.fn()}
        onFinishWithLiveSession={onFinishWithLiveSession}
      />
    )

    fireEvent.change(screen.getByPlaceholderText("Try a live message"), {
      target: { value: "summarize my assistant setup" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Send live test" }))
    expect(onSendLive).toHaveBeenCalledWith("summarize my assistant setup")

    fireEvent.click(screen.getByRole("button", { name: "Finish with live session" }))
    expect(onFinishWithLiveSession).toHaveBeenCalled()
  })

  it("renders a dry-run no-match outcome with a forward action", () => {
    const onCreateCommandFromPhrase = vi.fn()

    render(
      <SetupTestAndFinishStep
        saving={false}
        dryRunLoading={false}
        liveConnected={false}
        outcome={{
          kind: "dry_run_no_match",
          heardText: "open the pod bay doors"
        }}
        onRunDryRun={vi.fn()}
        onConnectLive={vi.fn()}
        onSendLive={vi.fn()}
        onFinishWithDryRun={vi.fn()}
        onFinishWithLiveSession={vi.fn()}
        onCreateCommandFromPhrase={onCreateCommandFromPhrase}
      />
    )

    expect(screen.getByText(/No direct command matched/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Create command from this phrase" }))
    expect(onCreateCommandFromPhrase).toHaveBeenCalledWith("open the pod bay doors")
    expect(screen.getByRole("button", { name: "Connect live session" })).toBeInTheDocument()
  })

  it("renders a live-unavailable outcome separately from live-success", () => {
    const { rerender } = render(
      <SetupTestAndFinishStep
        saving={false}
        dryRunLoading={false}
        liveConnected={false}
        outcome={{ kind: "live_unavailable" }}
        onRunDryRun={vi.fn()}
        onConnectLive={vi.fn()}
        onSendLive={vi.fn()}
        onFinishWithDryRun={vi.fn()}
        onFinishWithLiveSession={vi.fn()}
      />
    )

    expect(screen.getByText(/Live session unavailable until you connect/i)).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Finish with live session" })
    ).not.toBeInTheDocument()

    rerender(
      <SetupTestAndFinishStep
        saving={false}
        dryRunLoading={false}
        liveConnected
        outcome={{
          kind: "live_success",
          text: "summarize my assistant setup",
          responseText: "Here is the answer from the live session."
        }}
        onRunDryRun={vi.fn()}
        onConnectLive={vi.fn()}
        onSendLive={vi.fn()}
        onFinishWithDryRun={vi.fn()}
        onFinishWithLiveSession={vi.fn()}
      />
    )

    expect(screen.getByText(/Live session responded/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Finish with live session" })).toBeInTheDocument()
  })

  it("renders a live-send failure outcome with retry guidance", () => {
    render(
      <SetupTestAndFinishStep
        saving={false}
        dryRunLoading={false}
        liveConnected
        outcome={{
          kind: "live_failure",
          text: "summarize my assistant setup",
          message: "Socket send failed"
        }}
        onRunDryRun={vi.fn()}
        onConnectLive={vi.fn()}
        onSendLive={vi.fn()}
        onFinishWithDryRun={vi.fn()}
        onFinishWithLiveSession={vi.fn()}
      />
    )

    expect(screen.getByText("Socket send failed")).toBeInTheDocument()
    expect(
      screen.getByText("Try sending the live test again or reconnect the live session.")
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Send live test" })).toBeInTheDocument()
  })

  it("renders a local test-step error banner separately from structured outcomes", () => {
    render(
      <SetupTestAndFinishStep
        saving={false}
        dryRunLoading={false}
        liveConnected={false}
        error="Failed to finish assistant setup"
        outcome={null}
        onRunDryRun={vi.fn()}
        onConnectLive={vi.fn()}
        onSendLive={vi.fn()}
        onFinishWithDryRun={vi.fn()}
        onFinishWithLiveSession={vi.fn()}
      />
    )

    expect(screen.getByText("Failed to finish assistant setup")).toBeInTheDocument()
  })

  it("restores the dry-run phrase and shows a resume note when setup returns from commands", () => {
    render(
      <SetupTestAndFinishStep
        saving={false}
        dryRunLoading={false}
        liveConnected={false}
        initialHeardText="open the pod bay doors"
        notice="Command saved. Run the same phrase again to confirm setup."
        outcome={null}
        onRunDryRun={vi.fn()}
        onConnectLive={vi.fn()}
        onSendLive={vi.fn()}
        onFinishWithDryRun={vi.fn()}
        onFinishWithLiveSession={vi.fn()}
      />
    )

    expect(screen.getByPlaceholderText("Try a spoken phrase")).toHaveValue(
      "open the pod bay doors"
    )
    expect(
      screen.getByText("Command saved. Run the same phrase again to confirm setup.")
    ).toBeInTheDocument()
  })
})
