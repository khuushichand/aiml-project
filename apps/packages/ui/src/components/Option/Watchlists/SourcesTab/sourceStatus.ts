export type SourceStatusIconToken =
  | "healthy"
  | "activity"
  | "attention"
  | "error"
  | "neutral"

export interface SourceStatusVisual {
  color: "green" | "blue" | "gold" | "red" | "default"
  label: string
  iconToken: SourceStatusIconToken
}

const SOURCE_STATUS_MAP: Record<string, SourceStatusVisual> = {
  ok: { color: "green", label: "Healthy", iconToken: "healthy" },
  healthy: { color: "green", label: "Healthy", iconToken: "healthy" },
  ready: { color: "green", label: "Healthy", iconToken: "healthy" },
  running: { color: "blue", label: "Running", iconToken: "activity" },
  pending: { color: "blue", label: "Pending", iconToken: "activity" },
  queued: { color: "blue", label: "Queued", iconToken: "activity" },
  backoff: { color: "gold", label: "Backoff", iconToken: "attention" },
  deferred: { color: "gold", label: "Deferred", iconToken: "attention" },
  stale: { color: "gold", label: "Stale", iconToken: "attention" },
  warning: { color: "gold", label: "Warning", iconToken: "attention" },
  error: { color: "red", label: "Error", iconToken: "error" },
  failed: { color: "red", label: "Failed", iconToken: "error" },
  unreachable: { color: "red", label: "Unreachable", iconToken: "error" }
}

const toTitleCase = (value: string): string =>
  value
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")

const normalizeStatus = (status: string): string =>
  status.trim().toLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ")

export const getSourceStatusVisual = (
  status: string | null | undefined,
  active: boolean
): SourceStatusVisual => {
  if (!active) {
    return { color: "default", label: "Inactive", iconToken: "neutral" }
  }

  if (!status || !status.trim()) {
    return { color: "default", label: "Unknown", iconToken: "neutral" }
  }

  const normalized = normalizeStatus(status)
  const mapped = SOURCE_STATUS_MAP[normalized]
  if (mapped) return mapped

  return {
    color: "default",
    label: toTitleCase(normalized),
    iconToken: "neutral"
  }
}
