export const IMAGE_GENERATION_USER_MESSAGE_TYPE = "image-generation:user"
export const IMAGE_GENERATION_ASSISTANT_MESSAGE_TYPE = "image-generation:assistant"
export const PLAYGROUND_IMAGE_EVENT_SYNC_DEFAULT_STORAGE_KEY =
  "playgroundImageEventSyncDefault"
export const IMAGE_GENERATION_EVENT_MIRROR_PREFIX =
  "[[tldw:image-generation-event:v1]]"
export const IMAGE_GENERATION_EVENT_MIRROR_MAX_PREVIEW_URL_CHARS = 250_000

export const isImageGenerationMessageType = (
  messageType?: string | null
): boolean =>
  typeof messageType === "string" &&
  messageType.startsWith("image-generation:")

export type ImageGenerationEventSyncMode = "off" | "on"
export type ImageGenerationEventSyncPolicy = ImageGenerationEventSyncMode | "inherit"
export type ImageGenerationEventSyncStatus = "pending" | "synced" | "failed"

export type ImageGenerationRequestSnapshot = {
  prompt: string
  backend: string
  format?: "png" | "jpg" | "webp"
  negativePrompt?: string
  referenceFileId?: number
  width?: number
  height?: number
  steps?: number
  cfgScale?: number
  seed?: number
  sampler?: string
  model?: string
  extraParams?: Record<string, unknown>
}

export type ImageGenerationPromptMode =
  | "scene"
  | "expression"
  | "selfie"
  | "camera-angle"
  | "outfit"
  | "custom"

export type ImageGenerationRefineDiffStats = {
  baselineSegments: number
  candidateSegments: number
  sharedSegments: number
  overlapRatio: number
  addedCount: number
  removedCount: number
}

export type ImageGenerationRefineMetadata = {
  model: string
  latencyMs: number
  diffStats: ImageGenerationRefineDiffStats
}

export type ImageGenerationSyncMetadata = {
  mode: ImageGenerationEventSyncMode
  policy: ImageGenerationEventSyncPolicy
  status: ImageGenerationEventSyncStatus
  serverMessageId?: string
  lastAttemptAt?: number
  mirroredAt?: number
  error?: string
}

export type ImageGenerationMetadata = {
  request: ImageGenerationRequestSnapshot
  promptMode?: ImageGenerationPromptMode
  source?: "slash-command" | "generate-modal" | "message-regen"
  createdAt?: number
  refine?: ImageGenerationRefineMetadata
  sync?: ImageGenerationSyncMetadata
}

export type ImageGenerationEventMirrorPayload = {
  kind: "image_generation_event"
  version: 1
  eventId?: string
  createdAt?: number
  fileId?: string
  request: ImageGenerationRequestSnapshot
  promptMode?: ImageGenerationPromptMode
  source?: "slash-command" | "generate-modal" | "message-regen"
  refine?: ImageGenerationRefineMetadata
  variantCount?: number
  activeVariantIndex?: number
  imageDataUrl?: string
}

export type ImageGenerationVariantLike = {
  id?: string
  generationInfo?: unknown
}

type ImageGenerationVariantBundleParams<T extends ImageGenerationVariantLike> = {
  messageId?: string | null
  messageGenerationInfo?: unknown
  variants?: T[] | null
  activeVariantIndex?: number | null
  fallbackCreatedAt?: number
  hasVisibleVariant?: boolean
}

export type ImageGenerationVariantBundle<T extends ImageGenerationVariantLike> = {
  eventId: string
  activeVariantIndex: number
  variantCount: number
  generationInfo?: Record<string, unknown>
  variants: T[]
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value)

const normalizeNonEmptyString = (value: unknown): string | undefined =>
  typeof value === "string" && value.trim().length > 0 ? value.trim() : undefined

const resolveImageGenerationNode = (
  generationInfo: unknown
): Record<string, unknown> | null => {
  if (!isRecord(generationInfo)) return null
  const candidate = generationInfo.image_generation
  return isRecord(candidate) ? candidate : null
}

