import { afterEach, beforeEach, describe, expect, it } from "vitest"

import { buildPersonaWebSocketUrl } from "@/services/persona-stream"

describe("buildPersonaWebSocketUrl", () => {
  const originalDeploymentMode = process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE
  const originalWindow = globalThis.window

  beforeEach(() => {
    Object.defineProperty(globalThis, "window", {
      value: {
        location: {
          origin: "http://127.0.0.1:8080",
          protocol: "http:"
        }
      },
      configurable: true
    })
  })

  afterEach(() => {
    if (originalDeploymentMode === undefined) {
      delete process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE
    } else {
      process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = originalDeploymentMode
    }
    Object.defineProperty(globalThis, "window", {
      value: originalWindow,
      configurable: true
    })
  })

  it("uses the webui origin for quickstart websocket urls", () => {
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "quickstart"

    const url = buildPersonaWebSocketUrl({
      serverUrl: "http://127.0.0.1:8000/",
      authMode: "single-user",
      apiKey: "abc123",
      accessToken: ""
    })

    expect(url).toBe("ws://127.0.0.1:8080/api/v1/persona/stream?api_key=abc123")
  })

  it("builds api-key websocket url for single-user mode", () => {
    const url = buildPersonaWebSocketUrl({
      serverUrl: "http://127.0.0.1:8000/",
      authMode: "single-user",
      apiKey: "abc123",
      accessToken: ""
    })

    expect(url).toBe("ws://127.0.0.1:8000/api/v1/persona/stream?api_key=abc123")
  })

  it("builds token websocket url for multi-user mode", () => {
    const url = buildPersonaWebSocketUrl({
      serverUrl: "https://example.com",
      authMode: "multi-user",
      apiKey: "",
      accessToken: "jwt-token"
    })

    expect(url).toBe("wss://example.com/api/v1/persona/stream?token=jwt-token")
  })

  it("throws when auth secret is missing for selected auth mode", () => {
    expect(() =>
      buildPersonaWebSocketUrl({
        serverUrl: "http://127.0.0.1:8000",
        authMode: "single-user",
        apiKey: "",
        accessToken: ""
      })
    ).toThrowError(/API key missing/i)

    expect(() =>
      buildPersonaWebSocketUrl({
        serverUrl: "http://127.0.0.1:8000",
        authMode: "multi-user",
        apiKey: "",
        accessToken: ""
      })
    ).toThrowError(/Not authenticated/i)
  })
})
