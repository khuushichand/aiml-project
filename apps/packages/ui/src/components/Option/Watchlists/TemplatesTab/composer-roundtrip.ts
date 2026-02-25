import {
  COMPOSER_SCHEMA_VERSION,
  createEmptyComposerAst,
  DEFAULT_BLOCK_SOURCE,
  type ComposerAst,
  type ComposerNode,
  type ComposerNodeType
} from "./composer-types"

const UNSUPPORTED_JINJA_TOKENS = [
  "{% macro",
  "{% include",
  "{% extends",
  "{% import",
  "{% from",
  "{% block",
  "{% call"
]

const ITEM_LOOP_PATTERN = /{%\s*for\s+item\s+in\s+items\s*%}[\s\S]*?{%\s*endfor\s*%}/m

const looksLikeHeaderBlock = (source: string): boolean => {
  const trimmed = source.trim()
  return trimmed.startsWith("#") && trimmed.includes("{{ title }}")
}

const deterministicTypeKey = (type: ComposerNodeType): string =>
  type
    .replace(/Block$/, "")
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .toLowerCase()

const createDeterministicNode = (
  type: ComposerNodeType,
  source: string,
  counters: Record<string, number>
): ComposerNode => {
  const key = deterministicTypeKey(type)
  counters[key] = (counters[key] || 0) + 1
  return {
    id: `${key}-${counters[key]}`,
    type,
    source: source.trim(),
    enabled: true
  }
}

const rawCodeNode = (source: string, counters: Record<string, number>): ComposerNode =>
  createDeterministicNode("RawCodeBlock", source, counters)

const headerOrRawNode = (source: string, counters: Record<string, number>): ComposerNode =>
  looksLikeHeaderBlock(source)
    ? createDeterministicNode("HeaderBlock", source, counters)
    : rawCodeNode(source, counters)

export const parseTemplateToComposerAst = (content: string): ComposerAst => {
  const normalized = String(content || "").trim()
  const idCounters: Record<string, number> = {}
  if (!normalized) {
    return createEmptyComposerAst()
  }

  if (UNSUPPORTED_JINJA_TOKENS.some((token) => normalized.includes(token))) {
    return {
      schema_version: COMPOSER_SCHEMA_VERSION,
      nodes: [rawCodeNode(normalized, idCounters)]
    }
  }

  const loopMatch = ITEM_LOOP_PATTERN.exec(normalized)
  if (!loopMatch) {
    return {
      schema_version: COMPOSER_SCHEMA_VERSION,
      nodes: [headerOrRawNode(normalized, idCounters)]
    }
  }

  const prefix = normalized.slice(0, loopMatch.index).trim()
  const loopSourceRaw = loopMatch[0]
  const loopSource = loopSourceRaw.trim()
  const suffix = normalized.slice(loopMatch.index + loopSourceRaw.length).trim()
  const nodes: ComposerNode[] = []

  if (prefix) {
    nodes.push(headerOrRawNode(prefix, idCounters))
  }
  nodes.push(createDeterministicNode("ItemLoopBlock", loopSource, idCounters))
  if (suffix) {
    nodes.push(headerOrRawNode(suffix, idCounters))
  }

  return {
    schema_version: COMPOSER_SCHEMA_VERSION,
    nodes
  }
}

export const compileComposerAstToTemplate = (ast: ComposerAst): string => {
  const nodes = Array.isArray(ast?.nodes) ? ast.nodes : []
  const parts: string[] = []

  for (const node of nodes) {
    const source = String(node?.source || "").trim()
    if (source) {
      parts.push(source)
      continue
    }
    const fallback = DEFAULT_BLOCK_SOURCE[node.type] || ""
    if (fallback) {
      parts.push(fallback)
    }
  }

  return parts.join("\n\n").trim()
}

const hashString = (value: string): string => {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(16)
}

export const computeComposerSyncHash = (content: string, ast: ComposerAst): string =>
  hashString(`${content}\n::\n${JSON.stringify(ast)}`)