const resolveImageGenerationTextField = (
  generationInfo: unknown,
  key: "event_id" | "variant_id"
): string | undefined => {
  const imageGeneration = resolveImageGenerationNode(generationInfo)
  if (!imageGeneration) return undefined
  return normalizeNonEmptyString(imageGeneration[key])
}

const withImageGenerationVariantMetadata = (
  generationInfo: unknown,
  params: {
    eventId: string
    variantId: string
    variantIndex: number
    variantCount: number
    activeVariantIndex: number
    isKept: boolean
    fallbackCreatedAt?: number
  }
): Record<string, unknown> | undefined => {
  if (!isRecord(generationInfo)) return undefined
  const imageGeneration = resolveImageGenerationNode(generationInfo)
  if (!imageGeneration) return undefined

  const nextImageGeneration: Record<string, unknown> = {
    ...imageGeneration,
    event_id: params.eventId,
    variant_id: params.variantId,
    variant_index: params.variantIndex,
    variant_count: params.variantCount,
    active_variant_index: params.activeVariantIndex,
    is_kept: params.isKept
  }
  if (
    !(
      typeof nextImageGeneration.createdAt === "number" &&
      Number.isFinite(nextImageGeneration.createdAt)
    ) &&
    typeof params.fallbackCreatedAt === "number" &&
    Number.isFinite(params.fallbackCreatedAt)
  ) {
    nextImageGeneration.createdAt = params.fallbackCreatedAt
  }

  return {
    ...generationInfo,
    image_generation: nextImageGeneration
  }
}

const IMAGE_EVENT_SYNC_MODES = new Set<ImageGenerationEventSyncMode>([
  "off",
  "on"
])
const IMAGE_EVENT_SYNC_POLICIES = new Set<ImageGenerationEventSyncPolicy>([
  "inherit",
  "off",
  "on"
])

export const normalizeImageGenerationEventSyncMode = (
  value: unknown,
  fallback: ImageGenerationEventSyncMode = "off"
): ImageGenerationEventSyncMode => {
  if (typeof value !== "string") return fallback
  const normalized = value.trim().toLowerCase() as ImageGenerationEventSyncMode
  return IMAGE_EVENT_SYNC_MODES.has(normalized) ? normalized : fallback
}

export const normalizeImageGenerationEventSyncPolicy = (
  value: unknown,
  fallback: ImageGenerationEventSyncPolicy = "inherit"
): ImageGenerationEventSyncPolicy => {
  if (typeof value !== "string") return fallback
  const normalized = value.trim().toLowerCase() as ImageGenerationEventSyncPolicy
  return IMAGE_EVENT_SYNC_POLICIES.has(normalized) ? normalized : fallback
}

export const resolveImageGenerationEventSyncMode = (params: {
  requestPolicy?: ImageGenerationEventSyncPolicy | null
  chatMode?: ImageGenerationEventSyncMode | null
  globalMode?: ImageGenerationEventSyncMode | null
}): ImageGenerationEventSyncMode => {
  const requestPolicy = normalizeImageGenerationEventSyncPolicy(
    params.requestPolicy,
    "inherit"
  )
  if (requestPolicy === "on" || requestPolicy === "off") {
    return requestPolicy
  }
  if (params.chatMode === "on" || params.chatMode === "off") {
    return params.chatMode
  }
  return normalizeImageGenerationEventSyncMode(params.globalMode, "off")
}

export const resolveImageGenerationEventId = (params: {
  messageId?: string | null
  messageGenerationInfo?: unknown
  variants?: ImageGenerationVariantLike[] | null
}): string => {
  const fromMessageGeneration = resolveImageGenerationTextField(
    params.messageGenerationInfo,
    "event_id"
  )
  if (fromMessageGeneration) return fromMessageGeneration

  const variants = Array.isArray(params.variants) ? params.variants : []
  for (const variant of variants) {
    const fromVariantGeneration = resolveImageGenerationTextField(
      variant?.generationInfo,
      "event_id"
    )
    if (fromVariantGeneration) return fromVariantGeneration
  }

  const fromMessageId = normalizeNonEmptyString(params.messageId)
  if (fromMessageId) return fromMessageId

  return `image-event-${Date.now()}`
}

