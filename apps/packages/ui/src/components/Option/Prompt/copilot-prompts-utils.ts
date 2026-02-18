export type CopilotPromptLike = {
  key?: string | null
  prompt?: string | null
}

export const matchesCopilotPromptSearchText = (
  prompt: CopilotPromptLike,
  queryLower: string,
  keyLabel: string
): boolean => {
  if (!queryLower) {
    return true
  }

  const haystack = [prompt?.key, keyLabel, prompt?.prompt]
  return haystack.some((field) =>
    typeof field === "string" ? field.toLowerCase().includes(queryLower) : false
  )
}

export const filterCopilotPrompts = <T extends CopilotPromptLike>(
  prompts: T[],
  options: {
    keyFilter?: string
    queryLower?: string
    resolveKeyLabel?: (key: string) => string
  }
): T[] => {
  const keyFilter = options.keyFilter || "all"
  const queryLower = (options.queryLower || "").trim().toLowerCase()

  return prompts.filter((prompt) => {
    const key = typeof prompt?.key === "string" ? prompt.key : ""
    if (keyFilter !== "all" && key !== keyFilter) {
      return false
    }

    const label = key
      ? options.resolveKeyLabel?.(key) || key
      : ""
    return matchesCopilotPromptSearchText(prompt, queryLower, label)
  })
}
