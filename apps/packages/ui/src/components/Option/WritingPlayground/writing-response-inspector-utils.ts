import {
  logprobToProbability,
  type WritingLogprobEntry
} from "./writing-logprob-utils"

export type ResponseInspectorSort =
  | "sequence"
  | "logprob_desc"
  | "logprob_asc"
  | "probability_desc"
  | "probability_asc"

export type ResponseInspectorRow = {
  sequence: number
  token: string
  logprob: number
  probability: number
  whitespaceOnly: boolean
  topLogprobs: Array<{ token: string; logprob: number }>
}

const compareRows = (
  left: ResponseInspectorRow,
  right: ResponseInspectorRow,
  sort: ResponseInspectorSort
): number => {
  if (sort === "sequence") {
    return left.sequence - right.sequence
  }
  if (sort === "logprob_desc") {
    if (right.logprob !== left.logprob) return right.logprob - left.logprob
    return left.sequence - right.sequence
  }
  if (sort === "logprob_asc") {
    if (left.logprob !== right.logprob) return left.logprob - right.logprob
    return left.sequence - right.sequence
  }
  if (sort === "probability_desc") {
    if (right.probability !== left.probability) {
      return right.probability - left.probability
    }
    return left.sequence - right.sequence
  }
  if (left.probability !== right.probability) {
    return left.probability - right.probability
  }
  return left.sequence - right.sequence
}

const matchesQuery = (row: ResponseInspectorRow, query: string): boolean => {
  if (!query) return true
  const normalized = query.toLowerCase()
  if (row.token.toLowerCase().includes(normalized)) return true
  return row.topLogprobs.some((entry) =>
    entry.token.toLowerCase().includes(normalized)
  )
}

export const normalizeInspectorToken = (token: string): string =>
  token.replace(/\r/g, "\\r").replace(/\n/g, "\\n").replace(/\t/g, "\\t")

export const selectResponseInspectorRows = (
  rows: WritingLogprobEntry[],
  options: {
    query: string
    hideWhitespaceOnly: boolean
    sort: ResponseInspectorSort
    maxRows: number
  }
): ResponseInspectorRow[] => {
  const normalizedRows = rows
    .map((row, index) => ({
      sequence: index,
      token: normalizeInspectorToken(row.token),
      logprob: row.logprob,
      probability: logprobToProbability(row.logprob),
      whitespaceOnly: row.token.trim().length === 0,
      topLogprobs: row.topLogprobs.map((entry) => ({
        token: normalizeInspectorToken(entry.token),
        logprob: entry.logprob
      }))
    }))
    .filter((row) =>
      options.hideWhitespaceOnly ? !row.whitespaceOnly : true
    )
    .filter((row) => matchesQuery(row, options.query.trim()))

  normalizedRows.sort((left, right) => compareRows(left, right, options.sort))
  return normalizedRows.slice(0, Math.max(1, options.maxRows))
}

const csvEscape = (value: string): string => `"${value.replace(/"/g, '""')}"`

export const buildResponseInspectorCsv = (
  rows: ResponseInspectorRow[]
): string => {
  const lines = [
    "index,token,logprob,probability,top_alternatives",
    ...rows.map((row) => {
      const alternatives = row.topLogprobs
        .map((entry) => `${entry.token} (${entry.logprob.toFixed(3)})`)
        .join(" | ")
      return [
        row.sequence + 1,
        csvEscape(row.token),
        row.logprob.toFixed(6),
        row.probability.toFixed(8),
        csvEscape(alternatives)
      ].join(",")
    })
  ]
  return lines.join("\n")
}

export const buildRerollPromptFromRows = (
  rows: WritingLogprobEntry[],
  options: {
    prefix: string
    suffix: string
    sequence: number
    replacementToken?: string
    placeholder?: string
  }
): string => {
  const max = rows.length
  const clamped = Math.max(0, Math.min(max, Math.floor(options.sequence)))
  const generatedPrefix = rows
    .slice(0, clamped)
    .map((row) => row.token)
    .join("")
  const placeholder = options.placeholder ?? "{predict}"
  const replacementToken =
    typeof options.replacementToken === "string" ? options.replacementToken : ""
  return `${options.prefix}${generatedPrefix}${replacementToken}${placeholder}${options.suffix}`
}
