export type BasicStoppingModeType =
  | "max_tokens"
  | "new_line"
  | "fill_suffix"

const normalizeStopStrings = (value: string[]): string[] =>
  value.map((entry) => String(entry || "").trim()).filter(Boolean)

export const resolveGenerationStopStrings = (input: {
  useBasicMode: boolean
  basicModeType: BasicStoppingModeType
  customStopStrings: string[]
  fillSuffix: string
}): string[] => {
  if (!input.useBasicMode) {
    return normalizeStopStrings(input.customStopStrings)
  }

  if (input.basicModeType === "new_line") {
    return ["\n"]
  }

  if (input.basicModeType === "fill_suffix") {
    const suffix = String(input.fillSuffix || "").trim()
    return suffix.length > 0 ? [suffix.slice(0, 2)] : []
  }

  return []
}
