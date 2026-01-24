type SourceIds = {
  documentIds: string[]
  chunkIds: string[]
  corpus?: string
}

type SourceLike = {
  metadata?: Record<string, unknown>
} & Record<string, unknown>

const normalizeId = (value: unknown): string | null => {
  if (value == null) return null
  const asString = String(value).trim()
  return asString.length > 0 ? asString : null
}

export const extractSourceFeedbackIds = (source: SourceLike | null | undefined): SourceIds => {
  const metadata = source?.metadata || {}
  const docId =
    normalizeId(metadata.document_id) ||
    normalizeId(metadata.doc_id) ||
    normalizeId(metadata.documentId) ||
    normalizeId(metadata.docId) ||
    normalizeId(source?.document_id) ||
    normalizeId(source?.doc_id) ||
    normalizeId(source?.documentId) ||
    normalizeId(source?.docId)
  const chunkId =
    normalizeId(metadata.chunk_id) ||
    normalizeId(metadata.chunkId) ||
    normalizeId(source?.chunk_id) ||
    normalizeId(source?.chunkId)
  const corpus =
    normalizeId(metadata.corpus) ||
    normalizeId(metadata.namespace) ||
    normalizeId(metadata.index) ||
    normalizeId(source?.corpus) ||
    normalizeId(source?.namespace) ||
    undefined

  return {
    documentIds: docId ? [docId] : [],
    chunkIds: chunkId ? [chunkId] : [],
    corpus
  }
}

export const getSourceImpressionId = (
  source: SourceLike | null | undefined,
  index?: number
): string => {
  const { documentIds, chunkIds } = extractSourceFeedbackIds(source)
  if (chunkIds.length > 0) return chunkIds[0]
  if (documentIds.length > 0) return documentIds[0]
  const url = normalizeId(source?.url)
  if (url) return `url:${url}`
  const name = normalizeId(source?.name)
  if (name) return `name:${name}`
  return typeof index === "number" ? `index:${index}` : "unknown"
}

export const getSourceFeedbackKey = (
  source: SourceLike | null | undefined,
  index?: number
): string => {
  const { documentIds, chunkIds } = extractSourceFeedbackIds(source)
  if (chunkIds.length > 0) return `chunk:${chunkIds[0]}`
  if (documentIds.length > 0) return `doc:${documentIds[0]}`
  return getSourceImpressionId(source, index)
}

export const collectImpressionList = (sources: SourceLike[] = []): string[] => {
  return sources.map((source, index) => getSourceImpressionId(source, index))
}
