export const TEMPLATE_VARIABLE_REGEX = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g

type TemplateValidationCode = "unmatched_braces" | "invalid_token"

export type TemplateValidationResult = {
  isValid: boolean
  code?: TemplateValidationCode
  invalidTokens?: string[]
}

export const extractTemplateVariables = (
  template: string | null | undefined
): string[] => {
  const variables: string[] = []
  if (!template) {
    return variables
  }

  for (const match of template.matchAll(TEMPLATE_VARIABLE_REGEX)) {
    const variable = String(match?.[1] || "").trim()
    if (variable && !variables.includes(variable)) {
      variables.push(variable)
    }
  }

  return variables
}

export const tokenizeTemplateVariableHighlights = (
  template: string | null | undefined
): Array<{ text: string; isVariable: boolean; variableName?: string }> => {
  const source = template || ""
  if (!source) {
    return [{ text: "", isVariable: false }]
  }

  const tokens: Array<{ text: string; isVariable: boolean; variableName?: string }> = []
  let lastIndex = 0

  for (const match of source.matchAll(TEMPLATE_VARIABLE_REGEX)) {
    const index = typeof match.index === "number" ? match.index : -1
    if (index < 0) continue

    if (index > lastIndex) {
      tokens.push({
        text: source.slice(lastIndex, index),
        isVariable: false
      })
    }

    tokens.push({
      text: match[0] || "",
      isVariable: true,
      variableName: String(match[1] || "").trim()
    })
    lastIndex = index + String(match[0] || "").length
  }

  if (lastIndex < source.length) {
    tokens.push({
      text: source.slice(lastIndex),
      isVariable: false
    })
  }

  if (tokens.length === 0) {
    return [{ text: source, isVariable: false }]
  }

  return tokens
}

export const validateTemplateVariableSyntax = (
  template: string | null | undefined
): TemplateValidationResult => {
  const source = template || ""
  if (!source) {
    return { isValid: true }
  }

  const openCount = source.split("{{").length - 1
  const closeCount = source.split("}}").length - 1
  if (openCount !== closeCount) {
    return {
      isValid: false,
      code: "unmatched_braces"
    }
  }

  const allSegments = source.match(/\{\{[\s\S]*?\}\}/g) || []
  const invalidTokens = allSegments.filter(
    (segment) => !/^\{\{\s*[a-zA-Z0-9_]+\s*\}\}$/.test(segment)
  )

  if (invalidTokens.length > 0) {
    return {
      isValid: false,
      code: "invalid_token",
      invalidTokens
    }
  }

  return { isValid: true }
}
