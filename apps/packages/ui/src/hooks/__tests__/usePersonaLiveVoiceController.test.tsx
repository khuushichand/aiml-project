import React from "react"
import { act, renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

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
            model: "whisper-1"
          },
          tts: {
            provider: "openai",
            voice: "alloy"
          }
        })
      )
    })
  })

  it("streams persona audio chunks and commits a stripped transcript when listening stops", async () => {
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
    expect(ws.send).toHaveBeenLastCalledWith(
      JSON.stringify({
        type: "voice_commit",
        session_id: "sess-voice",
        transcript: "search my notes",
        source: "persona_live_voice"
      })
    )
    expect(result.current.lastCommittedText).toBe("search my notes")
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
