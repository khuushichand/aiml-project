import { buildResearchLaunchPath } from "@/routes/route-paths"
import type { ChatLinkedResearchRun } from "@/services/tldw/TldwApiClient"

export const CHAT_LINKED_RESEARCH_ACTIVE_POLL_MS = 5_000
export const CHAT_LINKED_RESEARCH_TERMINAL_POLL_MS = 30_000
export const CHAT_LINKED_RESEARCH_ERROR_POLL_MS = 60_000
export const CHAT_LINKED_RESEARCH_ERROR_BACKOFF_THRESHOLD = 3
export const CHAT_LINKED_RESEARCH_VISIBLE_TERMINAL_ROWS = 3

const CHECKPOINT_REVIEW_PHASE_REASONS: Record<string, string> = {
  awaiting_plan_review: "Plan review needed",
  awaiting_source_review: "Sources review needed",
  awaiting_sources_review: "Sources review needed",
  awaiting_outline_review: "Outline review needed"
}

export type ChatLinkedResearchActionPolicy = {
  needsReview: boolean
  reasonLabel: string | null
  primaryActionKind: "review" | "open"
  primaryActionLabel: "Review in Research" | "Open in Research"
  researchHref: string
  canUseInChat: boolean
  canFollowUp: boolean
}

export const isTerminalResearchRun = (run: ChatLinkedResearchRun): boolean =>
  run.status === "completed" || run.status === "failed" || run.status === "cancelled"

export const orderChatLinkedResearchRuns = (
  runs: ChatLinkedResearchRun[]
): ChatLinkedResearchRun[] => {
  const active: ChatLinkedResearchRun[] = []
  const terminal: ChatLinkedResearchRun[] = []
  runs.forEach((run) => {
    if (isTerminalResearchRun(run)) {
      terminal.push(run)
      return
    }
    active.push(run)
  })
  return [...active, ...terminal]
}

export const isCheckpointReviewRun = (
  run: ChatLinkedResearchRun
): boolean =>
  run.status === "waiting_human" &&
  run.phase.startsWith("awaiting_") &&
  run.phase.endsWith("_review")

export const getChatLinkedResearchReviewReason = (
  run: ChatLinkedResearchRun
): string | null => {
  if (!isCheckpointReviewRun(run)) {
    return null
  }
  if (CHECKPOINT_REVIEW_PHASE_REASONS[run.phase]) {
    return CHECKPOINT_REVIEW_PHASE_REASONS[run.phase]
  }
  return "Review needed"
}

export const getChatLinkedResearchActionPolicy = (
  run: ChatLinkedResearchRun
): ChatLinkedResearchActionPolicy => {
  const reasonLabel = getChatLinkedResearchReviewReason(run)
  const needsReview = reasonLabel !== null

  if (needsReview) {
    return {
      needsReview: true,
      reasonLabel,
      primaryActionKind: "review",
      primaryActionLabel: "Review in Research",
      researchHref: buildChatLinkedResearchPath(run.run_id),
      canUseInChat: false,
      canFollowUp: false
    }
  }

  if (run.status === "completed") {
    return {
      needsReview: false,
      reasonLabel: null,
      primaryActionKind: "open",
      primaryActionLabel: "Open in Research",
      researchHref: buildChatLinkedResearchPath(run.run_id),
      canUseInChat: true,
      canFollowUp: true
    }
  }

  return {
    needsReview: false,
    reasonLabel: null,
    primaryActionKind: "open",
    primaryActionLabel: "Open in Research",
    researchHref: buildChatLinkedResearchPath(run.run_id),
    canUseInChat: false,
    canFollowUp: false
  }
}

export const getChatLinkedResearchStatusLabel = (
  run: ChatLinkedResearchRun
): string => {
  if (
    run.phase === "awaiting_plan_review" ||
    run.phase === "awaiting_source_review" ||
    run.phase === "awaiting_outline_review"
  ) {
    return "Needs review"
  }
  if (run.status === "completed") {
    return "Completed"
  }
  if (run.status === "failed") {
    return "Failed"
  }
  if (run.status === "cancelled") {
    return "Cancelled"
  }
  if (run.control_state === "paused") {
    return "Paused"
  }
  return "Running"
}

export const getChatLinkedResearchRefetchInterval = (
  runs: ChatLinkedResearchRun[],
  consecutiveFailures: number
): number => {
  if (consecutiveFailures >= CHAT_LINKED_RESEARCH_ERROR_BACKOFF_THRESHOLD) {
    return CHAT_LINKED_RESEARCH_ERROR_POLL_MS
  }
  if (runs.some((run) => !isTerminalResearchRun(run))) {
    return CHAT_LINKED_RESEARCH_ACTIVE_POLL_MS
  }
  return CHAT_LINKED_RESEARCH_TERMINAL_POLL_MS
}

export const buildChatLinkedResearchPath = (runId: string): string =>
  buildResearchLaunchPath({ run: runId })
