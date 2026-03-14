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
    const onKeepListening = vi.fn()
    const onResetTurn = vi.fn()
    const onWaitOnRecovery = vi.fn()
    const onCopyLastCommandToComposer = vi.fn()
    const onReconnectPersonaSession = vi.fn()

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
        activeToolStatus=""
        pendingApprovalSummary={null}
        warning="Live TTS unavailable for this session. Continuing in text-only mode."
        recoveryMode="none"
        textOnlyDueToTtsFailure
        manualModeRequired
        canSendNow
        sessionAutoResume={false}
        sessionBargeIn
        onToggleListening={onToggleListening}
        onSendNow={onSendNow}
        onSessionAutoResumeChange={onSessionAutoResumeChange}
        onSessionBargeInChange={onSessionBargeInChange}
        onKeepListening={onKeepListening}
        onResetTurn={onResetTurn}
        onWaitOnRecovery={onWaitOnRecovery}
        onCopyLastCommandToComposer={onCopyLastCommandToComposer}
        onJumpToApproval={vi.fn()}
        onReconnectPersonaSession={onReconnectPersonaSession}
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

  it("renders listening recovery copy and actions", () => {
    const onKeepListening = vi.fn()
    const onResetTurn = vi.fn()
    const onReconnectPersonaSession = vi.fn()

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
        state="listening"
        speechAvailable
        isListening
        heardText="hey helper search my notes"
        lastCommittedText=""
        activeToolStatus=""
        pendingApprovalSummary={null}
        warning={null}
        recoveryMode="listening_stuck"
        textOnlyDueToTtsFailure={false}
        manualModeRequired={false}
        canSendNow
        sessionAutoResume
        sessionBargeIn={false}
        onToggleListening={vi.fn()}
        onSendNow={vi.fn()}
        onSessionAutoResumeChange={vi.fn()}
        onSessionBargeInChange={vi.fn()}
        onKeepListening={onKeepListening}
        onResetTurn={onResetTurn}
        onWaitOnRecovery={vi.fn()}
        onCopyLastCommandToComposer={vi.fn()}
        onJumpToApproval={vi.fn()}
        onReconnectPersonaSession={onReconnectPersonaSession}
      />
    )

    expect(screen.getByText("Voice turn needs attention")).toBeInTheDocument()
    expect(
      screen.getByText("I heard speech, but this turn has not been committed yet.")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("live-voice-recovery-keep-listening"))
    expect(onKeepListening).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByTestId("live-voice-recovery-reset-turn"))
    expect(onResetTurn).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByTestId("live-voice-recovery-reconnect"))
    expect(onReconnectPersonaSession).toHaveBeenCalledTimes(1)
  })

  it("renders thinking recovery copy and actions", () => {
    const onWaitOnRecovery = vi.fn()
    const onCopyLastCommandToComposer = vi.fn()
    const onResetTurn = vi.fn()
    const onReconnectPersonaSession = vi.fn()

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
        state="thinking"
        speechAvailable
        isListening={false}
        heardText="hey helper search my notes"
        lastCommittedText="search my notes"
        activeToolStatus=""
        pendingApprovalSummary={null}
        warning={null}
        recoveryMode="thinking_stuck"
        textOnlyDueToTtsFailure={false}
        manualModeRequired={false}
        canSendNow={false}
        sessionAutoResume
        sessionBargeIn={false}
        onToggleListening={vi.fn()}
        onSendNow={vi.fn()}
        onSessionAutoResumeChange={vi.fn()}
        onSessionBargeInChange={vi.fn()}
        onKeepListening={vi.fn()}
        onResetTurn={onResetTurn}
        onWaitOnRecovery={onWaitOnRecovery}
        onCopyLastCommandToComposer={onCopyLastCommandToComposer}
        onJumpToApproval={vi.fn()}
        onReconnectPersonaSession={onReconnectPersonaSession}
      />
    )

    expect(screen.getByText("Assistant response is delayed")).toBeInTheDocument()
    expect(
      screen.getByText("This voice turn was sent, but the assistant has not responded yet.")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("live-voice-recovery-wait"))
    expect(onWaitOnRecovery).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByTestId("live-voice-recovery-copy-command"))
    expect(onCopyLastCommandToComposer).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByTestId("live-voice-recovery-reset-turn"))
    expect(onResetTurn).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByTestId("live-voice-recovery-reconnect"))
    expect(onReconnectPersonaSession).toHaveBeenCalledTimes(1)
  })

  it("renders the current action line while thinking with active tool status", () => {
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
        state="thinking"
        speechAvailable
        isListening={false}
        heardText=""
        lastCommittedText="search my notes"
        activeToolStatus="Running search_notes: Looking through your notes"
        pendingApprovalSummary={null}
        warning={null}
        recoveryMode="none"
        textOnlyDueToTtsFailure={false}
        manualModeRequired={false}
        canSendNow={false}
        sessionAutoResume
        sessionBargeIn={false}
        onToggleListening={vi.fn()}
        onSendNow={vi.fn()}
        onSessionAutoResumeChange={vi.fn()}
        onSessionBargeInChange={vi.fn()}
        onKeepListening={vi.fn()}
        onResetTurn={vi.fn()}
        onWaitOnRecovery={vi.fn()}
        onCopyLastCommandToComposer={vi.fn()}
        onJumpToApproval={vi.fn()}
        onReconnectPersonaSession={vi.fn()}
      />
    )

    expect(screen.getByText("Current action")).toBeInTheDocument()
    expect(
      screen.getByText("Running search_notes: Looking through your notes")
    ).toBeInTheDocument()
  })

  it("hides the current action line when active tool status is empty", () => {
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
        state="thinking"
        speechAvailable
        isListening={false}
        heardText=""
        lastCommittedText="search my notes"
        activeToolStatus=""
        pendingApprovalSummary={null}
        warning={null}
        recoveryMode="none"
        textOnlyDueToTtsFailure={false}
        manualModeRequired={false}
        canSendNow={false}
        sessionAutoResume
        sessionBargeIn={false}
        onToggleListening={vi.fn()}
        onSendNow={vi.fn()}
        onSessionAutoResumeChange={vi.fn()}
        onSessionBargeInChange={vi.fn()}
        onKeepListening={vi.fn()}
        onResetTurn={vi.fn()}
        onWaitOnRecovery={vi.fn()}
        onCopyLastCommandToComposer={vi.fn()}
        onJumpToApproval={vi.fn()}
        onReconnectPersonaSession={vi.fn()}
      />
    )

    expect(screen.queryByText("Current action")).not.toBeInTheDocument()
  })

  it("renders approval summary text in the current action block", () => {
    const onJumpToApproval = vi.fn()

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
        state="thinking"
        speechAvailable
        isListening={false}
        heardText=""
        lastCommittedText="search my notes"
        activeToolStatus=""
        pendingApprovalSummary="Waiting for approval: search_notes (+1 more)"
        warning={null}
        recoveryMode="none"
        textOnlyDueToTtsFailure={false}
        manualModeRequired={false}
        canSendNow={false}
        sessionAutoResume
        sessionBargeIn={false}
        onToggleListening={vi.fn()}
        onSendNow={vi.fn()}
        onSessionAutoResumeChange={vi.fn()}
        onSessionBargeInChange={vi.fn()}
        onKeepListening={vi.fn()}
        onResetTurn={vi.fn()}
        onWaitOnRecovery={vi.fn()}
        onCopyLastCommandToComposer={vi.fn()}
        onJumpToApproval={onJumpToApproval}
        onReconnectPersonaSession={vi.fn()}
      />
    )

    expect(screen.getByText("Current action")).toBeInTheDocument()
    expect(
      screen.getByText("Waiting for approval: search_notes (+1 more)")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("live-voice-jump-to-approval"))
    expect(onJumpToApproval).toHaveBeenCalledTimes(1)
  })

  it("prefers approval summary over active tool status", () => {
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
        state="thinking"
        speechAvailable
        isListening={false}
        heardText=""
        lastCommittedText="search my notes"
        activeToolStatus="Running search_notes: Looking through your notes"
        pendingApprovalSummary="Waiting for approval: search_notes"
        warning={null}
        recoveryMode="none"
        textOnlyDueToTtsFailure={false}
        manualModeRequired={false}
        canSendNow={false}
        sessionAutoResume
        sessionBargeIn={false}
        onToggleListening={vi.fn()}
        onSendNow={vi.fn()}
        onSessionAutoResumeChange={vi.fn()}
        onSessionBargeInChange={vi.fn()}
        onKeepListening={vi.fn()}
        onResetTurn={vi.fn()}
        onWaitOnRecovery={vi.fn()}
        onCopyLastCommandToComposer={vi.fn()}
        onJumpToApproval={vi.fn()}
        onReconnectPersonaSession={vi.fn()}
      />
    )

    expect(screen.getByText("Waiting for approval: search_notes")).toBeInTheDocument()
    expect(
      screen.queryByText("Running search_notes: Looking through your notes")
    ).not.toBeInTheDocument()
  })
})
