type ModelDescriptor = {
  model?: unknown
  name?: unknown
}

export function normalizeChatModelId(value: string | null | undefined): string {
  const trimmed = String(value ?? "").trim()
  return trimmed.replace(/^tldw:/i, "")
}

export function buildAvailableChatModelIds(
  models: ModelDescriptor[] | null | undefined
): Set<string> {
  const ids = new Set<string>()
  for (const model of models || []) {
    const modelId = normalizeChatModelId(
      String(model?.model ?? model?.name ?? "")
    )
    if (modelId) {
      ids.add(modelId)
    }
  }
  return ids
}

export function findUnavailableChatModel(
  selectedModelIds: string[],
  availableModelIds: Set<string>
): string | null {
  if (availableModelIds.size === 0) {
    return null
  }

  for (const selectedModelId of selectedModelIds) {
    const normalized = normalizeChatModelId(selectedModelId)
    if (normalized && !availableModelIds.has(normalized)) {
      return normalized
    }
  }

  return null
}
