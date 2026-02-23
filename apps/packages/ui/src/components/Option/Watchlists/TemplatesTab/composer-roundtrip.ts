import {
  COMPOSER_SCHEMA_VERSION,
  createComposerNode,
  createEmptyComposerAst,
  DEFAULT_BLOCK_SOURCE,
  type ComposerAst,
  type ComposerNode
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

const rawCodeNode = (source: string): ComposerNode =>
  createComposerNode("RawCodeBlock", source.trim())

const headerOrRawNode = (source: string): ComposerNode =>
  looksLikeHeaderBlock(source)
    ? createComposerNode("HeaderBlock", source.trim())
    : rawCodeNode(source)

export const parseTemplateToComposerAst = (content: string): ComposerAst => {
  const normalized = String(content || "").trim()
  if (!normalized) {
    return createEmptyComposerAst()
  }

  if (UNSUPPORTED_JINJA_TOKENS.some((token) => normalized.includes(token))) {
    return {
      schema_version: COMPOSER_SCHEMA_VERSION,
      nodes: [rawCodeNode(normalized)]
    }
  }

  const loopMatch = ITEM_LOOP_PATTERN.exec(normalized)
  if (!loopMatch) {
    return {
      schema_version: COMPOSER_SCHEMA_VERSION,
      nodes: [headerOrRawNode(normalized)]
    }
  }

  const prefix = normalized.slice(0, loopMatch.index).trim()
  const loopSourceRaw = loopMatch[0]
  const loopSource = loopSourceRaw.trim()
  const suffix = normalized.slice(loopMatch.index + loopSourceRaw.length).trim()
  const nodes: ComposerNode[] = []

  if (prefix) {
    nodes.push(headerOrRawNode(prefix))
  }
  nodes.push(createComposerNode("ItemLoopBlock", loopSource))
  if (suffix) {
    nodes.push(headerOrRawNode(suffix))
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
