export type MediaNavigationTargetLike = {
  target_type: "page" | "char_range" | "time_range" | "href"
  target_start: number | null
  target_end: number | null
  target_href: string | null
}

const toFiniteNumber = (value: unknown): number | null => {
  if (typeof value !== "number" || !Number.isFinite(value)) return null
  return value
}

export const formatMediaNavigationTimecode = (seconds: number): string => {
  const safeSeconds = Math.max(0, Math.floor(seconds))
  const hh = Math.floor(safeSeconds / 3600)
  const mm = Math.floor((safeSeconds % 3600) / 60)
  const ss = safeSeconds % 60
  if (hh > 0) {
    return `${hh.toString().padStart(2, "0")}:${mm
      .toString()
      .padStart(2, "0")}:${ss.toString().padStart(2, "0")}`
  }
  return `${mm.toString().padStart(2, "0")}:${ss.toString().padStart(2, "0")}`
}

export const describeMediaNavigationTarget = (
  target: MediaNavigationTargetLike | null | undefined
): string | null => {
  if (!target) return null

  if (target.target_type === "time_range") {
    const start = toFiniteNumber(target.target_start)
    if (start == null) return null
    const end = toFiniteNumber(target.target_end)
    if (end != null && end > start) {
      return `Time ${formatMediaNavigationTimecode(
        start
      )} - ${formatMediaNavigationTimecode(end)}`
    }
    return `Time ${formatMediaNavigationTimecode(start)}`
  }

  if (target.target_type === "page") {
    const page = toFiniteNumber(target.target_start)
    if (page == null || page < 1) return null
    return `Page ${Math.trunc(page)}`
  }

  if (target.target_type === "char_range") {
    const start = toFiniteNumber(target.target_start)
    const end = toFiniteNumber(target.target_end)
    if (start == null || end == null || end <= start) return null
    return `Chars ${Math.trunc(start)}-${Math.trunc(end)}`
  }

  if (target.target_type === "href") {
    const href = String(target.target_href || "").trim()
    if (!href || !href.startsWith("#")) return null
    return `Anchor ${href}`
  }

  return null
}

