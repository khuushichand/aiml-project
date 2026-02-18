import { describe, expect, it } from "vitest"
import {
  buildPromptStudioWebSocketUrl,
  isPromptStudioStatusEvent
} from "@/services/prompt-studio-stream"

describe("buildPromptStudioWebSocketUrl", () => {
  it("builds single-user websocket url with api key", () => {
    const url = buildPromptStudioWebSocketUrl({
      serverUrl: "http://127.0.0.1:8000/",
      authMode: "single-user",
      apiKey: "abc123",
      accessToken: ""
    })

    expect(url).toBe("ws://127.0.0.1:8000/api/v1/prompt-studio/ws?api_key=abc123")
  })

  it("builds multi-user websocket url with bearer token and project id", () => {
    const url = buildPromptStudioWebSocketUrl(
      {
        serverUrl: "https://example.com",
        authMode: "multi-user",
        apiKey: "",
        accessToken: "jwt-token"
      },
      42
    )

    expect(url).toBe(
      "wss://example.com/api/v1/prompt-studio/ws?token=jwt-token&project_id=42"
    )
  })
})

describe("isPromptStudioStatusEvent", () => {
  it("accepts known realtime status event payloads", () => {
    expect(isPromptStudioStatusEvent({ type: "job_progress" })).toBe(true)
    expect(isPromptStudioStatusEvent({ type: "subscribed" })).toBe(true)
  })

  it("rejects unknown payloads", () => {
    expect(isPromptStudioStatusEvent({ type: "unrelated" })).toBe(false)
    expect(isPromptStudioStatusEvent(null)).toBe(false)
    expect(isPromptStudioStatusEvent("job_progress")).toBe(false)
  })
})
