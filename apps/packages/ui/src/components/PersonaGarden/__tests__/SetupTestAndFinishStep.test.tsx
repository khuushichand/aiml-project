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
        dryRunError={null}
        dryRunResult={null}
        liveConnected={false}
        liveSuccessText={null}
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
        dryRunError={null}
        dryRunResult={{
          heardText: "search notes for embeddings",
          matched: true,
          commandName: "Search Notes"
        }}
        liveConnected={false}
        liveSuccessText={null}
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
        dryRunError={null}
        dryRunResult={null}
        liveConnected={false}
        liveSuccessText={null}
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
        dryRunError={null}
        dryRunResult={null}
        liveConnected
        liveSuccessText="Here is the answer from the live session."
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
})
