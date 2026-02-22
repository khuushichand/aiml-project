import { describe, expect, it } from "vitest"
import {
  consumeStreamingChunk,
  extractStreamingChunkError
} from "../streaming-chunks"

describe("streaming chunk error handling", () => {
  it("extracts error details from explicit error payloads", () => {
    const details = extractStreamingChunkError({
      error: {
        code: "internal_error",
        message: "pony-alpha is not a valid model ID"
      }
    })

    expect(details).toEqual({
      code: "internal_error",
      message: "pony-alpha is not a valid model ID"
    })
  })

  it("treats event:error payloads as stream failures", () => {
    const details = extractStreamingChunkError({
      event: "error",
      message: "Selected model is unavailable"
    })

    expect(details).toEqual({
      code: undefined,
      message: "Selected model is unavailable"
    })
  })

  it("throws with provider message when stream emits an error chunk", () => {
    expect(() =>
      consumeStreamingChunk(
        { fullText: "", contentToSave: "", apiReasoning: false },
        { error: { code: "internal_error", message: "invalid model" } }
      )
    ).toThrowError("invalid model")
  })

  it("does not treat normal completion chunks as errors", () => {
    const state = consumeStreamingChunk(
      { fullText: "", contentToSave: "", apiReasoning: false },
      {
        choices: [{ delta: { content: "Hello" } }]
      }
    )

    expect(state.fullText).toBe("Hello")
    expect(state.contentToSave).toBe("Hello")
    expect(state.token).toBe("Hello")
  })
})
