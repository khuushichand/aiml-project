import type { PromptSearchField, PromptSearchItem } from "@/services/prompts-api"

export type TagMatchMode = "any" | "all"

export const PROMPT_SEARCH_FIELDS: PromptSearchField[] = [
  "name",
  "author",
  "details",
  "system_prompt",
  "user_prompt",
  "keywords"
]

export const matchesTagFilter = (
  promptKeywords: string[] = [],
  selectedTags: string[],
  mode: TagMatchMode
): boolean => {
  if (selectedTags.length === 0) {
    return true
  }

  if (mode === "all") {
    return selectedTags.every((tag) => promptKeywords.includes(tag))
  }

  return promptKeywords.some((tag) => selectedTags.includes(tag))
}

export const matchesPromptSearchText = (
  prompt: any,
  queryLower: string,
  getPromptKeywords: (prompt: any) => string[]
): boolean => {
  if (!queryLower) {
    return true
  }

  const haystack = [
    prompt?.title,
    prompt?.name,
    prompt?.content,
    prompt?.system_prompt,
    prompt?.user_prompt,
    prompt?.details,
    prompt?.author,
    ...(getPromptKeywords(prompt) || [])
  ]

  return haystack.some((field: unknown) =>
    typeof field === "string" ? field.toLowerCase().includes(queryLower) : false
  )
}

export const mapServerSearchItemsToLocalPrompts = <T extends { serverId?: number | null }>(
  serverItems: PromptSearchItem[],
  localPrompts: T[]
): T[] => {
  if (!Array.isArray(serverItems) || serverItems.length === 0) {
    return []
  }

  const localByServerId = new Map<number, T>()
  for (const prompt of localPrompts) {
    if (typeof prompt?.serverId === "number") {
      localByServerId.set(prompt.serverId, prompt)
    }
  }

  const mapped: T[] = []
  for (const item of serverItems) {
    const localPrompt = localByServerId.get(item.id)
    if (localPrompt) {
      mapped.push(localPrompt)
    }
  }

  return mapped
}
