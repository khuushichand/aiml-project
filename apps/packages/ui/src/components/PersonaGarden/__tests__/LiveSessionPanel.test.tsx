import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { AssistantVoiceCard } from "../AssistantVoiceCard"
import { LiveSessionPanel } from "../LiveSessionPanel"

describe("LiveSessionPanel", () => {
  it("renders the assistant voice card before status panels", () => {
    render(
      <LiveSessionPanel
        controls={<div>controls</div>}
        assistantVoice={<div data-testid="assistant-voice-slot">voice card</div>}
        error={<div>errors</div>}
        pendingPlan={<div>plan</div>}
        transcript={<div>transcript</div>}
        composer={<div>composer</div>}
      />
    )

    expect(screen.getByTestId("assistant-voice-slot")).toBeInTheDocument()
    expect(screen.getByText("errors")).toBeInTheDocument()
  })
})

describe("AssistantVoiceCard", () => {
  it("renders resolved defaults, session toggles, and warning state", () => {
    const onToggleListening = vi.fn()
    const onSendNow = vi.fn()
    const onSessionAutoResumeChange = vi.fn()
    const onSessionBargeInChange = vi.fn()

    render(
      <AssistantVoiceCard
        resolvedDefaults={{
          sttLanguage: "en-US",
          sttModel: "whisper-1",
          ttsProvider: "openai",
          ttsVoice: "alloy",
          confirmationMode: "destructive_only",
          voiceChatTriggerPhrases: ["hey helper"],
          autoResume: true,
          bargeIn: false
        }}
        state="speaking"
        speechAvailable
        isListening={false}
        heardText="hey helper open notes"
        lastCommittedText="open notes"
        warning="Live TTS unavailable for this session. Continuing in text-only mode."
        textOnlyDueToTtsFailure
        manualModeRequired
        canSendNow
        sessionAutoResume={false}
        sessionBargeIn
        onToggleListening={onToggleListening}
        onSendNow={onSendNow}
        onSessionAutoResumeChange={onSessionAutoResumeChange}
        onSessionBargeInChange={onSessionBargeInChange}
      />
    )

    expect(screen.getByText("Assistant Voice")).toBeInTheDocument()
    expect(screen.getByTestId("live-voice-trigger-phrases")).toHaveTextContent(
      "hey helper"
    )
    expect(screen.getByTestId("live-voice-warning")).toHaveTextContent(
      "Continuing in text-only mode"
    )
    expect(screen.getByTestId("live-voice-heard-text")).toHaveTextContent(
      "hey helper open notes"
    )
    expect(screen.getByTestId("live-voice-last-commit")).toHaveTextContent("open notes")

    fireEvent.click(screen.getByTestId("live-voice-start-stop"))
    expect(onToggleListening).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByTestId("live-voice-send-now"))
    expect(onSendNow).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByTestId("live-voice-auto-resume"))
    expect(onSessionAutoResumeChange).toHaveBeenCalledWith(true)

    fireEvent.click(screen.getByTestId("live-voice-barge-in"))
    expect(onSessionBargeInChange).toHaveBeenCalledWith(false)
  })
})
