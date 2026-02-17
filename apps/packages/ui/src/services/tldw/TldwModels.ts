import { Storage } from "@plasmohq/storage"
import { tldwClient, TldwModel, type TldwConfig } from "./TldwApiClient"
import { createSafeStorage } from "@/utils/safe-storage"
import { isPlaceholderApiKey } from "@/utils/api-key"
import {
  getProviderDisplayName,
  inferProviderFromModel
} from "@/utils/provider-registry"

export interface ModelInfo {
  id: string
  name: string
  provider: string
  type: 'chat' | 'embedding' | 'image' | 'other'
  capabilities?: string[]
  contextLength?: number
  description?: string
  modalities?: {
    input?: string[]
    output?: string[]
  }
}

export class TldwModelsService {
  private cachedModels: ModelInfo[] | null = null
  private lastFetchTime: number = 0
  private readonly CACHE_DURATION = 15 * 60 * 1000 // 15 minutes
  private readonly CACHE_KEY = "tldwModelsCache"
  private storage = createSafeStorage({ area: "local" })
  private storageLoaded = false
  private storageInitPromise: Promise<void> | null = null
  private inFlightFetch: Promise<ModelInfo[]> | null = null
  private cacheScopeKey: string | null = null

  private async ensureStorageLoaded() {
    if (this.storageLoaded) return
    if (!this.storageInitPromise) {
      this.storageInitPromise = (async () => {
        try {
          const cached = (await this.storage.get<any>(this.CACHE_KEY)) || null
          if (cached?.models && Array.isArray(cached.models)) {
            this.cachedModels = cached.models as ModelInfo[]
            this.lastFetchTime = Number(cached.timestamp || 0)
            this.cacheScopeKey =
              typeof cached.scope === "string" ? cached.scope : null
          }
        } catch {
          // ignore storage read failures
        } finally {
          this.storageLoaded = true
        }
      })()
    }
    await this.storageInitPromise
  }

  private async persistCache() {
    try {
      await this.storage.set(this.CACHE_KEY, {
        models: this.cachedModels,
        timestamp: this.lastFetchTime,
        scope: this.cacheScopeKey
      })
    } catch {
      // Best-effort persistence; ignore errors
    }
  }

  private isConfiguredForModels(config: TldwConfig | null): boolean {
    if (!config) return false
    const serverUrl = String(config.serverUrl || "").trim()
    if (!serverUrl) return false

    if (config.authMode === "multi-user") {
      return Boolean(String(config.accessToken || "").trim())
    }

    const key = String(config.apiKey || "").trim()
    if (!key) return false
    if (isPlaceholderApiKey(key)) return false
    return true
  }

  private buildCacheScope(config: TldwConfig | null): string {
    if (!config) return "none"
    const serverUrl = String(config.serverUrl || "").trim().toLowerCase()
    const authMode = String(config.authMode || "single-user")
    const hasAccessToken = Boolean(String(config.accessToken || "").trim())
    const hasApiKey = Boolean(String(config.apiKey || "").trim())
    const orgId = config.orgId != null ? String(config.orgId) : "none"
    return `${serverUrl}|${authMode}|${hasAccessToken ? "token" : hasApiKey ? "key" : "none"}|${orgId}`
  }

  /**
   * Get available models from tldw server
   * Uses cache to avoid frequent API calls
   */
  async getModels(
    forceRefresh: boolean = false,
    options?: { refreshOpenRouter?: boolean }
  ): Promise<ModelInfo[]> {
    await this.ensureStorageLoaded()
    const config = await tldwClient.getConfig().catch(() => null)
    const scopeKey = this.buildCacheScope(config)
    if (this.cacheScopeKey && this.cacheScopeKey !== scopeKey) {
      this.cachedModels = null
      this.lastFetchTime = 0
    }
    this.cacheScopeKey = scopeKey

    const now = Date.now()
    
    // Return cached models if available and not expired
    if (!forceRefresh && this.cachedModels && (now - this.lastFetchTime) < this.CACHE_DURATION) {
      return this.cachedModels
    }
    if (this.inFlightFetch) {
      return await this.inFlightFetch
    }

    if (!this.isConfiguredForModels(config)) {
      return this.cachedModels || []
    }

    const fetchPromise = (async () => {
      await tldwClient.initialize()
      const models = await tldwClient.getModels({
        refreshOpenRouter: options?.refreshOpenRouter === true
      })
      
      // Transform tldw models to our format
      this.cachedModels = models.map(model => this.transformModel(model))
      this.lastFetchTime = Date.now()
      await this.persistCache()
      
      return this.cachedModels
    })()

    this.inFlightFetch = fetchPromise
    try {
      return await fetchPromise
    } catch (error) {
      if (!import.meta.env?.DEV) {
        console.error('Failed to fetch models from tldw:', error)
      }
      
      // Return cached models if available, even if expired
      if (this.cachedModels) {
        return this.cachedModels
      }
      
      // Return empty array as fallback
      return []
    } finally {
      if (this.inFlightFetch === fetchPromise) {
        this.inFlightFetch = null
      }
    }
  }

