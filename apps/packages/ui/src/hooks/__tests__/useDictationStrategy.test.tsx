import { act, renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import {
  classifyDictationError,
  dictationErrorAllowsAutoFallback,
  resolveDictationMode,
  resolveRequestedDictationMode,
  useDictationStrategy
} from "../useDictationStrategy"

describe("useDictationStrategy helpers", () => {
  it("uses server default when auto fallback flag is off", () => {
    expect(resolveRequestedDictationMode(null, false)).toBe("server")
  })

  it("uses auto default when auto fallback flag is on", () => {
    expect(resolveRequestedDictationMode(null, true)).toBe("auto")
  })

  it("keeps explicit override precedence", () => {
    expect(resolveRequestedDictationMode("browser", false)).toBe("browser")
    expect(resolveRequestedDictationMode("server", true)).toBe("server")
    expect(resolveRequestedDictationMode("auto", false)).toBe("auto")
  })

  it("resolves dictation mode for explicit and auto preferences", () => {
    expect(
      resolveDictationMode({
        requestedMode: "server",
        canUseServerStt: true,
        browserSupportsSpeechRecognition: true
      })
    ).toBe("server")
    expect(
      resolveDictationMode({
        requestedMode: "server",
        canUseServerStt: false,
        browserSupportsSpeechRecognition: true
      })
    ).toBe("unavailable")
    expect(
      resolveDictationMode({
        requestedMode: "browser",
        canUseServerStt: true,
        browserSupportsSpeechRecognition: false
      })
    ).toBe("unavailable")
    expect(
      resolveDictationMode({
        requestedMode: "auto",
        canUseServerStt: false,
        browserSupportsSpeechRecognition: true
      })
    ).toBe("browser")
  })

  it("classifies backend payload errors and status hints", () => {
    expect(
      classifyDictationError({
        status: 503,
        details: { detail: { dictation_error_class: "provider_unavailable" } }
      })
    ).toBe("provider_unavailable")
    expect(
      classifyDictationError({
        status: 503,
        details: { status: "model_downloading" }
      })
    ).toBe("model_unavailable")
    expect(
      classifyDictationError({
        status: 402,
        details: { message: "quota exceeded" }
      })
    ).toBe("quota_error")
  })

  it("enforces the Stage 2 fallback matrix", () => {
    expect(dictationErrorAllowsAutoFallback("provider_unavailable")).toBe(true)
    expect(dictationErrorAllowsAutoFallback("model_unavailable")).toBe(true)
    expect(dictationErrorAllowsAutoFallback("transient_failure")).toBe(true)
    expect(dictationErrorAllowsAutoFallback("unsupported_api")).toBe(true)

    expect(dictationErrorAllowsAutoFallback("auth_error")).toBe(false)
    expect(dictationErrorAllowsAutoFallback("quota_error")).toBe(false)
    expect(dictationErrorAllowsAutoFallback("permission_denied")).toBe(false)
    expect(dictationErrorAllowsAutoFallback("empty_transcript")).toBe(false)
  })
})

describe("useDictationStrategy hook", () => {
  it("switches to browser in auto mode for fallback-eligible server errors", () => {
    const { result } = renderHook(() =>
      useDictationStrategy({
        canUseServerStt: true,
        browserSupportsSpeechRecognition: true,
        isServerDictating: false,
        isBrowserDictating: false,
        modeOverride: null,
        autoFallbackEnabled: true
      })
    )

    expect(result.current.requestedMode).toBe("auto")
    expect(result.current.resolvedMode).toBe("server")

    act(() => {
      const transition = result.current.recordServerError({
        status: 503,
        details: {
          detail: {
            dictation_error_class: "provider_unavailable"
          }
        }
      })
      expect(transition.errorClass).toBe("provider_unavailable")
      expect(transition.appliedFallback).toBe(true)
    })

    expect(result.current.autoFallbackActive).toBe(true)
    expect(result.current.resolvedMode).toBe("browser")
    expect(result.current.toggleIntent).toBe("start_browser")
  })

  it("does not fallback in auto mode for disallowed error classes", () => {
    const { result } = renderHook(() =>
      useDictationStrategy({
        canUseServerStt: true,
        browserSupportsSpeechRecognition: true,
        isServerDictating: false,
        isBrowserDictating: false,
        modeOverride: null,
        autoFallbackEnabled: true
      })
    )

    act(() => {
      const transition = result.current.recordServerError({
        status: 402,
        details: {
          detail: {
            dictation_error_class: "quota_error"
          }
        }
      })
      expect(transition.errorClass).toBe("quota_error")
      expect(transition.appliedFallback).toBe(false)
    })

    expect(result.current.autoFallbackActive).toBe(false)
    expect(result.current.resolvedMode).toBe("server")
  })

  it("honors explicit mode override over auto fallback behavior", () => {
    const { result } = renderHook(() =>
      useDictationStrategy({
        canUseServerStt: true,
        browserSupportsSpeechRecognition: true,
        isServerDictating: false,
        isBrowserDictating: false,
        modeOverride: "browser",
        autoFallbackEnabled: true
      })
    )

    expect(result.current.requestedMode).toBe("browser")
    expect(result.current.resolvedMode).toBe("browser")

    act(() => {
      const transition = result.current.recordServerError({
        status: 503,
        details: {
          detail: {
            dictation_error_class: "provider_unavailable"
          }
        }
      })
      expect(transition.appliedFallback).toBe(false)
    })

    expect(result.current.autoFallbackActive).toBe(false)
    expect(result.current.resolvedMode).toBe("browser")
  })

  it("uses the source-enforced server path when browser dictation is not compatible", () => {
    const { result } = renderHook(() =>
      useDictationStrategy({
        canUseServerStt: true,
        browserSupportsSpeechRecognition: true,
        browserDictationCompatible: false,
        resolvedModeOverride: "server",
        isServerDictating: false,
        isBrowserDictating: false,
        modeOverride: "browser",
        autoFallbackEnabled: true
      })
    )

    expect(result.current.requestedMode).toBe("browser")
    expect(result.current.resolvedMode).toBe("server")
    expect(result.current.toggleIntent).toBe("start_server")
  })
})
