import type { ChatResearchContext } from "@/services/tldw/TldwApiClient"
import type { DeepResearchAttachment } from "@/types/chat-session-settings"
import { buildChatLinkedResearchPath } from "./research-run-status"

const MAX_ATTACHED_RESEARCH_CLAIMS = 5
const MAX_ATTACHED_RESEARCH_UNRESOLVED_QUESTIONS = 5
const MAX_ATTACHED_RESEARCH_HISTORY = 3

type RecordLike = Record<string, unknown>

export type AttachedResearchContext = ChatResearchContext & {
  attached_at: string
}

export type DeepResearchCompletionMetadata = {
  run_id: string
  query: string
  kind: "completion_handoff"
}

export type AttachedResearchContextEdits = Partial<AttachedResearchContext>

export type AttachedResearchContextState = {
  active: AttachedResearchContext | null
  baseline: AttachedResearchContext | null
  history: AttachedResearchContext[]
}

const isRecord = (value: unknown): value is RecordLike =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value)

const asNonEmptyString = (value: unknown): string | null => {
  if (typeof value !== "string") {
    return null
  }
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

const asNonNegativeInteger = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value) && value >= 0) {
    return Math.trunc(value)
  }
  return null
}

const getOutlineSections = (outline: unknown): unknown[] => {
  if (Array.isArray(outline)) {
    return outline
  }
  if (isRecord(outline) && Array.isArray(outline.sections)) {
    return outline.sections
  }
  return []
}

export const deriveAttachedResearchContext = (
  bundle: RecordLike,
  runId: string,
  query: string
): AttachedResearchContext => {
  const question = asNonEmptyString(bundle.question) ?? query
  const outline = getOutlineSections(bundle.outline)
    .map((section) => (isRecord(section) ? asNonEmptyString(section.title) : null))
    .filter((title): title is string => title !== null)
    .map((title) => ({ title }))

  const keyClaims = Array.isArray(bundle.claims)
    ? bundle.claims
        .map((claim) => {
          if (typeof claim === "string") {
            return asNonEmptyString(claim)
          }
          if (isRecord(claim)) {
            return asNonEmptyString(claim.text)
          }
          return null
        })
        .filter((text): text is string => text !== null)
        .slice(0, MAX_ATTACHED_RESEARCH_CLAIMS)
        .map((text) => ({ text }))
    : []

  const unresolvedQuestions = Array.isArray(bundle.unresolved_questions)
    ? bundle.unresolved_questions
        .map((entry) => asNonEmptyString(entry))
        .filter((entry): entry is string => entry !== null)
        .slice(0, MAX_ATTACHED_RESEARCH_UNRESOLVED_QUESTIONS)
    : []

  const unsupportedClaimCount = isRecord(bundle.verification_summary)
    ? asNonNegativeInteger(bundle.verification_summary.unsupported_claim_count)
    : null
  const verificationSummary =
    unsupportedClaimCount === null
      ? undefined
      : { unsupported_claim_count: unsupportedClaimCount }

  const sourceTrustSummary = Array.isArray(bundle.source_trust)
    ? {
        high_trust_count: bundle.source_trust.reduce((count, entry) => {
          if (!isRecord(entry)) {
            return count
          }
          const trustTier = asNonEmptyString(entry.trust_tier)
          return trustTier?.toLowerCase() === "high" ? count + 1 : count
        }, 0)
      }
    : undefined

  return {
    attached_at: new Date().toISOString(),
    run_id: runId,
    query,
    question,
    outline,
    key_claims: keyClaims,
    unresolved_questions: unresolvedQuestions,
    verification_summary: verificationSummary,
    source_trust_summary: sourceTrustSummary,
    research_url: buildChatLinkedResearchPath(runId)
  }
}

const sanitizeOutline = (
  outline: AttachedResearchContext["outline"]
): AttachedResearchContext["outline"] =>
  Array.isArray(outline)
    ? outline
        .map((section) => asNonEmptyString(section?.title))
        .filter((title): title is string => title !== null)
        .map((title) => ({ title }))
    : []

const sanitizeKeyClaims = (
  keyClaims: AttachedResearchContext["key_claims"]
): AttachedResearchContext["key_claims"] =>
  Array.isArray(keyClaims)
    ? keyClaims
        .map((claim) => asNonEmptyString(claim?.text))
        .filter((text): text is string => text !== null)
        .map((text) => ({ text }))
    : []

const sanitizeUnresolvedQuestions = (
  unresolvedQuestions: AttachedResearchContext["unresolved_questions"]
): AttachedResearchContext["unresolved_questions"] =>
  Array.isArray(unresolvedQuestions)
    ? unresolvedQuestions
        .map((question) => asNonEmptyString(question))
        .filter((question): question is string => question !== null)
    : []

