type UnknownRecord = Record<string, unknown>

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value)

const firstNonEmptyString = (...values: unknown[]): string => {
  for (const value of values) {
    if (typeof value === "string" && value.trim().length > 0) {
      return value.trim()
    }
  }
  return ""
}

const extractNestedContent = (value: unknown): string => {
  if (typeof value === "string") return value.trim()
  if (!isRecord(value)) return ""

  return firstNonEmptyString(
    value.text,
    value.content,
    value.raw_text,
    value.rawText,
    value.transcript,
    value.summary
  )
}

export const extractMediaDetailContent = (detail: unknown): string => {
  if (typeof detail === "string") return detail.trim()
  if (!isRecord(detail)) return ""

  const fromContentObject = extractNestedContent(detail.content)
  if (fromContentObject) return fromContentObject

  const fromRoot = firstNonEmptyString(
    detail.text,
    detail.transcript,
    detail.raw_text,
    detail.rawText,
    detail.raw_content,
    detail.rawContent,
    detail.summary
  )
  if (fromRoot) return fromRoot

  const latestVersion = isRecord(detail.latest_version)
    ? detail.latest_version
    : isRecord(detail.latestVersion)
      ? detail.latestVersion
      : null
  if (latestVersion) {
    const fromLatestContent = extractNestedContent(latestVersion.content)
    if (fromLatestContent) return fromLatestContent

    const fromLatest = firstNonEmptyString(
      latestVersion.text,
      latestVersion.transcript,
      latestVersion.raw_text,
      latestVersion.rawText,
      latestVersion.summary
    )
    if (fromLatest) return fromLatest
  }

  const data = isRecord(detail.data) ? detail.data : null
  if (data) {
    const fromDataContent = extractNestedContent(data.content)
    if (fromDataContent) return fromDataContent

    const fromData = firstNonEmptyString(
      data.text,
      data.transcript,
      data.raw_text,
      data.rawText,
      data.summary
    )
    if (fromData) return fromData
  }

  return ""
}
