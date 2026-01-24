import type { ChatMessage } from "@/services/tldw/TldwApiClient"
import type {
  WritingPromptChunk,
  WritingSessionPayload,
  WritingTemplatePayload,
  WritingWorldInfo
} from "@/types/writing"
import { DEFAULT_SESSION } from "@/components/Option/WritingPlayground/presets"

const MAX_CACHE_SIZE = 100
const lenientPrefixCache = new Map<string, RegExp>()
const lenientCache = new Map<string, RegExp>()

const boundedSet = <K, V>(map: Map<K, V>, key: K, value: V) => {
  if (map.size >= MAX_CACHE_SIZE) {
    const firstKey = map.keys().next().value
    if (firstKey !== undefined) map.delete(firstKey)
  }
  map.set(key, value)
}

export const joinPrompt = (prompt: WritingPromptChunk[]) =>
  prompt.map((chunk) => chunk.content).join("")

export const replacePlaceholders = (
  input: string,
  placeholders: Record<string, string>
) =>
  input
    .replace(/\{[^}]+\}/g, (placeholder) =>
      Object.prototype.hasOwnProperty.call(placeholders, placeholder)
        ? placeholders[placeholder]
        : placeholder
    )
    .replace(/\\n/g, "\n")

export const replaceNewlines = (template: WritingTemplatePayload) => {
  return Object.fromEntries(
    Object.entries(template).map(([key, value]) => [
      key,
      typeof value === "string" ? value.replaceAll("\\n", "\n") : value
    ])
  ) as WritingTemplatePayload
}

