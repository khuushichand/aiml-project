import {
  recommendQuickChatWorkflowGuides,
  type QuickChatWorkflowGuide,
  type QuickChatWorkflowRecommendation
} from "./workflow-guides"

type QuickChatRagDoc = {
  content?: string
  text?: string
  chunk?: string
  metadata?: Record<string, unknown>
}

type QuickChatRagCitation = {
  title: string
  source?: string
  url?: string
}

type BuildQuickChatRagReplyOptions = {
  query?: string
  currentRoute?: string | null
  guides?: QuickChatWorkflowGuide[]
}

const getDocText = (doc: QuickChatRagDoc): string =>
  String(doc.content || doc.text || doc.chunk || "").trim()

const toStringValue = (value: unknown): string | undefined => {
  if (typeof value !== "string") return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

const truncate = (value: string, max: number): string =>
  value.length <= max ? value : `${value.slice(0, max - 1)}…`

const getDocTitle = (doc: QuickChatRagDoc, index: number): string => {
  const metadata = doc.metadata || {}
  return (
    toStringValue(metadata.title) ||
    toStringValue(metadata.source) ||
    `Document ${index + 1}`
  )
}

const normalizeCitations = (
  rawResponse: Record<string, unknown>,
  docs: QuickChatRagDoc[]
): QuickChatRagCitation[] => {
  const rawCitations = rawResponse.citations
  if (Array.isArray(rawCitations) && rawCitations.length > 0) {
    return rawCitations
      .map((item) => {
        if (!item || typeof item !== "object") return null
        const entry = item as Record<string, unknown>
        const citation: QuickChatRagCitation = {
          title:
            toStringValue(entry.title) ||
            toStringValue(entry.source) ||
            "Reference",
          source: toStringValue(entry.source),
          url: toStringValue(entry.url)
        }
        return citation
      })
      .filter((item): item is QuickChatRagCitation => item !== null)
  }

  return docs.map((doc, index) => {
    const metadata = doc.metadata || {}
    return {
      title: getDocTitle(doc, index),
      source: toStringValue(metadata.source),
      url: toStringValue(metadata.url)
    }
  })
}

const buildSuggestedPagesSection = (
  recommendations: QuickChatWorkflowRecommendation[]
): string => {
  if (recommendations.length === 0) return ""
  const lines = recommendations.map((recommendation) => {
    const currentPageNote = recommendation.isCurrentRoute ? " (current page)" : ""
    return `- **${recommendation.routeLabel}** (\`${recommendation.route}\`)${currentPageNote}: ${recommendation.reason}`
  })
  return ["### Suggested Pages", ...lines].join("\n")
}

export const buildQuickChatRagReply = (
  rawResponse: unknown,
  options: BuildQuickChatRagReplyOptions = {}
): { message: string; hasContext: boolean } => {
  const responseRecord =
    rawResponse && typeof rawResponse === "object"
      ? (rawResponse as Record<string, unknown>)
      : {}

  const answer =
    toStringValue(responseRecord.generated_answer) ||
    toStringValue(responseRecord.answer) ||
    toStringValue(responseRecord.response) ||
    ""

  const docsRaw =
    (Array.isArray(responseRecord.results) && responseRecord.results) ||
    (Array.isArray(responseRecord.documents) && responseRecord.documents) ||
    (Array.isArray(responseRecord.docs) && responseRecord.docs) ||
    []

  const docs = docsRaw
    .filter((item): item is QuickChatRagDoc =>
      Boolean(item && typeof item === "object")
    )
    .slice(0, 5)

  const citations = normalizeCitations(responseRecord, docs).slice(0, 5)
  const hasContext = docs.length > 0 || citations.length > 0 || answer.length > 0
  const recommendations = recommendQuickChatWorkflowGuides({
    query: options.query,
    answer,
    citations,
    currentRoute: options.currentRoute,
    guides: options.guides
  })
  const suggestedPagesSection = buildSuggestedPagesSection(recommendations)

  if (!hasContext) {
    const fallbackSections = [
      "I could not find relevant indexed documentation for that question. Try rephrasing your goal or use Browse Guides for curated workflows."
    ]
    if (suggestedPagesSection) {
      fallbackSections.push(suggestedPagesSection)
    }
    return {
      hasContext: false,
      message: fallbackSections.join("\n\n")
    }
  }

  const body =
    answer ||
    [
      "I found relevant documentation snippets:",
      "",
      ...docs.slice(0, 3).map((doc, index) => {
        const title = getDocTitle(doc, index)
        const snippet = truncate(getDocText(doc).replace(/\s+/g, " "), 220)
        return `- **${title}**: ${snippet || "No preview text available."}`
      })
    ].join("\n")

  const responseSections = [body]

  if (citations.length === 0) {
    if (suggestedPagesSection) {
      responseSections.push(suggestedPagesSection)
    }
    return { hasContext: true, message: responseSections.join("\n\n") }
  }

  const references = citations
    .map((citation) => {
      if (citation.url) {
        return `- [${citation.title}](${citation.url})`
      }
      if (citation.source) {
        return `- ${citation.title} (${citation.source})`
      }
      return `- ${citation.title}`
    })
    .join("\n")
  responseSections.push(`### References\n${references}`)

  if (suggestedPagesSection) {
    responseSections.push(suggestedPagesSection)
  }

  return {
    hasContext: true,
    message: responseSections.join("\n\n")
  }
}