export const sanitizeAttachedResearchContext = (
  value: AttachedResearchContext
): AttachedResearchContext => {
  const question = asNonEmptyString(value.question) ?? value.query
  const unsupportedClaimCount = asNonNegativeInteger(
    value.verification_summary?.unsupported_claim_count
  )
  const highTrustCount = asNonNegativeInteger(
    value.source_trust_summary?.high_trust_count
  )

  return {
    attached_at: value.attached_at,
    run_id: value.run_id,
    query: value.query,
    question,
    outline: sanitizeOutline(value.outline),
    key_claims: sanitizeKeyClaims(value.key_claims),
    unresolved_questions: sanitizeUnresolvedQuestions(
      value.unresolved_questions
    ),
    verification_summary:
      unsupportedClaimCount === null
        ? undefined
        : { unsupported_claim_count: unsupportedClaimCount },
    source_trust_summary:
      highTrustCount === null
        ? undefined
        : { high_trust_count: highTrustCount },
    research_url: value.research_url
  }
}

export const applyAttachedResearchContextEdits = (
  current: AttachedResearchContext,
  edits: AttachedResearchContextEdits
): AttachedResearchContext =>
  sanitizeAttachedResearchContext({
    ...current,
    question:
      edits.question !== undefined ? edits.question : current.question,
    outline: edits.outline !== undefined ? edits.outline : current.outline,
    key_claims:
      edits.key_claims !== undefined ? edits.key_claims : current.key_claims,
    unresolved_questions:
      edits.unresolved_questions !== undefined
        ? edits.unresolved_questions
        : current.unresolved_questions,
    verification_summary:
      edits.verification_summary !== undefined
        ? edits.verification_summary
        : current.verification_summary,
    source_trust_summary:
      edits.source_trust_summary !== undefined
        ? edits.source_trust_summary
        : current.source_trust_summary,
    run_id: current.run_id,
    query: current.query,
    research_url: current.research_url,
    attached_at: current.attached_at
  })

export const resetAttachedResearchContext = (
  baseline: AttachedResearchContext | null
): AttachedResearchContext | null =>
  baseline ? sanitizeAttachedResearchContext(baseline) : null

const rebuildAttachedResearchContextHistory = (
  entries: AttachedResearchContext[],
  activeRunId?: string | null
): AttachedResearchContext[] => {
  const seen = new Set<string>()
  const next: AttachedResearchContext[] = []
  for (const entry of entries) {
    const sanitized = sanitizeAttachedResearchContext(entry)
    if (activeRunId && sanitized.run_id === activeRunId) {
      continue
    }
    if (seen.has(sanitized.run_id)) {
      continue
    }
    seen.add(sanitized.run_id)
    next.push(sanitized)
    if (next.length >= MAX_ATTACHED_RESEARCH_HISTORY) {
      break
    }
  }
  return next
}

export const setAttachedResearchContextActive = ({
  active,
  baseline: _baseline,
  history,
  nextActive
}: AttachedResearchContextState & {
  nextActive: AttachedResearchContext
}): AttachedResearchContextState => {
  const sanitizedNextActive = sanitizeAttachedResearchContext(nextActive)
  const nextHistory = rebuildAttachedResearchContextHistory(
    [
      ...(active && active.run_id !== sanitizedNextActive.run_id ? [active] : []),
      ...history
    ],
    sanitizedNextActive.run_id
  )

  return {
    active: sanitizedNextActive,
    baseline: sanitizedNextActive,
    history: nextHistory
  }
}

export const clearAttachedResearchContext = ({
  history
}: AttachedResearchContextState): AttachedResearchContextState => ({
  active: null,
  baseline: null,
  history: rebuildAttachedResearchContextHistory(history)
})

export const toPersistedDeepResearchAttachment = (
  value: AttachedResearchContext,
  updatedAt = new Date().toISOString()
): DeepResearchAttachment => ({
  ...sanitizeAttachedResearchContext(value),
  updatedAt
})

export const fromPersistedDeepResearchAttachment = (
  value: DeepResearchAttachment
): AttachedResearchContext => {
  const { updatedAt: _updatedAt, ...attachedContext } = value
  return sanitizeAttachedResearchContext(attachedContext)
}

export const isDeepResearchCompletionMetadata = (
  value: unknown
): value is DeepResearchCompletionMetadata => {
  if (!isRecord(value)) {
    return false
  }
  return (
    asNonEmptyString(value.run_id) !== null &&
    asNonEmptyString(value.query) !== null &&
    value.kind === "completion_handoff"
  )
}

export const toChatResearchContext = (
  value: AttachedResearchContext
): ChatResearchContext => {
  const { attached_at: _attachedAt, ...researchContext } = value
  return researchContext
}
