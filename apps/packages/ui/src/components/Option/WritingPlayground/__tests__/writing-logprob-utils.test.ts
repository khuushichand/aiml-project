import { describe, expect, it } from "vitest"
import {
  extractLogprobEntriesFromChunk,
  logprobToProbability
} from "../writing-logprob-utils"

describe("writing logprob utils", () => {
  it("extracts chat-style logprobs.content entries", () => {
    const entries = extractLogprobEntriesFromChunk({
      choices: [
        {
          logprobs: {
            content: [
              {
                token: "hello",
                logprob: -0.2,
                top_logprobs: [
                  { token: "hello", logprob: -0.2 },
                  { token: "hi", logprob: -0.9 }
                ]
              }
            ]
          }
        }
      ]
    })
    expect(entries).toEqual([
      {
        token: "hello",
        logprob: -0.2,
        topLogprobs: [
          { token: "hello", logprob: -0.2 },
          { token: "hi", logprob: -0.9 }
        ]
      }
    ])
  })

  it("extracts completions-style token_logprobs arrays", () => {
    const entries = extractLogprobEntriesFromChunk({
      choices: [
        {
          logprobs: {
            tokens: ["A", "B"],
            token_logprobs: [-0.1, -1.2],
            top_logprobs: [
              { A: -0.1, Z: -3.4 },
              { B: -1.2, C: -1.3 }
            ]
          }
        }
      ]
    })

    expect(entries).toEqual([
      {
        token: "A",
        logprob: -0.1,
        topLogprobs: [
          { token: "A", logprob: -0.1 },
          { token: "Z", logprob: -3.4 }
        ]
      },
      {
        token: "B",
        logprob: -1.2,
        topLogprobs: [
          { token: "B", logprob: -1.2 },
          { token: "C", logprob: -1.3 }
        ]
      }
    ])
  })

  it("converts logprob to probability", () => {
    expect(logprobToProbability(0)).toBe(1)
    expect(logprobToProbability(-1)).toBeCloseTo(0.367879, 5)
  })
})
