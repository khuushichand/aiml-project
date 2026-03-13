import React from "react"
import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { usePersonaLiveVoiceController } from "../usePersonaLiveVoiceController"

const hookMocks = vi.hoisted(() => ({
  audioStart: vi.fn(),
  audioAppend: vi.fn(),
  audioFinish: vi.fn(),
  audioStop: vi.fn(),
  audioState: { playing: false },
  micStart: vi.fn(() => {
    hookMocks.micActive = true
    return Promise.resolve()
  }),
  micStop: vi.fn(() => {
    hookMocks.micActive = false
  }),
  micActive: false,
  micChunkHandler: null as ((chunk: ArrayBuffer) => void) | null
}))

vi.mock("@/hooks/useStreamingAudioPlayer", () => ({
  useStreamingAudioPlayer: () => ({
    start: hookMocks.audioStart,
    append: hookMocks.audioAppend,
    finish: hookMocks.audioFinish,
    stop: hookMocks.audioStop,
    state: hookMocks.audioState
  })
}))

vi.mock("@/hooks/useMicStream", () => ({
  useMicStream: (onChunk: (chunk: ArrayBuffer) => void) => {
    hookMocks.micChunkHandler = onChunk
    return {
      start: hookMocks.micStart,
      stop: hookMocks.micStop,
      active: hookMocks.micActive
    }
  }
}))

