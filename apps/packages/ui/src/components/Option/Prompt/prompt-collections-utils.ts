export type PromptCollectionRecord = {
  collection_id: number
  name: string
  description?: string | null
  prompt_ids: number[]
}

const toPositiveInteger = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isInteger(value) && value > 0) {
    return value
  }
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number.parseInt(value, 10)
    if (Number.isInteger(parsed) && parsed > 0) {
      return parsed
    }
  }
  return null
}

export const getPromptCollectionMembershipId = (prompt: any): number | null => {
  const serverId = toPositiveInteger(prompt?.serverId)
  if (serverId) return serverId
  return toPositiveInteger(prompt?.id)
}

export const isPromptInCollection = (
  prompt: any,
  collectionPromptIds: ReadonlySet<number>
): boolean => {
  const promptId = getPromptCollectionMembershipId(prompt)
  if (!promptId) return false
  return collectionPromptIds.has(promptId)
}

export const mergePromptIdsForCollection = (
  existingPromptIds: number[],
  prompts: any[]
): {
  promptIds: number[]
  added: number
  skipped: number
} => {
  const mergedPromptIds: number[] = []
  const seen = new Set<number>()

  for (const id of existingPromptIds) {
    const normalized = toPositiveInteger(id)
    if (!normalized || seen.has(normalized)) continue
    seen.add(normalized)
    mergedPromptIds.push(normalized)
  }

  let added = 0
  let skipped = 0

  for (const prompt of prompts) {
    const normalized = getPromptCollectionMembershipId(prompt)
    if (!normalized) {
      skipped += 1
      continue
    }
    if (seen.has(normalized)) continue
    seen.add(normalized)
    mergedPromptIds.push(normalized)
    added += 1
  }

  return {
    promptIds: mergedPromptIds,
    added,
    skipped
  }
}

