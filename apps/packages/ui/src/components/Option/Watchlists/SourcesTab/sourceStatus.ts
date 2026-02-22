export interface SourceStatusVisual {
  color: "green" | "blue" | "gold" | "red" | "default"
  label: string
}

const SOURCE_STATUS_MAP: Record<string, SourceStatusVisual> = {
  ok: { color: "green", label: "Healthy" },
  healthy: { color: "green", label: "Healthy" },
  ready: { color: "green", label: "Healthy" },
  running: { color: "blue", label: "Running" },
  pending: { color: "blue", label: "Pending" },
  queued: { color: "blue", label: "Queued" },
  backoff: { color: "gold", label: "Backoff" },
  deferred: { color: "gold", label: "Deferred" },
  stale: { color: "gold", label: "Stale" },
  warning: { color: "gold", label: "Warning" },
  error: { color: "red", label: "Error" },
  failed: { color: "red", label: "Failed" },
  unreachable: { color: "red", label: "Unreachable" }
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
    return { color: "default", label: "Inactive" }
  }

  if (!status || !status.trim()) {
    return { color: "default", label: "Unknown" }
  }

  const normalized = normalizeStatus(status)
  const mapped = SOURCE_STATUS_MAP[normalized]
  if (mapped) return mapped

  return {
    color: "default",
    label: toTitleCase(normalized)
  }
}
