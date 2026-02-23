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

let composerNodeSeed = 0

export const createComposerNodeId = (prefix = "block"): string => {
  composerNodeSeed += 1
  return `${prefix}-${composerNodeSeed}`
}

export const createComposerNode = (
  type: ComposerNodeType,
  source?: string
): ComposerNode => ({
  id: createComposerNodeId(type.replace(/Block$/, "").toLowerCase()),
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