export const resolveImageGenerationVariantId = (params: {
  eventId: string
  variantIndex: number
  messageId?: string | null
  generationInfo?: unknown
}): string => {
  const fromGeneration = resolveImageGenerationTextField(
    params.generationInfo,
    "variant_id"
  )
  if (fromGeneration) return fromGeneration

  const fromMessageId = normalizeNonEmptyString(params.messageId)
  if (fromMessageId) return fromMessageId

  return `${params.eventId}:variant:${Math.max(0, params.variantIndex) + 1}`
}

export const normalizeImageGenerationVariantBundle = <
  T extends ImageGenerationVariantLike
>(
  params: ImageGenerationVariantBundleParams<T>
): ImageGenerationVariantBundle<T> => {
  const variants = Array.isArray(params.variants) ? [...params.variants] : []
  const hasVisibleVariant = params.hasVisibleVariant ?? true
  const variantCount =
    variants.length > 0 ? variants.length : hasVisibleVariant ? 1 : 0
  const fallbackActiveIndex = variantCount > 0 ? variantCount - 1 : 0
  const candidateActiveIndex =
    typeof params.activeVariantIndex === "number" &&
    Number.isFinite(params.activeVariantIndex)
      ? Math.round(params.activeVariantIndex)
      : fallbackActiveIndex
  const activeVariantIndex =
    variantCount > 0
      ? Math.max(0, Math.min(candidateActiveIndex, variantCount - 1))
      : 0

  const eventId = resolveImageGenerationEventId({
    messageId: params.messageId,
    messageGenerationInfo: params.messageGenerationInfo,
    variants
  })

  if (variants.length === 0) {
    if (variantCount === 0) {
      return {
        eventId,
        activeVariantIndex: 0,
        variantCount: 0,
        generationInfo: isRecord(params.messageGenerationInfo)
          ? params.messageGenerationInfo
          : undefined,
        variants: []
      }
    }

    const variantId = resolveImageGenerationVariantId({
      eventId,
      variantIndex: activeVariantIndex,
      messageId: params.messageId,
      generationInfo: params.messageGenerationInfo
    })
    const generationInfo = withImageGenerationVariantMetadata(
      params.messageGenerationInfo,
      {
        eventId,
        variantId,
        variantIndex: activeVariantIndex,
        variantCount,
        activeVariantIndex,
        isKept: true,
        fallbackCreatedAt: params.fallbackCreatedAt
      }
    )
    return {
      eventId,
      activeVariantIndex,
      variantCount,
      generationInfo:
        generationInfo ??
        (isRecord(params.messageGenerationInfo)
          ? params.messageGenerationInfo
          : undefined),
      variants: []
    }
  }

  const normalizedVariants = variants.map((variant, index) => {
    const isActive = index === activeVariantIndex
    const baseGenerationInfo =
      isActive && variant?.generationInfo == null
        ? params.messageGenerationInfo
        : variant?.generationInfo
    const variantId = resolveImageGenerationVariantId({
      eventId,
      variantIndex: index,
      messageId: variant?.id,
      generationInfo: baseGenerationInfo
    })
    const normalizedGenerationInfo = withImageGenerationVariantMetadata(
      baseGenerationInfo,
      {
        eventId,
        variantId,
        variantIndex: index,
        variantCount,
        activeVariantIndex,
        isKept: isActive,
        fallbackCreatedAt: params.fallbackCreatedAt
      }
    )
    return {
      ...variant,
      id: variantId,
      generationInfo: normalizedGenerationInfo ?? variant?.generationInfo
    } as T
  })

  const activeVariant = normalizedVariants[activeVariantIndex]
  const generationInfo =
    (isRecord(activeVariant?.generationInfo)
      ? activeVariant.generationInfo
      : undefined) ??
    withImageGenerationVariantMetadata(params.messageGenerationInfo, {
      eventId,
      variantId: resolveImageGenerationVariantId({
        eventId,
        variantIndex: activeVariantIndex,
        messageId: params.messageId,
        generationInfo: params.messageGenerationInfo
      }),
      variantIndex: activeVariantIndex,
      variantCount,
      activeVariantIndex,
      isKept: true,
      fallbackCreatedAt: params.fallbackCreatedAt
    }) ??
    (isRecord(params.messageGenerationInfo)
      ? params.messageGenerationInfo
      : undefined)

  return {
    eventId,
    activeVariantIndex,
    variantCount,
    generationInfo,
    variants: normalizedVariants
  }
}

