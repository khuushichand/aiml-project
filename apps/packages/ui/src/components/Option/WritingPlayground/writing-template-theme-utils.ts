export type WritingDefaultTemplate = {
  name: string
  payload: Record<string, unknown>
  schema_version: number
  is_default: boolean
}

export type WritingDefaultTheme = {
  name: string
  class_name: string
  css: string
  schema_version: number
  is_default: boolean
  order: number
}

export const DEFAULT_TEMPLATE_CATALOG: WritingDefaultTemplate[] = [
  {
    name: "default",
    payload: {},
    schema_version: 1,
    is_default: true
  }
]

export const DEFAULT_THEME_CATALOG: WritingDefaultTheme[] = [
  {
    name: "default",
    class_name: "",
    css: "",
    schema_version: 1,
    is_default: true,
    order: 0
  }
]

export const buildDuplicateName = (
  sourceName: string,
  existingNames: string[],
  suffix = "Copy"
): string => {
  const baseName = String(sourceName || "").trim() || "Untitled"
  const normalizedExisting = new Set(
    existingNames.map((name) => String(name || "").trim().toLowerCase())
  )
  const makeName = (index?: number): string =>
    index == null
      ? `${baseName} (${suffix})`
      : `${baseName} (${suffix} ${index})`

  let candidate = makeName()
  if (!normalizedExisting.has(candidate.toLowerCase())) {
    return candidate
  }

  let index = 2
  while (normalizedExisting.has(makeName(index).toLowerCase())) {
    index += 1
  }
  candidate = makeName(index)
  return candidate
}
