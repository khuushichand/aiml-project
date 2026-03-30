import path from "node:path"

const OUTPUT_SUFFIX = `${path.sep}.output${path.sep}chrome-mv3`
const BUILD_SUFFIX = `${path.sep}build${path.sep}chrome-mv3`

const classifyExtensionCandidate = (candidate: string): "custom" | "output" | "build" => {
  const normalized = String(candidate || "").trim()
  if (!normalized) return "custom"
  if (normalized.endsWith(OUTPUT_SUFFIX)) return "output"
  if (normalized.endsWith(BUILD_SUFFIX)) return "build"
  return "custom"
}

export const prioritizeExtensionBuildCandidates = (candidates: string[]): string[] => {
  const buckets: Record<"custom" | "output" | "build", string[]> = {
    custom: [],
    output: [],
    build: []
  }
  const seen = new Set<string>()

  for (const candidate of candidates) {
    const normalized = String(candidate || "").trim()
    if (!normalized || seen.has(normalized)) continue
    seen.add(normalized)
    buckets[classifyExtensionCandidate(normalized)].push(normalized)
  }

  return [...buckets.custom, ...buckets.output, ...buckets.build]
}
