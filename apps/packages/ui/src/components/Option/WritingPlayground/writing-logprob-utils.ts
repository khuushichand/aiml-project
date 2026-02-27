export type WritingTopLogprob = {
  token: string
  logprob: number
}

export type WritingLogprobEntry = {
  token: string
  logprob: number
  topLogprobs: WritingTopLogprob[]
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

const toFiniteNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return null
}

const normalizeTopLogprobsObject = (value: unknown): WritingTopLogprob[] => {
  if (!isRecord(value)) return []
  return Object.entries(value)
    .map(([token, score]) => {
      const logprob = toFiniteNumber(score)
      if (logprob == null) return null
      return { token: String(token), logprob }
    })
    .filter(Boolean) as WritingTopLogprob[]
}

const normalizeTopLogprobsList = (value: unknown): WritingTopLogprob[] => {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => {
      if (!isRecord(entry)) return null
      const token = String(entry.token || "")
      const logprob = toFiniteNumber(entry.logprob)
      if (!token || logprob == null) return null
      return { token, logprob }
    })
    .filter(Boolean) as WritingTopLogprob[]
}

const fromChatStyle = (choice: Record<string, unknown>): WritingLogprobEntry[] => {
  const logprobs = isRecord(choice.logprobs) ? choice.logprobs : null
  if (!logprobs || !Array.isArray(logprobs.content)) return []
  return logprobs.content
    .map((entry) => {
      if (!isRecord(entry)) return null
      const token = String(entry.token || "")
      const logprob = toFiniteNumber(entry.logprob)
      if (!token || logprob == null) return null
      const topLogprobs = normalizeTopLogprobsList(entry.top_logprobs)
      return { token, logprob, topLogprobs }
    })
    .filter(Boolean) as WritingLogprobEntry[]
}

const fromCompletionsStyle = (
  choice: Record<string, unknown>
): WritingLogprobEntry[] => {
  const logprobs = isRecord(choice.logprobs) ? choice.logprobs : null
  if (!logprobs) return []
  const tokens = Array.isArray(logprobs.tokens) ? logprobs.tokens : []
  const tokenLogprobs = Array.isArray(logprobs.token_logprobs)
    ? logprobs.token_logprobs
    : []
  const topLogprobs = Array.isArray(logprobs.top_logprobs)
    ? logprobs.top_logprobs
    : []
  if (tokens.length === 0 || tokenLogprobs.length === 0) return []
  const total = Math.min(tokens.length, tokenLogprobs.length)
  const entries: WritingLogprobEntry[] = []
  for (let index = 0; index < total; index += 1) {
    const token = String(tokens[index] || "")
    const logprob = toFiniteNumber(tokenLogprobs[index])
    if (!token || logprob == null) continue
    entries.push({
      token,
      logprob,
      topLogprobs: normalizeTopLogprobsObject(topLogprobs[index])
    })
  }
  return entries
}

export const extractLogprobEntriesFromChunk = (
  chunk: unknown
): WritingLogprobEntry[] => {
  if (!isRecord(chunk)) return []
  const choices = Array.isArray(chunk.choices) ? chunk.choices : []
  const entries: WritingLogprobEntry[] = []
  for (const rawChoice of choices) {
    if (!isRecord(rawChoice)) continue
    const chatEntries = fromChatStyle(rawChoice)
    if (chatEntries.length > 0) {
      entries.push(...chatEntries)
      continue
    }
    entries.push(...fromCompletionsStyle(rawChoice))
  }
  return entries
}

export const logprobToProbability = (logprob: number): number => {
  const normalized = Number.isFinite(logprob) ? logprob : Number.NEGATIVE_INFINITY
  return Math.exp(normalized)
}
