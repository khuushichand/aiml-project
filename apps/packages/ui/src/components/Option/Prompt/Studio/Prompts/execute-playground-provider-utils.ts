type UnknownRecord = Record<string, unknown>

export type ExecuteProviderInfo = {
  name: string
  label: string
  models: string[]
  defaultModel: string | null
}

export type ExecuteProvidersCatalog = {
  providers: ExecuteProviderInfo[]
  defaultProvider: string | null
}

const asRecord = (value: unknown): UnknownRecord | null => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null
  return value as UnknownRecord
}

const toStringValue = (value: unknown): string | null => {
  if (typeof value === "string") {
    const trimmed = value.trim()
    return trimmed.length > 0 ? trimmed : null
  }
  if (typeof value === "number" && Number.isFinite(value)) return String(value)
  return null
}

const toModelName = (entry: unknown): string | null => {
  const direct = toStringValue(entry)
  if (direct) return direct

  const record = asRecord(entry)
  if (!record) return null

  return (
    toStringValue(record.name) ||
    toStringValue(record.id) ||
    toStringValue(record.model_id) ||
    toStringValue(record.display_name)
  )
}

const dedupeStrings = (items: string[]): string[] => {
  const seen = new Set<string>()
  const deduped: string[] = []
  items.forEach((item) => {
    const key = item.toLowerCase()
    if (seen.has(key)) return
    seen.add(key)
    deduped.push(item)
  })
  return deduped
}

export const normalizeExecuteProvidersCatalog = (
  payload: unknown
): ExecuteProvidersCatalog => {
  const root = asRecord(payload)
  const providersRaw = Array.isArray(root?.providers) ? root.providers : []
  const defaultProviderRaw = toStringValue(root?.default_provider)

  const providers: ExecuteProviderInfo[] = providersRaw
    .map((entry) => {
      const provider = asRecord(entry)
      if (!provider) return null

      const name =
        toStringValue(provider.name) || toStringValue(provider.provider) || null
      if (!name) return null

      const label =
        toStringValue(provider.display_name) ||
        toStringValue(provider.label) ||
        name

      const modelsFromArray = Array.isArray(provider.models)
        ? provider.models.map(toModelName).filter(Boolean)
        : []
      const modelsFromInfo = Array.isArray(provider.models_info)
        ? provider.models_info.map(toModelName).filter(Boolean)
        : []
      const models = dedupeStrings([
        ...(modelsFromArray as string[]),
        ...(modelsFromInfo as string[])
      ])

      const defaultModel = toStringValue(provider.default_model) || models[0] || null

      return {
        name,
        label,
        models,
        defaultModel
      }
    })
    .filter((provider): provider is ExecuteProviderInfo => provider !== null)

  const defaultProvider =
    providers.find((provider) => provider.name === defaultProviderRaw)?.name ||
    defaultProviderRaw ||
    providers[0]?.name ||
    null

  return {
    providers,
    defaultProvider
  }
}

export const getExecuteProviderOptions = (catalog: ExecuteProvidersCatalog) =>
  catalog.providers.map((provider) => ({
    value: provider.name,
    label: provider.label
  }))

const getProviderByName = (
  catalog: ExecuteProvidersCatalog,
  providerName?: string | null
): ExecuteProviderInfo | null => {
  const targetName = providerName || catalog.defaultProvider
  if (!targetName) return null
  return (
    catalog.providers.find((provider) => provider.name === targetName) || null
  )
}

export const getExecuteModelOptions = (
  catalog: ExecuteProvidersCatalog,
  providerName?: string | null
) => {
  const provider = getProviderByName(catalog, providerName)
  if (!provider) return []
  return provider.models.map((model) => ({ value: model, label: model }))
}

export const getExecuteDefaultProvider = (
  catalog: ExecuteProvidersCatalog
): string | null => catalog.defaultProvider

export const getExecuteDefaultModel = (
  catalog: ExecuteProvidersCatalog,
  providerName?: string | null
): string | null => {
  const provider = getProviderByName(catalog, providerName)
  if (!provider) return null
  return provider.defaultModel || provider.models[0] || null
}

export const isValidExecuteProvider = (
  catalog: ExecuteProvidersCatalog,
  providerName?: string | null
): boolean => {
  if (!providerName) return true
  if (catalog.providers.length === 0) return true
  return catalog.providers.some((provider) => provider.name === providerName)
}

export const isValidExecuteModel = (
  catalog: ExecuteProvidersCatalog,
  providerName: string | null | undefined,
  modelName?: string | null
): boolean => {
  if (!modelName) return true
  if (catalog.providers.length === 0) return true

  const provider = getProviderByName(catalog, providerName)
  if (!provider) return true
  return provider.models.includes(modelName)
}
