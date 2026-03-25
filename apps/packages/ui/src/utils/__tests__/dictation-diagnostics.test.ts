import { afterEach, describe, expect, it, vi } from "vitest"

import {
  DICTATION_DIAGNOSTICS_EVENT,
  emitDictationDiagnostics,
  sanitizeDictationDiagnosticsPayload
} from "@/utils/dictation-diagnostics"

describe("dictation-diagnostics", () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("sanitizes payload fields into the canonical diagnostics schema", () => {
    const payload = sanitizeDictationDiagnosticsPayload({
      surface: "playground",
      kind: "server_error",
      requestedMode: "auto",
      resolvedMode: "server",
      requestedSourceKind: "mic_device",
      resolvedSourceKind: "mic_device",
      speechAvailable: true,
      speechUsesServer: true,
      toggleIntent: "start_server",
      errorClass: "provider_unavailable",
      fallbackApplied: true,
      fallbackReason: "provider_unavailable",
      at: "2026-02-22T20:00:00.000Z"
    })

    expect(payload).toEqual({
      version: 2,
      at: "2026-02-22T20:00:00.000Z",
      surface: "playground",
      kind: "server_error",
      requested_mode: "auto",
      resolved_mode: "server",
      requested_source_kind: "mic_device",
      resolved_source_kind: "mic_device",
      speech_available: true,
      speech_uses_server: true,
      toggle_intent: "start_server",
      error_class: "provider_unavailable",
      fallback_applied: true,
      fallback_reason: "provider_unavailable"
    })
  })

  it("drops unsupported values and never serializes transcript/prompt/audio content", () => {
    const payload = sanitizeDictationDiagnosticsPayload({
      surface: "sidepanel",
      kind: "toggle",
      requestedMode: "invalid" as any,
      resolvedMode: "invalid" as any,
      requestedSourceKind: "invalid" as any,
      resolvedSourceKind: "invalid" as any,
      toggleIntent: "invalid" as any,
      errorClass: "invalid" as any,
      fallbackReason: "invalid" as any,
      fallbackApplied: false,
      speechAvailable: false,
      speechUsesServer: false,
      at: "",
      transcript: "secret transcript",
      prompt: "secret prompt",
      audio: "base64-audio"
    } as any)

    expect(payload.requested_mode).toBe("unknown")
    expect(payload.resolved_mode).toBe("unknown")
    expect(payload.requested_source_kind).toBe("unknown")
    expect(payload.resolved_source_kind).toBe("unknown")
    expect(payload.toggle_intent).toBeNull()
    expect(payload.error_class).toBeNull()
    expect(payload.fallback_reason).toBeNull()
    expect(payload.fallback_applied).toBe(false)
    expect(Object.hasOwn(payload, "transcript")).toBe(false)
    expect(Object.hasOwn(payload, "prompt")).toBe(false)
    expect(Object.hasOwn(payload, "audio")).toBe(false)
  })

  it("dispatches a browser event with sanitized payload", () => {
    const handler = vi.fn()
    window.addEventListener(DICTATION_DIAGNOSTICS_EVENT, handler)
    try {
      const emitted = emitDictationDiagnostics({
        surface: "playground",
        kind: "toggle",
        requestedMode: "server",
        resolvedMode: "server",
        speechAvailable: true,
        speechUsesServer: true,
        toggleIntent: "stop_server"
      })

      expect(emitted.toggle_intent).toBe("stop_server")
      expect(handler).toHaveBeenCalledTimes(1)
      const event = handler.mock.calls[0]?.[0] as CustomEvent
      expect(event.detail.toggle_intent).toBe("stop_server")
      expect(event.detail.speech_uses_server).toBe(true)
    } finally {
      window.removeEventListener(DICTATION_DIAGNOSTICS_EVENT, handler)
    }
  })
})
