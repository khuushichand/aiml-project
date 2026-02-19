export type TakeTabNavigationSource =
  | "generate"
  | "create"
  | "manage"
  | "results"
  | "flashcards"
  | "assignment"

export type TakeTabNavigationIntent = {
  startQuizId?: number | null
  highlightQuizId?: number | null
  sourceTab?: TakeTabNavigationSource | null
  attemptId?: number | null
  assignmentMode?: "shared" | null
  assignmentDueAt?: string | null
  assignmentNote?: string | null
  assignedByRole?: string | null
}
