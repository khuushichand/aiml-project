import React from 'react'

const OPERATOR_TOKENS = new Set(['AND', 'OR', 'NOT'])
const QUERY_TOKEN_REGEX = /"([^"]+)"|(\S+)/g

interface HighlightMatchesOptions {
  caseSensitive?: boolean
  highlightClassName?: string
}

export const tokenizeSearchQuery = (query: string): string[] => {
  const terms: string[] = []
  const seen = new Set<string>()

  for (const match of query.matchAll(QUERY_TOKEN_REGEX)) {
    const quotedToken = match[1]
    const rawToken = match[2]

    let token = (quotedToken ?? rawToken ?? '').trim()
    if (!token) continue

    if (!quotedToken) {
      token = token.replace(/^[-+]/, '')
      if (!token || OPERATOR_TOKENS.has(token.toUpperCase())) {
        continue
      }
    }

    const normalized = token.toLowerCase()
    if (seen.has(normalized)) continue
    seen.add(normalized)
    terms.push(token)
  }

  return terms
}

const escapeForRegex = (value: string): string => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

export const highlightMatches = (
  text: string,
  query: string,
  options: HighlightMatchesOptions = {}
): React.ReactNode => {
  if (!text || !query.trim()) {
    return text
  }

  const {
    caseSensitive = false,
    highlightClassName = 'bg-warn/20 rounded px-0.5'
  } = options

  const terms = tokenizeSearchQuery(query)
  if (terms.length === 0) {
    return text
  }

  const pattern = terms
    .slice()
    .sort((a, b) => b.length - a.length)
    .map((term) => escapeForRegex(term))
    .join('|')

  if (!pattern) {
    return text
  }

  const regex = new RegExp(`(${pattern})`, caseSensitive ? 'g' : 'gi')
  const parts = text.split(regex)
  if (parts.length === 1) {
    return text
  }

  return (
    <>
      {parts.map((part, index) => {
        const isMatch = terms.some((term) =>
          caseSensitive ? part === term : part.toLowerCase() === term.toLowerCase()
        )
        if (!isMatch) {
          return part
        }
        return (
          <mark key={`${part}-${index}`} className={highlightClassName}>
            {part}
          </mark>
        )
      })}
    </>
  )
}