  /**
   * Get chat models only
   */
  async getChatModels(
    forceRefresh: boolean = false,
    options?: { refreshOpenRouter?: boolean }
  ): Promise<ModelInfo[]> {
    const models = await this.getModels(forceRefresh, options)
    return models.filter(m => m.type === 'chat')
  }

  /**
   * Get embedding models only
   */
  async getEmbeddingModels(
    forceRefresh: boolean = false,
    options?: { refreshOpenRouter?: boolean }
  ): Promise<ModelInfo[]> {
    const models = await this.getModels(forceRefresh, options)
    return models.filter(m => m.type === 'embedding')
  }

  /**
   * Get image models only
   */
  async getImageModels(
    forceRefresh: boolean = false,
    options?: { refreshOpenRouter?: boolean }
  ): Promise<ModelInfo[]> {
    const models = await this.getModels(forceRefresh, options)
    return models.filter(m => m.type === 'image')
  }

  /**
   * Get a specific model by ID
   */
  async getModel(modelId: string): Promise<ModelInfo | null> {
    const models = await this.getModels()
    return models.find(m => m.id === modelId) || null
  }

  /**
   * Check if a model exists
   */
  async modelExists(modelId: string): Promise<boolean> {
    const model = await this.getModel(modelId)
    return model !== null
  }

  /**
   * Get models grouped by provider
   */
  async getModelsByProvider(): Promise<Map<string, ModelInfo[]>> {
    const models = await this.getModels()
    const grouped = new Map<string, ModelInfo[]>()
    
    for (const model of models) {
      const provider = model.provider
      if (!grouped.has(provider)) {
        grouped.set(provider, [])
      }
      grouped.get(provider)!.push(model)
    }
    
    return grouped
  }

  /**
   * Transform tldw model to our format
   */
  private transformModel(tldwModel: TldwModel): ModelInfo {
    const nameLower = tldwModel.name.toLowerCase()
    const declaredType = (tldwModel.type || "").trim().toLowerCase()
    const normalizeMods = (mods?: string[]) =>
      Array.isArray(mods)
        ? mods.map((v) => String(v).trim().toLowerCase()).filter(Boolean)
        : []
    const inputMods = normalizeMods(tldwModel.modalities?.input)
    const outputMods = normalizeMods(tldwModel.modalities?.output)

    const caps: string[] = []
    if (Array.isArray(tldwModel.capabilities)) {
      caps.push(...tldwModel.capabilities)
    } else if (tldwModel.capabilities && typeof tldwModel.capabilities === "object") {
      Object.entries(tldwModel.capabilities).forEach(([key, value]) => {
        if (value) caps.push(key)
      })
    }
    if (tldwModel.vision) caps.push('vision')
    if (tldwModel.function_calling) caps.push('tools')
    // Heuristic: flag some models as "fast" based on name
    if (
      nameLower.includes('mini') ||
      nameLower.includes('flash') ||
      nameLower.includes('small') ||
      nameLower.includes('haiku')
    ) {
      caps.push('fast')
    }
    const capsNormalized = caps.map((cap) => cap.toLowerCase())

    // Determine model type based on declared metadata, modalities, or heuristics.
    let type: 'chat' | 'embedding' | 'image' | 'other' = 'chat'
    if (declaredType === 'image') {
      type = 'image'
    } else if (declaredType === 'embedding') {
      type = 'embedding'
    } else if (outputMods.includes('image')) {
      type = 'image'
    } else if (outputMods.includes('embedding')) {
      type = 'embedding'
    } else if (capsNormalized.includes('image') || capsNormalized.includes('image_generation')) {
      type = 'image'
    } else if (nameLower.includes('embed') || nameLower.includes('embedding')) {
      type = 'embedding'
    }

    // Extract provider from model ID or name if not provided
    const inferred =
      inferProviderFromModel(tldwModel.id, "llm") ||
      inferProviderFromModel(tldwModel.name, "llm")
    const provider = tldwModel.provider || inferred || "unknown"

    return {
      id: tldwModel.id,
      name: tldwModel.name || tldwModel.id,
      provider: provider,
      type: type,
      capabilities: caps.length ? Array.from(new Set(caps)) : undefined,
      contextLength: tldwModel.context_length,
      description: tldwModel.description,
      modalities: tldwModel.modalities
    }
  }

  /**
   * Clear the model cache
   */
  async clearCache(): Promise<void> {
    this.cachedModels = null
    this.lastFetchTime = 0
    this.inFlightFetch = null
    this.cacheScopeKey = null
    await this.persistCache()
  }

  /**
   * Get provider display name
   */
  getProviderDisplayName(provider: string): string {
    return getProviderDisplayName(provider)
  }

  /**
   * Warm the cache and return the latest models.
   */
  async warmCache(
    force: boolean = false,
    options?: { refreshOpenRouter?: boolean }
  ): Promise<ModelInfo[]> {
    return await this.getModels(force, options)
  }
}

// Singleton instance
export const tldwModels = new TldwModelsService()
