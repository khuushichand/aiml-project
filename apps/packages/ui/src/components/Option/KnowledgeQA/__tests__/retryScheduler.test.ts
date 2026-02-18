import { describe, expect, it } from "vitest"
import {
  getRetryCountdownSeconds,
  KNOWLEDGE_QA_RETRY_INTERVAL_MS,
  normalizeRetryIntervalMs,
} from "../retryScheduler"

describe("KnowledgeQA retry scheduler helpers", () => {
  it("clamps retry interval into safe bounds", () => {
    expect(normalizeRetryIntervalMs(1_000)).toBe(5_000)
    expect(normalizeRetryIntervalMs(10_000)).toBe(10_000)
    expect(normalizeRetryIntervalMs(120_000)).toBe(60_000)
  })

  it("falls back to default retry interval when value is invalid", () => {
    expect(normalizeRetryIntervalMs(Number.NaN)).toBe(
      KNOWLEDGE_QA_RETRY_INTERVAL_MS
    )
  })

  it("returns full countdown when no previous attempt timestamp exists", () => {
    const seconds = getRetryCountdownSeconds({
      lastAttemptAt: null,
      now: 1_000_000,
      retryIntervalMs: 10_000,
    })

    expect(seconds).toBe(10)
  })

  it("counts down and floors at zero after retry interval elapses", () => {
    const start = 1_000_000
    expect(
      getRetryCountdownSeconds({
        lastAttemptAt: start,
        now: start + 1_500,
        retryIntervalMs: 10_000,
      })
    ).toBe(9)

    expect(
      getRetryCountdownSeconds({
        lastAttemptAt: start,
        now: start + 12_000,
        retryIntervalMs: 10_000,
      })
    ).toBe(0)
  })
})
