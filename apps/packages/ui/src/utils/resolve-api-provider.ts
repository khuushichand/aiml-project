import { tldwModels } from "@/services/tldw"
import { inferProviderFromModel } from "@/utils/provider-registry"

type ResolveApiProviderOptions = {
  modelId?: string | null
  explicitProvider?: string | null
  providerHint?: string | null
}

const PROVIDER_ALIASES: Record<string, string> = {
  "custom_openai_api": "custom-openai-api",
  "custom-openai-api2": "custom-openai-api-2",
  "custom_openai_api_2": "custom-openai-api-2",
  "local_llm": "local-llm",
  "llamacpp": "llama.cpp"
}

const KNOWN_PROVIDER_KEYS = new Set<string>([
  "openai",
  "anthropic",
  "cohere",
  "groq",
  "qwen",
  "openrouter",
  "deepseek",
  "mistral",
  "google",
  "gemini",
  "huggingface",
  "moonshot",
  "zai",
  "llama.cpp",
  "kobold",
  "ooba",
  "tabbyapi",
  "vllm",
  "local-llm",
  "ollama",
  "aphrodite",
  "mlx",
  "custom-openai-api",
  "custom-openai-api-2",
  "together",
  "xai",
  "siliconflow",
  "volcengine",
  "tencentcloud",
  "alibabacloud",
  "fireworks",
  "novita",
  "chutes",
  "bedrock"
])

const PROVIDER_MODEL_PREFIX_RULES: Array<[string, string]> = [
  ["deepseek", "deepseek"],
  ["moonshot", "moonshot"],
  ["claude", "anthropic"],
  ["gpt-", "openai"],
  ["o1-", "openai"],
  ["o3-", "openai"],
  ["gemini", "google"],
  ["mistral", "mistral"],
  ["qwen", "qwen"],
  ["zai", "zai"],
  ["glm", "zai"],
  ["groq", "groq"]
]

const normalizeProvider = (value: unknown): string => {
  const trimmed = String(value || "").trim().toLowerCase().replace(/\s+/g, "")
  if (!trimmed || trimmed === "unknown") return ""
  return PROVIDER_ALIASES[trimmed] ?? trimmed
}

const normalizeModelId = (value: unknown): string =>
  String(value || "").trim().replace(/^tldw:/i, "")

const normalizeKnownProvider = (value: unknown): string => {
  const normalized = normalizeProvider(value)
  if (!normalized) return ""
  if (!KNOWN_PROVIDER_KEYS.has(normalized)) return ""
  return normalized
}

const inferInlineProvider = (normalizedModelId: string): string => {
  const slashIndex = normalizedModelId.indexOf("/")
  if (slashIndex <= 0) return ""
  const prefix = normalizeProvider(normalizedModelId.slice(0, slashIndex))
  if (!prefix || !KNOWN_PROVIDER_KEYS.has(prefix)) return ""
  return prefix
}

const inferProviderFromPrefix = (normalizedModelId: string): string => {
  const lower = normalizedModelId.toLowerCase()
  for (const [prefix, provider] of PROVIDER_MODEL_PREFIX_RULES) {
    if (lower.startsWith(prefix)) {
      return provider
    }
  }
  return ""
}

const inferProviderFromServerModelCatalog = async (
  normalizedModelId: string
): Promise<string> => {
  if (!normalizedModelId) return ""
  try {
    const models = await tldwModels.getModels()
    const needle = normalizedModelId.toLowerCase()
    const matched = models.find((model) => {
      const id = normalizeModelId(model.id).toLowerCase()
      if (id === needle) return true
      const name = String(model.name || "").trim().toLowerCase()
      return name === needle
    })
    return normalizeProvider(matched?.provider)
  } catch {
    return ""
  }
}

export const resolveApiProviderForModel = async ({
  modelId,
  providerHint,
  explicitProvider
}: ResolveApiProviderOptions): Promise<string | undefined> => {
  const explicit = normalizeProvider(explicitProvider)
  if (explicit) return explicit

  const normalizedModelId = normalizeModelId(modelId)

  const inlineProvider = inferInlineProvider(normalizedModelId)
  if (inlineProvider) return inlineProvider

  const catalogProvider = await inferProviderFromServerModelCatalog(
    normalizedModelId
  )
  if (catalogProvider) return catalogProvider

  const hint = normalizeProvider(providerHint)
  if (hint) return hint

  const inferredFromRegistry = normalizeKnownProvider(
    inferProviderFromModel(normalizedModelId, "llm")
  )
  if (inferredFromRegistry) return inferredFromRegistry

  const inferredFromPrefix = normalizeKnownProvider(
    inferProviderFromPrefix(normalizedModelId)
  )
  if (inferredFromPrefix) return inferredFromPrefix

  return undefined
}