const resolveImageGenerationRefineMetadata = (
  candidate: unknown
): ImageGenerationRefineMetadata | undefined => {
  if (!isRecord(candidate)) return undefined
  const model =
    typeof candidate.model === "string" ? candidate.model.trim() : ""
  const latencyMs =
    typeof candidate.latencyMs === "number" && Number.isFinite(candidate.latencyMs)
      ? Math.max(0, Math.round(candidate.latencyMs))
      : null
  const diffStats = isRecord(candidate.diffStats) ? candidate.diffStats : null

  const baselineSegments =
    typeof diffStats?.baselineSegments === "number" &&
    Number.isFinite(diffStats.baselineSegments)
      ? Math.max(0, Math.round(diffStats.baselineSegments))
      : null
  const candidateSegments =
    typeof diffStats?.candidateSegments === "number" &&
    Number.isFinite(diffStats.candidateSegments)
      ? Math.max(0, Math.round(diffStats.candidateSegments))
      : null
  const sharedSegments =
    typeof diffStats?.sharedSegments === "number" &&
    Number.isFinite(diffStats.sharedSegments)
      ? Math.max(0, Math.round(diffStats.sharedSegments))
      : null
  const overlapRatio =
    typeof diffStats?.overlapRatio === "number" &&
    Number.isFinite(diffStats.overlapRatio)
      ? Math.max(0, Math.min(1, Number(diffStats.overlapRatio)))
      : null
  const addedCount =
    typeof diffStats?.addedCount === "number" &&
    Number.isFinite(diffStats.addedCount)
      ? Math.max(0, Math.round(diffStats.addedCount))
      : null
  const removedCount =
    typeof diffStats?.removedCount === "number" &&
    Number.isFinite(diffStats.removedCount)
      ? Math.max(0, Math.round(diffStats.removedCount))
      : null

  if (
    !model ||
    latencyMs == null ||
    baselineSegments == null ||
    candidateSegments == null ||
    sharedSegments == null ||
    overlapRatio == null ||
    addedCount == null ||
    removedCount == null
  ) {
    return undefined
  }

  return {
    model,
    latencyMs,
    diffStats: {
      baselineSegments,
      candidateSegments,
      sharedSegments,
      overlapRatio,
      addedCount,
      removedCount
    }
  }
}

const resolveImageGenerationRequestSnapshot = (
  value: unknown
): ImageGenerationRequestSnapshot | null => {
  if (!isRecord(value)) return null
  const prompt = typeof value.prompt === "string" ? value.prompt.trim() : ""
  const backend = typeof value.backend === "string" ? value.backend.trim() : ""
  if (!prompt || !backend) return null

  const request: ImageGenerationRequestSnapshot = { prompt, backend }
  const assignNumber = (
    key:
      | "referenceFileId"
      | "width"
      | "height"
      | "steps"
      | "cfgScale"
      | "seed",
    candidate: unknown
  ) => {
    if (typeof candidate === "number" && Number.isFinite(candidate)) {
      request[key] = candidate
    }
  }
  const assignString = (
    key: "negativePrompt" | "sampler" | "model" | "format",
    candidate: unknown
  ) => {
    if (typeof candidate === "string" && candidate.trim().length > 0) {
      ;(request as any)[key] = candidate.trim()
    }
  }

  assignString("format", value.format)
  assignString("negativePrompt", value.negativePrompt)
  assignString("sampler", value.sampler)
  assignString("model", value.model)
  assignNumber("referenceFileId", value.referenceFileId)
  assignNumber("width", value.width)
  assignNumber("height", value.height)
  assignNumber("steps", value.steps)
  assignNumber("cfgScale", value.cfgScale)
  assignNumber("seed", value.seed)

  if (isRecord(value.extraParams)) {
    request.extraParams = value.extraParams
  }

  return request
}

