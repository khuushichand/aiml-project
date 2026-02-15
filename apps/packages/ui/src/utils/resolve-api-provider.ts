type ResolveApiProviderOptions = {
  modelId?: string | null
  explicitProvider?: string | null
  providerHint?: string | null
}

const normalizeProvider = (value: unknown): string => {
  const trimmed = String(value || "").trim().toLowerCase()
  if (!trimmed || trimmed === "unknown") return ""
  return trimmed
}

export const resolveApiProviderForModel = async ({
  explicitProvider
}: ResolveApiProviderOptions): Promise<string | undefined> => {
  const explicit = normalizeProvider(explicitProvider)
  if (explicit) return explicit
  return undefined
}
