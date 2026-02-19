import { beforeEach, describe, expect, it } from "vitest"

import {
  clearQueuedQuizSubmission,
  deserializeQueuedQuizSubmission,
  readQueuedQuizSubmission,
  serializeQueuedQuizSubmission,
  writeQueuedQuizSubmission,
  type QueuedQuizSubmission
} from "../quizSubmissionQueue"

const validQueue: QueuedQuizSubmission = {
  attemptId: 101,
  quizId: 7,
  answers: [{ question_id: 1, user_answer: "true", hint_used: true, time_spent_ms: 1200 }],
  allowPartial: false,
  queuedAt: Date.now(),
  retryCount: 0,
  lastAttemptedAt: Date.now(),
  lastError: "Network Error"
}

describe("quizSubmissionQueue", () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it("serializes and deserializes a valid queued submission", () => {
    const raw = serializeQueuedQuizSubmission(validQueue)
    const parsed = deserializeQueuedQuizSubmission(raw)

    expect(parsed).toEqual(validQueue)
  })

  it("returns null for invalid or stale payloads", () => {
    expect(deserializeQueuedQuizSubmission(null)).toBeNull()
    expect(deserializeQueuedQuizSubmission("{bad json")).toBeNull()

    const staleRaw = JSON.stringify({
      ...validQueue,
      queuedAt: Date.now() - (25 * 60 * 60 * 1000)
    })
    expect(deserializeQueuedQuizSubmission(staleRaw)).toBeNull()

    const invalidAnswerShapeRaw = JSON.stringify({
      ...validQueue,
      answers: [{ question_id: 2, user_answer: { left: 1 } }]
    })
    expect(deserializeQueuedQuizSubmission(invalidAnswerShapeRaw)).toBeNull()
  })

  it("accepts array and map answer values in queued submissions", () => {
    const withArrayAnswer = serializeQueuedQuizSubmission({
      ...validQueue,
      answers: [{ question_id: 2, user_answer: [2, 0] }]
    })
    expect(deserializeQueuedQuizSubmission(withArrayAnswer)).not.toBeNull()

    const withMapAnswer = serializeQueuedQuizSubmission({
      ...validQueue,
      answers: [{ question_id: 3, user_answer: { CPU: "Processor", RAM: "Memory" } }]
    })
    expect(deserializeQueuedQuizSubmission(withMapAnswer)).not.toBeNull()
  })

  it("writes, reads, and clears queued submissions", async () => {
    const writeOk = await writeQueuedQuizSubmission(validQueue)
    expect(writeOk).toBe(true)

    const loaded = await readQueuedQuizSubmission(validQueue.attemptId)
    expect(loaded).toEqual(validQueue)

    await clearQueuedQuizSubmission(validQueue.attemptId)
    const afterClear = await readQueuedQuizSubmission(validQueue.attemptId)
    expect(afterClear).toBeNull()
  })
})
