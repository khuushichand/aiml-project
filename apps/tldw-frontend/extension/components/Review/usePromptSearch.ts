import React from "react"

import { getAllPrompts } from "@/db/dexie/helpers"
import { tldwClient } from "@/services/tldw/TldwApiClient"

export type PromptSearchResult = {
  id?: string
  title: string
  content: string
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object"

const dedupePromptResults = (
  items: PromptSearchResult[]
): PromptSearchResult[] => {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = `${item.title}:${item.content.slice(0, 64)}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export const usePromptSearch = () => {
  const [query, setQuery] = React.useState("")
  const [results, setResults] = React.useState<PromptSearchResult[]>([])
  const [loading, setLoading] = React.useState(false)
  const [includeLocal, setIncludeLocal] = React.useState(true)
  const [includeServer, setIncludeServer] = React.useState(true)

  const clearResults = React.useCallback(() => {
    setResults([])
  }, [])

  const search = React.useCallback(
    async (q: string) => {
      const trimmed = q.trim()
      if (!trimmed) {
        setResults([])
        return
      }

      setLoading(true)
      try {
        let merged: PromptSearchResult[] = []
        if (includeLocal) {
          const locals = await getAllPrompts()
          const filtered = (locals || [])
            .filter(
              (prompt) =>
                prompt.title?.toLowerCase().includes(trimmed.toLowerCase()) ||
                prompt.content?.toLowerCase().includes(trimmed.toLowerCase())
            )
            .map((prompt) => ({
              id: prompt.id,
              title: prompt.title,
              content: prompt.content
            }))
          merged = merged.concat(filtered)
        }

        if (includeServer) {
          await tldwClient.initialize().catch(() => null)
          const res = await tldwClient.searchPrompts(trimmed).catch(() => null)
          const list: Record<string, unknown>[] = Array.isArray(res)
            ? res.filter(isRecord)
            : isRecord(res) && Array.isArray(res.results)
              ? res.results.filter(isRecord)
              : isRecord(res) && Array.isArray(res.prompts)
                ? res.prompts.filter(isRecord)
                : []
          merged = merged.concat(
            list.map((entry) => {
              const rawId = entry.id
              const id =
                typeof rawId === "string"
                  ? rawId
                  : typeof rawId === "number"
                    ? String(rawId)
                    : undefined
              return {
                id,
                title: String(entry.title || entry.name || "Untitled"),
                content: String(entry.content || entry.prompt || "")
              }
            })
          )
        }

        setResults(dedupePromptResults(merged).slice(0, 50))
      } finally {
        setLoading(false)
      }
    },
    [includeLocal, includeServer]
  )

  return {
    query,
    setQuery,
    results,
    loading,
    includeLocal,
    setIncludeLocal,
    includeServer,
    setIncludeServer,
    search,
    clearResults
  }
}