describe("usePersonaLiveVoiceController", () => {
  beforeEach(() => {
    hookMocks.audioStart.mockReset()
    hookMocks.audioAppend.mockReset()
    hookMocks.audioFinish.mockReset()
    hookMocks.audioStop.mockReset()
    hookMocks.audioState.playing = false
    hookMocks.micActive = false
    hookMocks.micChunkHandler = null
    hookMocks.micStart.mockReset()
    hookMocks.micStart.mockImplementation(() => {
      hookMocks.micActive = true
      return Promise.resolve()
    })
    hookMocks.micStop.mockReset()
    hookMocks.micStop.mockImplementation(() => {
      hookMocks.micActive = false
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  const resolvedDefaults = {
    sttLanguage: "en-US",
    sttModel: "whisper-1",
    ttsProvider: "openai",
    ttsVoice: "alloy",
    confirmationMode: "destructive_only" as const,
    voiceChatTriggerPhrases: ["hey helper"],
    autoResume: true,
    bargeIn: false
  }

  const getSentPayloads = (ws: WebSocket & { send: ReturnType<typeof vi.fn> }) =>
    ws.send.mock.calls.map(([payload]) => JSON.parse(String(payload)))

  it("sends persona-scoped voice_config when the live websocket is connected", async () => {
    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    await waitFor(() => {
      expect(ws.send).toHaveBeenCalledWith(
        JSON.stringify({
          type: "voice_config",
          session_id: "sess-voice",
          voice: {
            trigger_phrases: ["hey helper"],
            auto_resume: true,
            barge_in: false
          },
          stt: {
            language: "en-US",
            model: "whisper-1",
            enable_vad: true
          },
          tts: {
            provider: "openai",
            voice: "alloy"
          }
        })
      )
    })
  })

  it("streams persona audio chunks and does not send a routine manual commit when listening stops", async () => {
    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result, rerender } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    await act(async () => {
      await result.current.startListening()
    })
    rerender()

    expect(hookMocks.micStart).toHaveBeenCalledTimes(1)
    expect(result.current.isListening).toBe(true)
    expect(hookMocks.micChunkHandler).toBeTypeOf("function")

    act(() => {
      hookMocks.micChunkHandler?.(new Uint8Array([1, 2, 3, 4]).buffer)
    })

    expect(getSentPayloads(ws as WebSocket & { send: ReturnType<typeof vi.fn> })).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: "audio_chunk",
          session_id: "sess-voice",
          audio_format: "pcm16",
          bytes_base64: expect.any(String)
        })
      ])
    )

    act(() => {
      result.current.handlePayload({
        event: "partial_transcript",
        text_delta: "hey helper search my notes"
      })
    })

    expect(result.current.heardText).toBe("hey helper search my notes")

    const stopCallsBeforeStop = hookMocks.micStop.mock.calls.length

    act(() => {
      result.current.stopListening()
    })
    rerender()

    expect(hookMocks.micStop.mock.calls.length).toBe(stopCallsBeforeStop + 1)
    expect(
      getSentPayloads(ws as WebSocket & { send: ReturnType<typeof vi.fn> }).filter(
        (payload) => payload.type === "voice_commit"
      )
    ).toEqual([])
  })

  it("shows listening recovery after 4 seconds with transcript but no commit", async () => {
    vi.useFakeTimers()

    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result, rerender } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    await act(async () => {
      await result.current.startListening()
    })
    rerender()

    act(() => {
      result.current.handlePayload({
        event: "partial_transcript",
        text_delta: "hey helper"
      })
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000)
    })

    expect((result.current as any).recoveryMode).toBe("listening_stuck")
  })

  it("restarts listening recovery when new transcript deltas arrive", async () => {
    vi.useFakeTimers()

    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result, rerender } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    await act(async () => {
      await result.current.startListening()
    })
    rerender()

    act(() => {
      result.current.handlePayload({
        event: "partial_transcript",
        text_delta: "hey helper"
      })
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3500)
    })

    act(() => {
      result.current.handlePayload({
        event: "partial_transcript",
        text_delta: "search my notes"
      })
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })

    expect((result.current as any).recoveryMode).toBe("none")

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000)
    })

    expect((result.current as any).recoveryMode).toBe("listening_stuck")
  })

  it("keep listening dismisses and restarts listening recovery", async () => {
    vi.useFakeTimers()

    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result, rerender } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    await act(async () => {
      await result.current.startListening()
    })
    rerender()

    act(() => {
      result.current.handlePayload({
        event: "partial_transcript",
        text_delta: "hey helper search my notes"
      })
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000)
    })

    expect((result.current as any).recoveryMode).toBe("listening_stuck")

    act(() => {
      ;(result.current as any).keepListening()
    })

    expect((result.current as any).recoveryMode).toBe("none")

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3999)
    })

    expect((result.current as any).recoveryMode).toBe("none")

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1)
    })

    expect((result.current as any).recoveryMode).toBe("listening_stuck")
  })

  it("reset turn clears heard transcript and returns to idle", async () => {
    vi.useFakeTimers()

    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result, rerender } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    await act(async () => {
      await result.current.startListening()
    })
    rerender()

    act(() => {
      result.current.handlePayload({
        event: "partial_transcript",
        text_delta: "hey helper search my notes"
      })
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000)
    })

    const stopCallsBeforeReset = hookMocks.micStop.mock.calls.length

    act(() => {
      ;(result.current as any).resetTurn()
    })
    rerender()

    expect(hookMocks.micStop.mock.calls.length).toBe(stopCallsBeforeReset + 1)
    expect(result.current.heardText).toBe("")
    expect(result.current.state).toBe("idle")
    expect((result.current as any).recoveryMode).toBe("none")
  })

  it("switches to thinking and stops the mic when the server auto-commits a voice turn", async () => {
    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result, rerender } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    await act(async () => {
      await result.current.startListening()
    })
    rerender()

    act(() => {
      result.current.handlePayload({
        event: "partial_transcript",
        text_delta: "hey helper search my notes"
      })
    })

    const stopCallsBeforeCommit = hookMocks.micStop.mock.calls.length

    act(() => {
      result.current.handlePayload({
        event: "notice",
        reason_code: "VOICE_TURN_COMMITTED",
        transcript: "search my notes",
        commit_source: "vad_auto"
      })
    })
    rerender()

    expect(hookMocks.micStop.mock.calls.length).toBe(stopCallsBeforeCommit + 1)
    expect(result.current.state).toBe("thinking")
    expect(result.current.lastCommittedText).toBe("search my notes")
    expect(result.current.heardText).toBe("hey helper search my notes")
  })

  it("shows thinking recovery after 8 seconds after commit with no assistant progress", async () => {
    vi.useFakeTimers()

    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    act(() => {
      result.current.handlePayload({
        event: "notice",
        reason_code: "VOICE_TURN_COMMITTED",
        transcript: "search my notes",
        commit_source: "vad_auto"
      })
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(8000)
    })

    expect((result.current as any).recoveryMode).toBe("thinking_stuck")
  })

  it("assistant progress clears thinking recovery", async () => {
    vi.useFakeTimers()

    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    act(() => {
      result.current.handlePayload({
        event: "notice",
        reason_code: "VOICE_TURN_COMMITTED",
        transcript: "search my notes",
        commit_source: "vad_auto"
      })
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(8000)
    })

    expect((result.current as any).recoveryMode).toBe("thinking_stuck")

    act(() => {
      result.current.handlePayload({
        event: "assistant_delta",
        text_delta: "Working on it"
      })
    })

    expect((result.current as any).recoveryMode).toBe("none")
  })

  it("re-arms thinking recovery when VOICE_TURN_PROCESSING arrives", async () => {
    vi.useFakeTimers()

    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    act(() => {
      result.current.handlePayload({
        event: "notice",
        reason_code: "VOICE_TURN_COMMITTED",
        transcript: "search my notes",
        commit_source: "vad_auto"
      })
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(7000)
    })

    expect((result.current as any).recoveryMode).toBe("none")

    act(() => {
      result.current.handlePayload({
        event: "notice",
        reason_code: "VOICE_TURN_PROCESSING",
        message: "Still processing this voice turn."
      })
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500)
    })

    expect((result.current as any).recoveryMode).toBe("none")
  })

  it("still enters thinking_stuck after a renewed quiet window", async () => {
    vi.useFakeTimers()

    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    act(() => {
      result.current.handlePayload({
        event: "notice",
        reason_code: "VOICE_TURN_COMMITTED",
        transcript: "search my notes",
        commit_source: "vad_auto"
      })
    })

    act(() => {
      result.current.handlePayload({
        event: "notice",
        reason_code: "VOICE_TURN_PROCESSING",
        message: "Still processing this voice turn."
      })
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(8000)
    })

    expect((result.current as any).recoveryMode).toBe("thinking_stuck")
  })

  it("sets activeToolStatus and re-arms thinking recovery on tool_call", async () => {
    vi.useFakeTimers()

    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    act(() => {
      result.current.handlePayload({
        event: "notice",
        reason_code: "VOICE_TURN_COMMITTED",
        transcript: "search my notes",
        commit_source: "vad_auto"
      })
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(7000)
    })

    expect((result.current as any).recoveryMode).toBe("none")

    act(() => {
      result.current.handlePayload({
        event: "tool_call",
        tool: "search_notes",
        why: "Looking through your notes"
      })
    })

    expect((result.current as any).activeToolStatus).toBe(
      "Running search_notes: Looking through your notes"
    )
    expect((result.current as any).recoveryMode).toBe("none")

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500)
    })

    expect((result.current as any).recoveryMode).toBe("none")
  })

  it("re-arms thinking recovery when VOICE_TOOL_EXECUTION_PROCESSING arrives", async () => {
    vi.useFakeTimers()

    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    await act(async () => {
      result.current.handlePayload({
        event: "notice",
        reason_code: "VOICE_TURN_COMMITTED",
        transcript: "search my notes",
        commit_source: "vad_auto"
      })
    })

    act(() => {
      result.current.handlePayload({
        event: "tool_call",
        tool: "search_notes",
        why: "Looking through your notes"
      })
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(7000)
    })

    expect((result.current as any).recoveryMode).toBe("none")

    act(() => {
      result.current.handlePayload({
        event: "notice",
        reason_code: "VOICE_TOOL_EXECUTION_PROCESSING",
        tool: "search_notes",
        step_idx: 0,
        why: "Looking through your notes"
      })
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500)
    })

    expect((result.current as any).recoveryMode).toBe("none")
  })

  it("clears activeToolStatus and re-arms recovery on tool_result", async () => {
    vi.useFakeTimers()

    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    act(() => {
      result.current.handlePayload({
        event: "notice",
        reason_code: "VOICE_TURN_COMMITTED",
        transcript: "search my notes",
        commit_source: "vad_auto"
      })
    })

    act(() => {
      result.current.handlePayload({
        event: "tool_call",
        tool: "search_notes",
        why: "Looking through your notes"
      })
    })

    expect((result.current as any).activeToolStatus).toBeTruthy()

    act(() => {
      result.current.handlePayload({
        event: "tool_result",
        ok: true,
        tool: "search_notes",
        output: { ok: true }
      })
    })

    expect((result.current as any).activeToolStatus).toBe("")
    expect((result.current as any).recoveryMode).toBe("none")

    await act(async () => {
      await vi.advanceTimersByTimeAsync(8000)
    })

    expect((result.current as any).recoveryMode).toBe("thinking_stuck")
  })

  it("clears activeToolStatus and recovery on approval tool_result", async () => {
    vi.useFakeTimers()

    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    act(() => {
      result.current.handlePayload({
        event: "notice",
        reason_code: "VOICE_TURN_COMMITTED",
        transcript: "search my notes",
        commit_source: "vad_auto"
      })
    })

    act(() => {
      result.current.handlePayload({
        event: "tool_call",
        tool: "search_notes",
        why: "Looking through your notes"
      })
    })

    expect((result.current as any).activeToolStatus).toBeTruthy()

    act(() => {
      result.current.handlePayload({
        event: "tool_result",
        approval: {
          tool_name: "search_notes",
          context_key: "ctx",
          scope_key: "once",
          duration_options: ["once"]
        }
      })
    })

    expect((result.current as any).activeToolStatus).toBe("")
    expect((result.current as any).recoveryMode).toBe("none")
  })

  it("enters manual mode when the server cannot auto-commit and sends the current transcript on demand", async () => {
    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result, rerender } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    await act(async () => {
      await result.current.startListening()
    })
    rerender()

    act(() => {
      result.current.handlePayload({
        event: "partial_transcript",
        text_delta: "hey helper search my notes"
      })
    })
    act(() => {
      result.current.handlePayload({
        event: "notice",
        reason_code: "VOICE_MANUAL_MODE_REQUIRED",
        message:
          "Server VAD unavailable for this live session. Use Send now to commit heard speech manually."
      })
    })

    expect(result.current.manualModeRequired).toBe(true)
    expect(result.current.canSendNow).toBe(true)
    expect(result.current.warning).toContain("Use Send now")

    const stopCallsBeforeSend = hookMocks.micStop.mock.calls.length

    act(() => {
      result.current.sendCurrentTranscriptNow()
    })
    rerender()

    expect(hookMocks.micStop.mock.calls.length).toBe(stopCallsBeforeSend + 1)
    expect(ws.send).toHaveBeenLastCalledWith(
      JSON.stringify({
        type: "voice_commit",
        session_id: "sess-voice",
        transcript: "hey helper search my notes",
        source: "persona_live_voice_manual"
      })
    )
    expect(result.current.state).toBe("thinking")
  })

  it("auto-resumes listening after a recoverable text-only tts warning", async () => {
    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result, rerender } = renderHook(() =>
      usePersonaLiveVoiceController({
        ws,
        connected: true,
        sessionId: "sess-voice",
        personaId: "persona-1",
        resolvedDefaults,
        canUseServerStt: true
      })
    )

    act(() => {
      result.current.handlePayload({
        event: "notice",
        reason_code: "TTS_UNAVAILABLE_TEXT_ONLY",
        message: "Live TTS unavailable for this session. Continuing in text-only mode."
      })
    })
    rerender()

    await waitFor(() => {
      expect(hookMocks.micStart).toHaveBeenCalledTimes(1)
    })
    expect(result.current.textOnlyDueToTtsFailure).toBe(true)
    expect(result.current.warning).toContain("Continuing in text-only mode.")
  })

  it("resets session-local overrides when the persona session changes", async () => {
    const ws = {
      readyState: WebSocket.OPEN,
      send: vi.fn()
    } as unknown as WebSocket

    const { result, rerender } = renderHook(
      ({
        personaId,
        sessionId
      }: {
        personaId: string
        sessionId: string
      }) =>
        usePersonaLiveVoiceController({
          ws,
          connected: true,
          sessionId,
          personaId,
          resolvedDefaults,
          canUseServerStt: true
        }),
      {
        initialProps: {
          personaId: "persona-1",
          sessionId: "sess-voice"
        }
      }
    )

    act(() => {
      result.current.setSessionAutoResume(false)
      result.current.setSessionBargeIn(true)
    })

    expect(result.current.sessionAutoResume).toBe(false)
    expect(result.current.sessionBargeIn).toBe(true)

    rerender({
      personaId: "persona-2",
      sessionId: "sess-voice-2"
    })

    await waitFor(() => {
      expect(result.current.sessionAutoResume).toBe(true)
      expect(result.current.sessionBargeIn).toBe(false)
    })
  })
})
