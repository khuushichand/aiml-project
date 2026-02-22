export type CitationSegment =
  | { type: "text"; value: string }
  | { type: "citation"; index: number }

const CITATION_REGEX = /\[(\d+)\]/g

export const splitCitationSegments = (text: string): CitationSegment[] => {
  if (!text) return []

  const segments: CitationSegment[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = CITATION_REGEX.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: "text", value: text.slice(lastIndex, match.index) })
    }

    const citationIndex = Number.parseInt(match[1], 10)
    if (Number.isFinite(citationIndex)) {
      segments.push({ type: "citation", index: citationIndex })
    } else {
      segments.push({ type: "text", value: match[0] })
    }

    lastIndex = match.index + match[0].length
  }

  if (lastIndex < text.length) {
    segments.push({ type: "text", value: text.slice(lastIndex) })
  }

  return segments
}

type MarkdownNode = {
  type?: string
  value?: string
  url?: string
  children?: MarkdownNode[]
}

const NON_TRAVERSABLE_TYPES = new Set(["code", "inlineCode", "link", "linkReference"])

const toCitationLinkNode = (index: number): MarkdownNode => ({
  type: "link",
  url: `citation://${index}`,
  children: [{ type: "text", value: `[${index}]` }],
})

const transformCitationTextNodes = (node: MarkdownNode) => {
  if (!node || !Array.isArray(node.children)) return

  const nextChildren: MarkdownNode[] = []
  for (const child of node.children) {
    if (child?.type === "text" && typeof child.value === "string") {
      const segments = splitCitationSegments(child.value)
      const hasCitation = segments.some((segment) => segment.type === "citation")

      if (!hasCitation) {
        nextChildren.push(child)
        continue
      }

      for (const segment of segments) {
        if (segment.type === "text") {
          if (segment.value.length > 0) {
            nextChildren.push({ type: "text", value: segment.value })
          }
          continue
        }
        nextChildren.push(toCitationLinkNode(segment.index))
      }
      continue
    }

    if (child?.type && !NON_TRAVERSABLE_TYPES.has(child.type)) {
      transformCitationTextNodes(child)
    }
    nextChildren.push(child)
  }

  node.children = nextChildren
}

export const remarkCitationLinks = () => (tree: MarkdownNode) => {
  transformCitationTextNodes(tree)
}