const resolveImageGenerationSource = (
  value: unknown
): ImageGenerationMetadata["source"] | undefined => {
  if (
    value === "slash-command" ||
    value === "generate-modal" ||
    value === "message-regen"
  ) {
    return value
  }
  return undefined
}

const resolveImageGenerationPromptMode = (
  value: unknown
): ImageGenerationPromptMode | undefined => {
  if (
    value === "scene" ||
    value === "expression" ||
    value === "selfie" ||
    value === "camera-angle" ||
    value === "outfit" ||
    value === "custom"
  ) {
    return value
  }
  return undefined
}

const resolveImageGenerationSyncMetadata = (
  value: unknown
): ImageGenerationSyncMetadata | undefined => {
  if (!isRecord(value)) return undefined
  const mode = normalizeImageGenerationEventSyncMode(value.mode, "off")
  const policy = normalizeImageGenerationEventSyncPolicy(value.policy, "inherit")
  const rawStatus =
    typeof value.status === "string" ? value.status.trim().toLowerCase() : ""
  const status: ImageGenerationEventSyncStatus =
    rawStatus === "synced" || rawStatus === "failed" || rawStatus === "pending"
      ? rawStatus
      : "pending"

  const sync: ImageGenerationSyncMetadata = {
    mode,
    policy,
    status
  }
  if (
    typeof value.serverMessageId === "string" &&
    value.serverMessageId.trim().length > 0
  ) {
    sync.serverMessageId = value.serverMessageId.trim()
  }
  if (
    typeof value.lastAttemptAt === "number" &&
    Number.isFinite(value.lastAttemptAt)
  ) {
    sync.lastAttemptAt = value.lastAttemptAt
  }
  if (typeof value.mirroredAt === "number" && Number.isFinite(value.mirroredAt)) {
    sync.mirroredAt = value.mirroredAt
  }
  if (typeof value.error === "string" && value.error.trim().length > 0) {
    sync.error = value.error.trim()
  }
  return sync
}

export const buildImageGenerationEventMirrorContent = (
  payload: ImageGenerationEventMirrorPayload
): string => {
  const request = resolveImageGenerationRequestSnapshot(payload.request)
  if (!request) {
    throw new Error("Image generation event mirror payload requires request.")
  }
  const normalizedPayload: ImageGenerationEventMirrorPayload = {
    kind: "image_generation_event",
    version: 1,
    request
  }
  if (typeof payload.eventId === "string" && payload.eventId.trim().length > 0) {
    normalizedPayload.eventId = payload.eventId.trim()
  }
  if (typeof payload.createdAt === "number" && Number.isFinite(payload.createdAt)) {
    normalizedPayload.createdAt = payload.createdAt
  }
  if (typeof payload.fileId === "string" && payload.fileId.trim().length > 0) {
    normalizedPayload.fileId = payload.fileId.trim()
  }
  const promptMode = resolveImageGenerationPromptMode(payload.promptMode)
  if (promptMode) normalizedPayload.promptMode = promptMode
  const source = resolveImageGenerationSource(payload.source)
  if (source) normalizedPayload.source = source
  const refine = resolveImageGenerationRefineMetadata(payload.refine)
  if (refine) normalizedPayload.refine = refine
  if (
    typeof payload.variantCount === "number" &&
    Number.isFinite(payload.variantCount) &&
    payload.variantCount > 0
  ) {
    normalizedPayload.variantCount = Math.max(1, Math.round(payload.variantCount))
  }
  if (
    typeof payload.activeVariantIndex === "number" &&
    Number.isFinite(payload.activeVariantIndex) &&
    payload.activeVariantIndex >= 0
  ) {
    normalizedPayload.activeVariantIndex = Math.max(
      0,
      Math.round(payload.activeVariantIndex)
    )
  }
  if (
    typeof payload.imageDataUrl === "string" &&
    payload.imageDataUrl.startsWith("data:image/") &&
    payload.imageDataUrl.length <= IMAGE_GENERATION_EVENT_MIRROR_MAX_PREVIEW_URL_CHARS
  ) {
    normalizedPayload.imageDataUrl = payload.imageDataUrl
  }

  return `${IMAGE_GENERATION_EVENT_MIRROR_PREFIX}${JSON.stringify(
    normalizedPayload
  )}`
}

