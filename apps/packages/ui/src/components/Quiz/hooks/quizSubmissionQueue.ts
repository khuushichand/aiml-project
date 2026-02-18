import type { QuizAnswer } from "@/services/quizzes"

const QUEUED_SUBMISSION_PREFIX = "quiz-attempt-submit-queue-v1:"
const SUBMISSION_STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000 // 24 hours

export type QueuedQuizSubmission = {
  attemptId: number
  quizId: number
  answers: Omit<QuizAnswer, "is_correct">[]
  allowPartial: boolean
  queuedAt: number
  retryCount: number
  lastAttemptedAt: number
  lastError?: string
}

const keyForAttempt = (attemptId: number) => `${QUEUED_SUBMISSION_PREFIX}${attemptId}`

const isPlainObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value != null

const isValidAnswerEntry = (value: unknown): value is Omit<QuizAnswer, "is_correct"> => {
  if (!isPlainObject(value)) return false
  if (typeof value.question_id !== "number") return false
  const answerValue = value.user_answer
  return typeof answerValue === "string" || typeof answerValue === "number"
}

export const isQueuedQuizSubmission = (
  value: unknown
): value is QueuedQuizSubmission => {
  if (!isPlainObject(value)) return false
  if (typeof value.attemptId !== "number") return false
  if (typeof value.quizId !== "number") return false
  if (!Array.isArray(value.answers) || !value.answers.every(isValidAnswerEntry)) return false
  if (typeof value.allowPartial !== "boolean") return false
  if (typeof value.queuedAt !== "number") return false
  if (typeof value.retryCount !== "number") return false
  if (typeof value.lastAttemptedAt !== "number") return false
  if (value.lastError != null && typeof value.lastError !== "string") return false
  return true
}

export const serializeQueuedQuizSubmission = (
  submission: QueuedQuizSubmission
): string => JSON.stringify(submission)

export const deserializeQueuedQuizSubmission = (
  raw: string | null
): QueuedQuizSubmission | null => {
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!isQueuedQuizSubmission(parsed)) return null
    if (Date.now() - parsed.queuedAt > SUBMISSION_STALE_THRESHOLD_MS) {
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export const readQueuedQuizSubmission = async (
  attemptId: number
): Promise<QueuedQuizSubmission | null> => {
  if (typeof window === "undefined") return null
  const key = keyForAttempt(attemptId)
  try {
    const parsed = deserializeQueuedQuizSubmission(window.localStorage.getItem(key))
    if (!parsed) {
      window.localStorage.removeItem(key)
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export const writeQueuedQuizSubmission = async (
  submission: QueuedQuizSubmission
): Promise<boolean> => {
  if (typeof window === "undefined") return false
  try {
    window.localStorage.setItem(
      keyForAttempt(submission.attemptId),
      serializeQueuedQuizSubmission(submission)
    )
    return true
  } catch {
    return false
  }
}

export const clearQueuedQuizSubmission = async (attemptId: number): Promise<void> => {
  if (typeof window === "undefined") return
  try {
    window.localStorage.removeItem(keyForAttempt(attemptId))
  } catch {
    // ignore storage errors
  }
}
