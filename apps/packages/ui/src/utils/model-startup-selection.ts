type StartupModelDescriptor = {
  model?: unknown
}

type ResolveStartupSelectedModelParams = {
  currentModel: string | null | undefined
  models: StartupModelDescriptor[] | null | undefined
  preferredModelIds?: string[] | null | undefined
  isCurrentModelHydrating?: boolean
  arePreferencesHydrating?: boolean
}

const normalizeModelId = (value: unknown): string | null => {
  if (typeof value !== "string") return null
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

export const resolveStartupSelectedModel = ({
  currentModel,
  models,
  preferredModelIds,
  isCurrentModelHydrating = false,
  arePreferencesHydrating = false
}: ResolveStartupSelectedModelParams): string | null => {
  if (isCurrentModelHydrating || arePreferencesHydrating) {
    return null
  }

  if (normalizeModelId(currentModel)) {
    return null
  }

  const modelList = Array.isArray(models) ? models : []
  if (modelList.length === 0) {
    return null
  }

  const preferred = new Set(
    (preferredModelIds || [])
      .map((id) => normalizeModelId(id))
      .filter((id): id is string => Boolean(id))
  )

  if (preferred.size > 0) {
    for (const model of modelList) {
      const modelId = normalizeModelId(model?.model)
      if (modelId && preferred.has(modelId)) {
        return modelId
      }
    }
  }

  for (const model of modelList) {
    const modelId = normalizeModelId(model?.model)
    if (modelId) {
      return modelId
    }
  }

  return null
}