export const parseImageGenerationEventMirrorContent = (
  content: unknown
): ImageGenerationEventMirrorPayload | null => {
  if (typeof content !== "string" || content.trim().length === 0) return null
  const normalizedContent = content.trimStart()
  if (!normalizedContent.startsWith(IMAGE_GENERATION_EVENT_MIRROR_PREFIX)) {
    return null
  }
  const payloadRaw = normalizedContent
    .slice(IMAGE_GENERATION_EVENT_MIRROR_PREFIX.length)
    .trim()
  if (!payloadRaw) return null
  try {
    const parsed = JSON.parse(payloadRaw)
    if (!isRecord(parsed)) return null
    if (parsed.kind !== "image_generation_event") return null
    const request = resolveImageGenerationRequestSnapshot(parsed.request)
    if (!request) return null

    const payload: ImageGenerationEventMirrorPayload = {
      kind: "image_generation_event",
      version: 1,
      request
    }
    if (typeof parsed.eventId === "string" && parsed.eventId.trim().length > 0) {
      payload.eventId = parsed.eventId.trim()
    }
    if (typeof parsed.createdAt === "number" && Number.isFinite(parsed.createdAt)) {
      payload.createdAt = parsed.createdAt
    }
    if (typeof parsed.fileId === "string" && parsed.fileId.trim().length > 0) {
      payload.fileId = parsed.fileId.trim()
    }
    const promptMode = resolveImageGenerationPromptMode(parsed.promptMode)
    if (promptMode) payload.promptMode = promptMode
    const source = resolveImageGenerationSource(parsed.source)
    if (source) payload.source = source
    const refine = resolveImageGenerationRefineMetadata(parsed.refine)
    if (refine) payload.refine = refine
    if (
      typeof parsed.variantCount === "number" &&
      Number.isFinite(parsed.variantCount) &&
      parsed.variantCount > 0
    ) {
      payload.variantCount = Math.max(1, Math.round(parsed.variantCount))
    }
    if (
      typeof parsed.activeVariantIndex === "number" &&
      Number.isFinite(parsed.activeVariantIndex) &&
      parsed.activeVariantIndex >= 0
    ) {
      payload.activeVariantIndex = Math.max(0, Math.round(parsed.activeVariantIndex))
    }
    if (
      typeof parsed.imageDataUrl === "string" &&
      parsed.imageDataUrl.startsWith("data:image/") &&
      parsed.imageDataUrl.length <= IMAGE_GENERATION_EVENT_MIRROR_MAX_PREVIEW_URL_CHARS
    ) {
      payload.imageDataUrl = parsed.imageDataUrl
    }
    return payload
  } catch {
    return null
  }
}

export const resolveImageGenerationMetadata = (
  generationInfo: unknown
): ImageGenerationMetadata | null => {
  if (!isRecord(generationInfo)) return null
  const candidate = generationInfo.image_generation
  if (!isRecord(candidate)) return null
  const request = resolveImageGenerationRequestSnapshot(candidate.request)
  if (!request) return null

  const metadata: ImageGenerationMetadata = { request }
  const promptMode = resolveImageGenerationPromptMode(candidate.promptMode)
  if (promptMode) metadata.promptMode = promptMode
  const source = resolveImageGenerationSource(candidate.source)
  if (source) metadata.source = source

  if (typeof candidate.createdAt === "number" && Number.isFinite(candidate.createdAt)) {
    metadata.createdAt = candidate.createdAt
  }

  const refineCandidate = isRecord(candidate.refine)
    ? candidate.refine
    : isRecord(candidate.diff_stats) ||
        typeof candidate.refine_model === "string" ||
        typeof candidate.refine_latency_ms === "number"
      ? {
          model: candidate.refine_model,
          latencyMs: candidate.refine_latency_ms,
          diffStats: candidate.diff_stats
        }
      : null

  const refine = resolveImageGenerationRefineMetadata(refineCandidate)
  if (refine) metadata.refine = refine

  const sync = resolveImageGenerationSyncMetadata(candidate.sync)
  if (sync) metadata.sync = sync

  return metadata
}