export const regexSplitString = (
  value: string,
  separator: string,
  limit?: number
): [string[], string[]] => {
  const result: string[] = []
  const separators: string[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null
  const regex = new RegExp(separator, "g")

  while ((match = regex.exec(value)) !== null) {
    if (limit !== undefined && result.length >= limit) break
    result.push(value.slice(lastIndex, match.index))
    separators.push(match[0])
    lastIndex = match.index + match[0].length
  }

  result.push(value.slice(lastIndex))
  return [result, separators]
}

export const regexIndexOf = (value: string, regex: RegExp, start = 0) => {
  const indexOf = value.substring(start).search(regex)
  return indexOf >= 0 ? indexOf + start : indexOf
}

export const regexLastIndexOf = (value: string, regex: RegExp, start?: number) => {
  const flags = Array.from(new Set((regex.flags || "") + "g")).join("")
  const newRegex = new RegExp(regex.source, flags)
  let startPos = start
  if (typeof startPos === "undefined") {
    startPos = value.length
  } else if (startPos < 0) {
    startPos = 0
  }
  const stringToWorkWith = value.substring(0, startPos + 1)
  let lastIndex = -1
  let nextStop = 0
  let result: RegExpExecArray | null
  while ((result = newRegex.exec(stringToWorkWith)) != null) {
    lastIndex = result.index
    newRegex.lastIndex = ++nextStop
  }
  return lastIndex
}

const escapeRegExp = (value: string) =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")

const makeWhiteSpaceLenient = (value: string) =>
  value
    .replace(/\s+/g, "")
    .replace(/(?<!\\)(?:\\{2})*(?!\s)(?!$)/g, "$&\\s*")

export const createLenientPrefixRegex = (prefix: string) => {
  if (!prefix) return /^/
  const cached = lenientPrefixCache.get(prefix)
  if (cached) return cached
  const regex = new RegExp(`^${makeWhiteSpaceLenient(escapeRegExp(prefix))}`, "i")
  boundedSet(lenientPrefixCache, prefix, regex)
  return regex
}

export const createLenientRegex = (value: string) => {
  if (!value) return /$^/
  const cached = lenientCache.get(value)
  if (cached) return cached
  const regex = new RegExp(
    makeWhiteSpaceLenient(escapeRegExp(value)).replace(/^\\s\*/, "(^\\s*)?"),
    "i"
  )
  boundedSet(lenientCache, value, regex)
  return regex
}

export const prefixMatchLength = (left: string, right: string) => {
  if (left === "" || right === "") return 0
  for (let len = left.length; len > 0; len--) {
    const sub = left.substring(left.length - len)
    if (right.startsWith(sub)) return len
  }
  return 0
}

export const convertChatToMessages = (
  chatString: string,
  template?: WritingTemplatePayload
): ChatMessage[] => {
  if (!template || typeof template !== "object") {
    return [{ role: "user", content: chatString }]
  }

  const messages: ChatMessage[] = []
  const { sysPre, sysSuf, instPre, instSuf } = replaceNewlines(template)
  let remaining = chatString.trimStart()

  const indices = [sysPre, instPre]
    .map((prefix) => (prefix ? regexIndexOf(remaining, createLenientPrefixRegex(prefix)) : -1))
    .filter((index) => index !== -1)
  const minIndex = indices.length > 0 ? Math.min(...indices) : remaining.length
  if (minIndex !== 0 && instPre) {
    const matchLen = prefixMatchLength(instPre.trim(), remaining)
    remaining = instPre + remaining.substring(matchLen)
  }

  const extractMessage = (
    text: string,
    prefix: string,
    suffixes: string[],
    role: ChatMessage["role"]
  ) => {
    const matches = prefix ? text.match(createLenientPrefixRegex(prefix)) : null
    if (!matches || !matches.length) return null
    let working = text.substring(matches[0].length)
    let endIndex = suffixes[0]
      ? regexIndexOf(working, createLenientRegex(suffixes[0]))
      : -1
    if (endIndex === -1) {
      if (suffixes.length > 1) {
        const indices = suffixes
          .slice(1)
          .map((suffix) => (suffix ? regexIndexOf(working, createLenientRegex(suffix)) : -1))
          .filter((index) => index !== -1)
        endIndex = indices.length > 0 ? Math.min(...indices) : working.length
      } else {
        endIndex = working.length
      }
    }
    let content = working.substring(0, endIndex)
    content = endIndex !== working.length ? content.trim() : content.trimLeft()
    return {
      message: { role, content },
      remainingString: working.substring(endIndex)
    }
  }

  const skipToNextKnownPrefix = (text: string, ...prefixes: Array<string | undefined>) => {
    const indices = prefixes
      .map((prefix) => (prefix ? regexIndexOf(text, createLenientRegex(prefix)) : -1))
      .filter((index) => index !== -1)
    const nextIndex = indices.length > 0 ? Math.min(...indices) : text.length
    if (nextIndex === 0) return ""
    return text.substring(nextIndex)
  }

  while (remaining.length > 0) {
    let extracted = null
    if (sysPre) {
      extracted = extractMessage(remaining, sysPre, [sysSuf || "", instPre || "", instSuf || ""], "system")
    }
    if (instPre && !extracted) {
      extracted = extractMessage(remaining, instPre, [instSuf || ""], "user")
    }
    if (instSuf && !extracted) {
      extracted = extractMessage(remaining, instSuf, [instPre || ""], "assistant")
    }
    if (!extracted) {
      remaining = skipToNextKnownPrefix(remaining, sysPre, instPre, instSuf)
      continue
    }
    const { message, remainingString } = extracted
    if (message.content.length > 0) messages.push(message)
    remaining = remainingString
  }

  const last = messages.at(-1)
  if (last && last.role === "assistant" && !last.content) {
    messages.pop()
  }
  return messages
}

export const applyFimTemplate = (
  promptChunks: WritingPromptChunk[],
  template?: WritingTemplatePayload
) => {
  const fillPlaceholder = "{fill}"
  const predictPlaceholder = "{predict}"

  const placeholderRegex = template?.fimTemplate
    ? `${escapeRegExp(predictPlaceholder)}|${escapeRegExp(fillPlaceholder)}`
    : escapeRegExp(predictPlaceholder)

  let leftPromptChunks: WritingPromptChunk[] | undefined
  let rightPromptChunks: WritingPromptChunk[] | undefined
  let foundPlaceholder: string | undefined

  for (let i = 0; i < promptChunks.length; i++) {
    const chunk = promptChunks[i]
    if (chunk.type !== "user") continue
    if (chunk.content.includes(fillPlaceholder) || chunk.content.includes(predictPlaceholder)) {
      const [sides, separators] = regexSplitString(chunk.content, placeholderRegex, 1)
      foundPlaceholder = separators[0]
      let left = sides[0]
      if ((left.at(-2) !== " " && left.at(-2) !== "\t") && left.at(-1) === " ") {
        left = left.substring(0, left.length - 1)
      }
      leftPromptChunks = [
        ...promptChunks.slice(0, i),
        ...(left ? [{ type: "user" as const, content: left }] : [])
      ]

      const right = sides[1]
      rightPromptChunks = [
        ...(right ? [{ type: "user" as const, content: right }] : []),
        ...promptChunks.slice(i + 1)
      ]
      break
    }
  }

  if (!foundPlaceholder || !leftPromptChunks || !rightPromptChunks) {
    return {
      modifiedPromptText: joinPrompt(promptChunks)
    }
  }

  let modifiedPromptText = ""
  if (foundPlaceholder === "{fill}" && template?.fimTemplate) {
    const prefix = joinPrompt(leftPromptChunks)
    const suffix = joinPrompt(rightPromptChunks)
    modifiedPromptText = replacePlaceholders(template.fimTemplate, {
      "{prefix}": prefix,
      "{suffix}": suffix
    })
  } else {
    modifiedPromptText = joinPrompt(leftPromptChunks)
  }

  return {
    modifiedPromptText,
    fimPromptInfo: {
      fimLeftChunks: leftPromptChunks,
      fimRightChunks: rightPromptChunks,
      fimPlaceholder: foundPlaceholder
    }
  }
}

export const assembleWorldInfo = (
  prompt: string,
  worldInfo: WritingWorldInfo,
  tokenRatio: number
) => {
  const entries = Array.isArray(worldInfo.entries) ? worldInfo.entries : []
  const validEntries = entries.filter(
    (entry) =>
      entry.keys.length > 0 &&
      !(entry.keys.length === 1 && entry.keys[0] === "") &&
      entry.text !== ""
  )
  const activeEntries = validEntries.filter((entry) => {
    const searchRange = Number(entry.search)
    const resolvedRange = Number.isFinite(searchRange) ? searchRange : 2048
    const sliceLength = Math.max(0, Math.round(resolvedRange * tokenRatio))
    const searchPrompt = prompt.substring(Math.max(0, prompt.length - sliceLength))
    const searchPromptLower = searchPrompt.toLowerCase()
    return entry.keys.some((key) => {
      if (!searchPromptLower.length) return false
      if (typeof key !== "string" || !key) return false
      return searchPromptLower.includes(key.toLowerCase())
    })
  })

  return activeEntries.length > 0
    ? activeEntries.map((entry) => entry.text).join("\n")
    : ""
}

export const buildAdditionalContext = (params: {
  promptText: string
  contextLength: number
  tokenRatio: number
  memoryTokens: WritingSessionPayload["memoryTokens"]
  authorNoteTokens: WritingSessionPayload["authorNoteTokens"]
  authorNoteDepth: number
  worldInfo: WritingWorldInfo
  assembledWorldInfo: string
  defaultContextOrder: string
}) => {
  const {
    promptText,
    contextLength,
    tokenRatio,
    memoryTokens,
    authorNoteTokens,
    authorNoteDepth,
    worldInfo,
    assembledWorldInfo,
    defaultContextOrder
  } = params

  const authorNote = authorNoteTokens.text
    ? [authorNoteTokens.prefix, authorNoteTokens.text, authorNoteTokens.suffix].join("")
    : ""

  const contextReplacements: Record<string, string> = {
    "{wiPrefix}": assembledWorldInfo ? worldInfo.prefix : "",
    "{wiText}": assembledWorldInfo,
    "{wiSuffix}": assembledWorldInfo ? worldInfo.suffix : "",
    "{memPrefix}": memoryTokens.text || assembledWorldInfo ? memoryTokens.prefix : "",
    "{memText}": memoryTokens.text,
    "{memSuffix}": memoryTokens.text || assembledWorldInfo ? memoryTokens.suffix : "",
    "{prompt}": ""
  }

  const additionalContext = Object.values(contextReplacements).join("").length
  const estimatedStart = Math.round(
    promptText.length - contextLength * tokenRatio + additionalContext
  )
  const startIndex = Math.max(0, estimatedStart + 1)
  const truncatedPrompt = promptText.substring(startIndex)

  const promptLines = truncatedPrompt.match(/.*\n?/g) || []
  const depth = Math.min(promptLines.length, authorNoteDepth)
  const insertIndex = Math.max(0, promptLines.length - depth - 1)
  if (authorNote) {
    promptLines.splice(insertIndex, 0, authorNote)
  }
  const authorNotePrompt = authorNote ? promptLines.join("") : truncatedPrompt
  contextReplacements["{prompt}"] = authorNotePrompt

  const contextOrder = memoryTokens.contextOrder || defaultContextOrder
  return contextOrder
    .split("\n")
    .map((line) => replacePlaceholders(line, contextReplacements))
    .filter((line) => line.trim() !== "")
    .join("\n")
    .replace(/\\n/g, "\n")
}

const parseJsonMaybe = (value: string) => {
  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}

const coercePromptChunks = (
  value: unknown,
  fallback: WritingPromptChunk[]
): WritingPromptChunk[] => {
  if (!value) return fallback
  if (typeof value === "string") {
    return [{ type: "user", content: value }]
  }
  if (!Array.isArray(value)) return fallback
  const chunks = value
    .map((item) => {
      if (!item) return null
      if (typeof item === "string") {
        return { type: "user", content: item }
      }
      if (typeof item === "object") {
        const record = item as WritingPromptChunk
        if (record.type && typeof record.content === "string") {
          return record
        }
        const contentValue = (record as { content?: unknown }).content
        const content =
          typeof contentValue === "string"
            ? contentValue
            : String(contentValue ?? "")
        return { type: "user", content }
      }
      return null
    })
    .filter(Boolean) as WritingPromptChunk[]
  return chunks.length > 0 ? chunks : fallback
}

export const normalizeSessionPayload = (
  raw: unknown,
  defaults: WritingSessionPayload = DEFAULT_SESSION
): WritingSessionPayload => {
  if (!raw || typeof raw !== "object") {
    return { ...defaults }
  }
  const payload = raw as Record<string, unknown>
  const normalized: WritingSessionPayload = { ...defaults }
  const normalizedRecord = normalized as Record<string, unknown>

  ;(Object.keys(defaults) as Array<keyof WritingSessionPayload>).forEach((key) => {
    const value = payload[key]
    const defaultValue = defaults[key]
    if (value === undefined || value === null) {
      return
    }
    if (typeof defaultValue === "number") {
      const numeric =
        typeof value === "string"
          ? Number(value)
          : typeof value === "number"
            ? value
            : Number.NaN
      normalizedRecord[key] = Number.isFinite(numeric) ? numeric : defaultValue
      return
    }
    if (typeof defaultValue === "boolean") {
      if (typeof value === "string") {
        normalizedRecord[key] = value === "true"
      } else {
        normalizedRecord[key] = Boolean(value)
      }
      return
    }
    if (Array.isArray(defaultValue)) {
      if (typeof value === "string") {
        const parsed = parseJsonMaybe(value)
        normalizedRecord[key] = Array.isArray(parsed) ? parsed : defaultValue
      } else if (Array.isArray(value)) {
        normalizedRecord[key] = value
      }
      return
    }
    if (typeof defaultValue === "object" && defaultValue !== null) {
      if (typeof value === "string") {
        const parsed = parseJsonMaybe(value)
        normalizedRecord[key] =
          typeof parsed === "object" && parsed
            ? {
                ...(defaultValue as Record<string, unknown>),
                ...(parsed as Record<string, unknown>)
              }
            : defaultValue
      } else if (typeof value === "object" && value) {
        normalizedRecord[key] = {
          ...(defaultValue as Record<string, unknown>),
          ...(value as Record<string, unknown>)
        }
      }
      return
    }
    if (typeof value === "string") {
      normalizedRecord[key] = value
    }
  })

  normalized.prompt = coercePromptChunks(
    payload.prompt ?? payload.promptChunks,
    defaults.prompt
  )

  const endpointModel = payload.endpointModel
  if (!normalized.model && typeof endpointModel === "string") {
    normalized.model = endpointModel
  }
  const selectedTemplate = payload.selectedTemplate
  if (!normalized.template && typeof selectedTemplate === "string") {
    normalized.template = selectedTemplate
  }

  if (!normalized.prompt.length) {
    normalized.prompt = defaults.prompt
  }

  return normalized
}
