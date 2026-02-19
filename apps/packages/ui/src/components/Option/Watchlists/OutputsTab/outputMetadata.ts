import type { WatchlistOutput, WatchlistOutputCreate } from "@/types/watchlists"

export interface DeliveryStatusSummary {
  channel: string
  status: string
  detail?: string
}

export interface DeliveryDisclosureSummary {
  visible: DeliveryStatusSummary[]
  hidden: DeliveryStatusSummary[]
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

const asNonEmptyString = (value: unknown): string | undefined => {
  if (typeof value !== "string") return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

const asPositiveInteger = (value: unknown): number | undefined => {
  if (typeof value !== "number" || !Number.isInteger(value) || value <= 0) return undefined
  return value
}

const getMetadataRecord = (metadata: unknown): Record<string, unknown> | null =>
  isRecord(metadata) ? metadata : null

export const getOutputTemplateName = (metadata: unknown): string | undefined => {
  const record = getMetadataRecord(metadata)
  if (!record) return undefined
  return asNonEmptyString(record.template_name)
}

export const getOutputTemplateVersion = (metadata: unknown): number | undefined => {
  const record = getMetadataRecord(metadata)
  if (!record) return undefined
  const numeric = asPositiveInteger(record.template_version)
  if (numeric != null) return numeric
  const fromString = asNonEmptyString(record.template_version)
  if (!fromString) return undefined
  const parsed = Number.parseInt(fromString, 10)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined
}

const normalizeDelivery = (
  value: unknown,
  fallbackChannel?: string
): DeliveryStatusSummary | null => {
  if (typeof value === "string") {
    const status = asNonEmptyString(value)
    if (!status) return null
    return {
      channel: fallbackChannel || "delivery",
      status
    }
  }

  if (!isRecord(value)) return null

  const channel = asNonEmptyString(value.channel) || fallbackChannel || "delivery"
  const status = asNonEmptyString(value.status) || "unknown"
  const detail =
    asNonEmptyString(value.error) ||
    asNonEmptyString(value.message) ||
    asNonEmptyString(value.detail) ||
    asNonEmptyString(value.reason)

  return {
    channel,
    status,
    detail
  }
}

export const getOutputDeliveryStatuses = (metadata: unknown): DeliveryStatusSummary[] => {
  const record = getMetadataRecord(metadata)
  if (!record) return []

  const rawDeliveries = record.deliveries
  if (Array.isArray(rawDeliveries)) {
    return rawDeliveries
      .map((entry) => normalizeDelivery(entry))
      .filter((entry): entry is DeliveryStatusSummary => entry !== null)
  }

  if (isRecord(rawDeliveries)) {
    return Object.entries(rawDeliveries)
      .map(([channel, value]) => normalizeDelivery(value, channel))
      .filter((entry): entry is DeliveryStatusSummary => entry !== null)
  }

  return []
}

export const buildDeliveryDisclosureSummary = (
  deliveries: DeliveryStatusSummary[],
  options?: { maxVisible?: number }
): DeliveryDisclosureSummary => {
  const maxVisible = Math.max(1, Number(options?.maxVisible ?? 1))
  if (!Array.isArray(deliveries) || deliveries.length <= maxVisible) {
    return {
      visible: Array.isArray(deliveries) ? [...deliveries] : [],
      hidden: []
    }
  }
  return {
    visible: deliveries.slice(0, maxVisible),
    hidden: deliveries.slice(maxVisible)
  }
}

export const getDeliveryStatusColor = (status: string): string => {
  const normalized = status.trim().toLowerCase()
  if (normalized === "sent" || normalized === "stored" || normalized === "success") return "green"
  if (normalized === "partial" || normalized === "warning") return "gold"
  if (normalized === "queued" || normalized === "pending" || normalized === "in_progress") return "blue"
  if (normalized === "failed" || normalized === "error") return "red"
  return "default"
}

export const getDeliveryStatusLabel = (status: string): string => {
  const normalized = status.trim().toLowerCase()
  if (normalized === "sent") return "Sent"
  if (normalized === "stored") return "Stored"
  if (normalized === "success") return "Success"
  if (normalized === "partial") return "Partial"
  if (normalized === "warning") return "Warning"
  if (normalized === "queued") return "Queued"
  if (normalized === "pending") return "Pending"
  if (normalized === "in_progress") return "In progress"
  if (normalized === "failed") return "Failed"
  if (normalized === "error") return "Error"
  return status
}

interface BuildRegenerateOptions {
  title?: string | null
  templateName?: string | null
  templateVersion?: number | null
}

export const buildRegenerateOutputRequest = (
  output: Pick<WatchlistOutput, "run_id" | "type">,
  options: BuildRegenerateOptions
): WatchlistOutputCreate => {
  const request: WatchlistOutputCreate = {
    run_id: output.run_id,
    type: output.type || undefined
  }

  const title = asNonEmptyString(options.title)
  if (title) {
    request.title = title
  }

  const templateName = asNonEmptyString(options.templateName)
  if (templateName) {
    request.template_name = templateName
    const version = asPositiveInteger(options.templateVersion)
    if (version != null) {
      request.template_version = version
    }
  }

  return request
}
