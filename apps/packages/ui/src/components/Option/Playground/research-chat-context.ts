import { buildChatLinkedResearchPath } from "./research-run-status"

const MAX_ATTACHED_RESEARCH_CLAIMS = 5
const MAX_ATTACHED_RESEARCH_UNRESOLVED_QUESTIONS = 5

type RecordLike = Record<string, unknown>

type AttachedResearchOutlineSection = {
  title: string
}

type AttachedResearchClaim = {
  text: string
}

type AttachedResearchVerificationSummary = {
  unsupported_claim_count?: number
}

type AttachedResearchSourceTrustSummary = {
  high_trust_count?: number
}

export type AttachedResearchContext = {
  attached_at: string
  run_id: string
  query: string
  question: string
  outline: AttachedResearchOutlineSection[]
  key_claims: AttachedResearchClaim[]
  unresolved_questions: string[]
  verification_summary?: AttachedResearchVerificationSummary
  source_trust_summary?: AttachedResearchSourceTrustSummary
  research_url: string
}

export type DeepResearchCompletionMetadata = {
  run_id: string
  query: string
  kind: "completion_handoff"
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
