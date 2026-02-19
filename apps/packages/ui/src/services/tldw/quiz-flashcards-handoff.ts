export type FlashcardsStudyIntent = {
  quizId?: number
  attemptId?: number
  deckId?: number
}

export type QuizAssessmentIntent = {
  startQuizId?: number
  highlightQuizId?: number
  deckId?: number
  deckName?: string
  sourceAttemptId?: number
  assignmentMode?: "shared"
  assignmentDueAt?: string
  assignmentNote?: string
  assignedByRole?: string
}

const extractSearchFromHash = (hash: string): string => {
  const questionMarkIndex = hash.indexOf("?")
  if (questionMarkIndex < 0) return ""
  return hash.slice(questionMarkIndex)
}

const toSearchParams = (search: string): URLSearchParams => {
  const normalized = search.startsWith("?") ? search.slice(1) : search
  return new URLSearchParams(normalized)
}

const parsePositiveInt = (value: string | null): number | undefined => {
  if (!value) return undefined
  const parsed = Number.parseInt(value, 10)
  if (Number.isNaN(parsed) || parsed <= 0) return undefined
  return parsed
}

const parseNonEmptyString = (value: string | null): string | undefined => {
  if (typeof value !== "string") return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

const parseSharedAssignmentMode = (value: string | null): "shared" | undefined => {
  if (typeof value !== "string") return undefined
  return value.trim().toLowerCase() === "shared" ? "shared" : undefined
}

const parseIsoDateString = (value: string | null): string | undefined => {
  const trimmed = parseNonEmptyString(value)
  if (!trimmed) return undefined
  const parsed = new Date(trimmed)
  if (Number.isNaN(parsed.getTime())) return undefined
  return parsed.toISOString()
}

const parseFlashcardsStudyIntentFromParams = (
  params: URLSearchParams
): FlashcardsStudyIntent | null => {
  const hasSignal =
    params.get("study_source") === "quiz" ||
    params.has("quiz_id") ||
    params.has("attempt_id") ||
    params.has("deck_id")
  if (!hasSignal) return null

  const intent: FlashcardsStudyIntent = {
    quizId: parsePositiveInt(params.get("quiz_id")),
    attemptId: parsePositiveInt(params.get("attempt_id")),
    deckId: parsePositiveInt(params.get("deck_id"))
  }

  if (!intent.quizId && !intent.attemptId && !intent.deckId) {
    return null
  }

  return intent
}

const parseQuizAssessmentIntentFromParams = (
  params: URLSearchParams
): QuizAssessmentIntent | null => {
  const hasSignal =
    params.get("source") === "flashcards" ||
    params.has("start_quiz_id") ||
    params.has("highlight_quiz_id") ||
    params.has("deck_id") ||
    params.has("deck_name") ||
    params.has("assignment_mode") ||
    params.has("assignment_due_at") ||
    params.has("assignment_note") ||
    params.has("assigned_by_role")
  if (!hasSignal) return null

  const intent: QuizAssessmentIntent = {
    startQuizId: parsePositiveInt(params.get("start_quiz_id")),
    highlightQuizId: parsePositiveInt(params.get("highlight_quiz_id")),
    deckId: parsePositiveInt(params.get("deck_id")),
    deckName: parseNonEmptyString(params.get("deck_name")),
    sourceAttemptId: parsePositiveInt(params.get("source_attempt_id")),
    assignmentMode: parseSharedAssignmentMode(params.get("assignment_mode")),
    assignmentDueAt: parseIsoDateString(params.get("assignment_due_at")),
    assignmentNote: parseNonEmptyString(params.get("assignment_note")),
    assignedByRole: parseNonEmptyString(params.get("assigned_by_role"))
  }

  if (
    !intent.startQuizId &&
    !intent.highlightQuizId &&
    !intent.deckId &&
    !intent.deckName &&
    !intent.sourceAttemptId &&
    !intent.assignmentMode &&
    !intent.assignmentDueAt &&
    !intent.assignmentNote &&
    !intent.assignedByRole
  ) {
    return null
  }

  return intent
}

export const parseFlashcardsStudyIntentFromSearch = (
  search: string
): FlashcardsStudyIntent | null => {
  return parseFlashcardsStudyIntentFromParams(toSearchParams(search))
}

export const parseFlashcardsStudyIntentFromLocation = (locationLike: {
  search?: string
  hash?: string
}): FlashcardsStudyIntent | null => {
  const fromSearch = parseFlashcardsStudyIntentFromSearch(locationLike.search || "")
  if (fromSearch) return fromSearch
  return parseFlashcardsStudyIntentFromSearch(extractSearchFromHash(locationLike.hash || ""))
}

export const parseQuizAssessmentIntentFromSearch = (
  search: string
): QuizAssessmentIntent | null => {
  return parseQuizAssessmentIntentFromParams(toSearchParams(search))
}

export const parseQuizAssessmentIntentFromLocation = (locationLike: {
  search?: string
  hash?: string
}): QuizAssessmentIntent | null => {
  const fromSearch = parseQuizAssessmentIntentFromSearch(locationLike.search || "")
  if (fromSearch) return fromSearch
  return parseQuizAssessmentIntentFromSearch(extractSearchFromHash(locationLike.hash || ""))
}

export const buildFlashcardsStudyRouteFromQuiz = (
  intent: FlashcardsStudyIntent
): string => {
  const params = new URLSearchParams()
  params.set("tab", "review")
  params.set("study_source", "quiz")

  if (intent.quizId && intent.quizId > 0) {
    params.set("quiz_id", String(intent.quizId))
  }
  if (intent.attemptId && intent.attemptId > 0) {
    params.set("attempt_id", String(intent.attemptId))
  }
  if (intent.deckId && intent.deckId > 0) {
    params.set("deck_id", String(intent.deckId))
  }

  return `/flashcards?${params.toString()}`
}

export const buildQuizAssessmentRouteFromFlashcards = (
  intent: QuizAssessmentIntent
): string => {
  const params = new URLSearchParams()
  params.set("tab", "take")
  params.set("source", "flashcards")

  const startQuizId = intent.startQuizId && intent.startQuizId > 0 ? intent.startQuizId : undefined
  const highlightQuizId =
    intent.highlightQuizId && intent.highlightQuizId > 0
      ? intent.highlightQuizId
      : startQuizId

  if (startQuizId) {
    params.set("start_quiz_id", String(startQuizId))
  }
  if (highlightQuizId) {
    params.set("highlight_quiz_id", String(highlightQuizId))
  }
  if (intent.deckId && intent.deckId > 0) {
    params.set("deck_id", String(intent.deckId))
  }
  if (intent.sourceAttemptId && intent.sourceAttemptId > 0) {
    params.set("source_attempt_id", String(intent.sourceAttemptId))
  }
  const deckName = parseNonEmptyString(intent.deckName ?? null)
  if (deckName) {
    params.set("deck_name", deckName)
  }

  return `/quiz?${params.toString()}`
}
