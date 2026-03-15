import type { Quiz, QuizGenerateSource } from "@/services/quizzes"

export type QuizSourceSummary = {
  media: number
  notes: number
  flashcards: number
}

const isNonEmptyString = (value: unknown): value is string => (
  typeof value === "string" && value.trim().length > 0
)

const normalizeBundle = (bundle: Quiz["source_bundle_json"]): QuizGenerateSource[] => {
  if (!Array.isArray(bundle)) return []
  return bundle.filter((source): source is QuizGenerateSource => (
    source != null &&
    isNonEmptyString(source.source_type) &&
    isNonEmptyString(source.source_id)
  ))
}

export const summarizeQuizSources = (quiz: Pick<Quiz, "source_bundle_json" | "media_id">): QuizSourceSummary => {
  const summary: QuizSourceSummary = {
    media: 0,
    notes: 0,
    flashcards: 0
  }

  const bundle = normalizeBundle(quiz.source_bundle_json)
  bundle.forEach((source) => {
    if (source.source_type === "media") {
      summary.media += 1
      return
    }
    if (source.source_type === "note") {
      summary.notes += 1
      return
    }
    if (source.source_type === "flashcard_deck" || source.source_type === "flashcard_card") {
      summary.flashcards += 1
    }
  })

  if (bundle.length === 0 && quiz.media_id != null) {
    summary.media = 1
  }

  return summary
}
