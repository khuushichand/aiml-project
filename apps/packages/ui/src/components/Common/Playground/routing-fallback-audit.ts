type StringRecord = Record<string, unknown>

const asRecord = (value: unknown): StringRecord | null => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null
  return value as StringRecord
}

const pickString = (sources: unknown[]): string | null => {
  for (const entry of sources) {
    if (typeof entry !== "string") continue
    const trimmed = entry.trim()
    if (trimmed.length > 0) return trimmed
  }
  return null
}

const pickNumber = (sources: unknown[]): number | null => {
  for (const entry of sources) {
    if (typeof entry !== "number" || !Number.isFinite(entry)) continue
    return Math.max(0, Math.round(entry))
  }
  return null
}

const normalizePolicy = (value: string | null): "auto" | "pinned" | "unknown" => {
  if (!value) return "unknown"
  const lower = value.toLowerCase()
  if (
    lower.includes("pinned") ||
    lower.includes("fixed") ||
    lower.includes("manual")
  ) {
    return "pinned"
  }
  if (lower.includes("auto") || lower.includes("fallback")) {
    return "auto"
  }
  return "unknown"
}

const buildTarget = (provider: string | null, model: string | null): string | null => {
  if (!provider && !model) return null
  if (provider && model) return `${provider}/${model}`
  return provider || model
}

export type FallbackAudit = {
  policy: "auto" | "pinned" | "unknown"
  requestedTarget: string | null
  resolvedTarget: string | null
  fallbackApplied: boolean
  attempts: number | null
  reason: string | null
}

export const resolveFallbackAudit = (
  generationInfo: unknown
): FallbackAudit | null => {
  const info = asRecord(generationInfo)
  if (!info) return null
  const routing = asRecord(
    info.routing ??
      info.routing_metadata ??
      info.fallback ??
      info.fallbackRouting ??
      info.provider_routing
  )

  const requestedProvider = pickString([
    info.requested_provider,
    info.requestedProvider,
    routing?.requested_provider,
    routing?.requestedProvider,
    info.api_provider
  ])
  const requestedModel = pickString([
    info.requested_model,
    info.requestedModel,
    routing?.requested_model,
    routing?.requestedModel,
    info.model_name,
    info.model
  ])
  const resolvedProvider = pickString([
    info.resolved_provider,
    info.resolvedProvider,
    info.provider,
    info.provider_name,
    routing?.resolved_provider,
    routing?.resolvedProvider,
    routing?.provider,
    info.fallback_provider,
    info.fallbackProvider
  ])
  const resolvedModel = pickString([
    info.resolved_model,
    info.resolvedModel,
    routing?.resolved_model,
    routing?.resolvedModel,
    info.model,
    info.model_name,
    info.fallback_model,
    info.fallbackModel
  ])
  const policy = normalizePolicy(
    pickString([
      info.routing_policy,
      info.routingPolicy,
      info.provider_policy,
      info.providerPolicy,
      routing?.policy,
      routing?.routing_policy
    ])
  )
  const reason = pickString([
    info.fallback_reason,
    info.fallbackReason,
    routing?.reason,
    routing?.fallback_reason,
    info.error_hint
  ])

  const attempts = pickNumber([
    info.routing_attempts,
    info.routingAttempts,
    info.attempt_count,
    info.attemptCount,
    routing?.attempt_count,
    routing?.attemptCount,
    Array.isArray(routing?.attempts) ? routing?.attempts.length : null
  ])

  const requestedTarget = buildTarget(requestedProvider, requestedModel)
  const resolvedTarget = buildTarget(resolvedProvider, resolvedModel)
  const explicitFallbackApplied =
    info.used_fallback === true ||
    info.usedFallback === true ||
    info.fallback_applied === true ||
    info.fallbackApplied === true
  const providerChanged =
    Boolean(
      requestedProvider &&
        resolvedProvider &&
        requestedProvider !== resolvedProvider
    )
  const modelChanged =
    Boolean(requestedModel && resolvedModel && requestedModel !== resolvedModel)
  const inferredFallbackApplied =
    providerChanged ||
    modelChanged ||
    (typeof attempts === "number" && attempts > 1)
  const fallbackApplied = explicitFallbackApplied || inferredFallbackApplied

  if (
    !requestedTarget &&
    !resolvedTarget &&
    !reason &&
    attempts == null &&
    policy === "unknown"
  ) {
    return null
  }

  return {
    policy,
    requestedTarget,
    resolvedTarget,
    fallbackApplied,
    attempts,
    reason
  }
}
