/**
 * Comparison mode state contract for Knowledge QA.
 *
 * Stage 4 deliverable: define the model and validation logic before
 * rendering a full side-by-side UI.
 */

export const KNOWLEDGE_QA_COMPARISON_PHASES = [
  "phase_1_manual_pairing",
  "phase_2_shared_source_overlap",
  "phase_3_diff_and_verdicts",
] as const

export type ComparisonStatus = "draft" | "ready"

export type ComparisonSide = {
  query: string
  threadId: string | null
  messageId: string | null
  answer: string | null
  citationIndices: number[]
}

export type KnowledgeQaComparisonDraft = {
  id: string
  createdAt: string
  updatedAt: string
  status: ComparisonStatus
  left: ComparisonSide
  right: ComparisonSide
}

export type CreateComparisonDraftInput = {
  id?: string
  left: Partial<ComparisonSide> & { query?: string }
  right: Partial<ComparisonSide> & { query?: string }
  nowIso?: string
}

const sanitizeQuery = (value: unknown): string =>
  typeof value === "string" ? value.trim() : ""

const sanitizeCitationIndices = (value: unknown): number[] => {
  if (!Array.isArray(value)) return []
  const seen = new Set<number>()
  const normalized: number[] = []
  for (const raw of value) {
    if (typeof raw !== "number" || !Number.isFinite(raw)) continue
    const candidate = Math.max(1, Math.floor(raw))
    if (seen.has(candidate)) continue
    seen.add(candidate)
    normalized.push(candidate)
  }
  return normalized
}

const buildSide = (side: Partial<ComparisonSide> & { query?: string }): ComparisonSide => ({
  query: sanitizeQuery(side.query),
  threadId: typeof side.threadId === "string" ? side.threadId : null,
  messageId: typeof side.messageId === "string" ? side.messageId : null,
  answer: typeof side.answer === "string" ? side.answer : null,
  citationIndices: sanitizeCitationIndices(side.citationIndices),
})

const computeStatus = (left: ComparisonSide, right: ComparisonSide): ComparisonStatus =>
  left.query.length > 0 && right.query.length > 0 ? "ready" : "draft"

export const createComparisonDraft = (
  input: CreateComparisonDraftInput
): KnowledgeQaComparisonDraft => {
  const nowIso = input.nowIso || new Date().toISOString()
  const left = buildSide(input.left)
  const right = buildSide(input.right)

  return {
    id:
      typeof input.id === "string" && input.id.trim().length > 0
        ? input.id.trim()
        : `comparison-${nowIso}`,
    createdAt: nowIso,
    updatedAt: nowIso,
    status: computeStatus(left, right),
    left,
    right,
  }
}

export const updateComparisonDraft = (
  draft: KnowledgeQaComparisonDraft,
  updates: Partial<{
    left: Partial<ComparisonSide>
    right: Partial<ComparisonSide>
    nowIso: string
  }>
): KnowledgeQaComparisonDraft => {
  const nextLeft = updates.left ? buildSide({ ...draft.left, ...updates.left }) : draft.left
  const nextRight = updates.right
    ? buildSide({ ...draft.right, ...updates.right })
    : draft.right

  return {
    ...draft,
    left: nextLeft,
    right: nextRight,
    updatedAt: updates.nowIso || new Date().toISOString(),
    status: computeStatus(nextLeft, nextRight),
  }
}

export const isComparisonReady = (draft: KnowledgeQaComparisonDraft): boolean =>
  draft.status === "ready"
