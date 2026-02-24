export type ComposerNodeType =
  | "HeaderBlock"
  | "IntroSummaryBlock"
  | "ItemLoopBlock"
  | "GroupSectionBlock"
  | "CtaFooterBlock"
  | "FinalFlowCheckBlock"
  | "RawCodeBlock"

export interface ComposerNode {
  id: string
  type: ComposerNodeType
  source: string
  enabled?: boolean
  config?: Record<string, unknown>
}

export interface ComposerAst {
  schema_version: string
  nodes: ComposerNode[]
}

export interface ComposerBlockDefinition {
  type: ComposerNodeType
  label: string
}

export const COMPOSER_SCHEMA_VERSION = "1.0.0"

export const CORE_BLOCK_DEFINITIONS: ComposerBlockDefinition[] = [
  { type: "HeaderBlock", label: "Header" },
  { type: "IntroSummaryBlock", label: "Intro Summary" },
  { type: "ItemLoopBlock", label: "Item Loop" },
  { type: "GroupSectionBlock", label: "Group Section" },
  { type: "CtaFooterBlock", label: "CTA Footer" },
  { type: "FinalFlowCheckBlock", label: "Final Flow Check" }
]

export const DEFAULT_BLOCK_SOURCE: Record<ComposerNodeType, string> = {
  HeaderBlock: "# {{ title }}",
  IntroSummaryBlock: "{% if has_briefing_summary %}\n{{ briefing_summary }}\n{% endif %}",
  ItemLoopBlock:
    "{% for item in items %}\n## {{ item.title }}\n{{ item.summary or item.llm_summary or '' }}\n{% endfor %}",
  GroupSectionBlock:
    "{% for group in groups %}\n## {{ group.name }}\n{% for item in group.items %}\n- {{ item.title }}\n{% endfor %}\n{% endfor %}",
  CtaFooterBlock: "For feedback or requests, reply to this newsletter.",
  FinalFlowCheckBlock: "{# final flow-check placeholder #}",
  RawCodeBlock: ""
}

const normalizeIdPrefix = (prefix: string): string => {
  const cleaned = String(prefix || "block")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
  return cleaned || "block"
}

let fallbackNodeSeed = 0

const createRandomNodeSuffix = (): string => {
  const cryptoApi = globalThis.crypto
  if (cryptoApi && typeof cryptoApi.randomUUID === "function") {
    return cryptoApi.randomUUID().replace(/-/g, "").slice(0, 12)
  }
  fallbackNodeSeed += 1
  return `${Date.now().toString(36)}${fallbackNodeSeed.toString(36)}`
}

export const createComposerNodeId = (prefix = "block", existingIds?: Iterable<string>): string => {
  const normalizedPrefix = normalizeIdPrefix(prefix)
  const existing = new Set(existingIds ?? [])
  let candidate = `${normalizedPrefix}-${createRandomNodeSuffix()}`
  while (existing.has(candidate)) {
    candidate = `${normalizedPrefix}-${createRandomNodeSuffix()}`
  }
  return candidate
}

export const createComposerNode = (
  type: ComposerNodeType,
  source?: string,
  existingIds?: Iterable<string>
): ComposerNode => ({
  id: createComposerNodeId(type.replace(/Block$/, "").toLowerCase(), existingIds),
  type,
  source: typeof source === "string" ? source : DEFAULT_BLOCK_SOURCE[type],
  enabled: true
})

export const createEmptyComposerAst = (): ComposerAst => ({
  schema_version: COMPOSER_SCHEMA_VERSION,
  nodes: []
})

export const isPromptCapableBlock = (type: ComposerNodeType): boolean =>
  type !== "HeaderBlock" && type !== "RawCodeBlock" && type !== "FinalFlowCheckBlock"
