export type TakeTabNavigationSource = "generate" | "create" | "manage" | "results"

export type TakeTabNavigationIntent = {
  startQuizId?: number | null
  highlightQuizId?: number | null
  sourceTab?: TakeTabNavigationSource | null
  attemptId?: number | null
}
