export type PromptImportErrorCode =
  | "empty_file"
  | "invalid_json"
  | "invalid_schema"

export class PromptImportValidationError extends Error {
  readonly code: PromptImportErrorCode
  readonly parsePosition?: number

  constructor(
    code: PromptImportErrorCode,
    message: string,
    options?: { parsePosition?: number }
  ) {
    super(message)
    this.name = "PromptImportValidationError"
    this.code = code
    this.parsePosition = options?.parsePosition
  }
}

const JSON_POSITION_RE = /position\s+(\d+)/i

const getJsonParsePosition = (errorMessage: string): number | undefined => {
  const match = JSON_POSITION_RE.exec(errorMessage || "")
  if (!match?.[1]) {
    return undefined
  }

  const parsed = Number.parseInt(match[1], 10)
  return Number.isFinite(parsed) ? parsed : undefined
}

export const parseImportPromptsPayload = (fileText: string): any[] => {
  const trimmed = fileText.trim()
  if (!trimmed) {
    throw new PromptImportValidationError(
      "empty_file",
      "Import file is empty."
    )
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(fileText)
  } catch (error: any) {
    const parsePosition = getJsonParsePosition(String(error?.message || ""))
    throw new PromptImportValidationError(
      "invalid_json",
      String(error?.message || "Invalid JSON"),
      { parsePosition }
    )
  }

  if (Array.isArray(parsed)) {
    return parsed
  }

  if (parsed && typeof parsed === "object" && Array.isArray((parsed as any).prompts)) {
    return (parsed as any).prompts
  }

  throw new PromptImportValidationError(
    "invalid_schema",
    "Unsupported prompt import schema."
  )
}

export type PromptImportErrorNotice = {
  titleKey: string
  titleDefaultValue: string
  descriptionKey: string
  descriptionDefaultValue: string
  values?: Record<string, unknown>
}

export const getPromptImportErrorNotice = (
  error: unknown
): PromptImportErrorNotice | null => {
  const candidate = error as
    | PromptImportValidationError
    | { code?: PromptImportErrorCode; parsePosition?: number }
    | null

  if (!candidate || typeof candidate !== "object" || !candidate.code) {
    return null
  }

  if (candidate.code === "empty_file") {
    return {
      titleKey: "managePrompts.importError.empty.title",
      titleDefaultValue: "Import failed",
      descriptionKey: "managePrompts.importError.empty.description",
      descriptionDefaultValue:
        "File is empty. Select a JSON file that contains prompts."
    }
  }

  if (candidate.code === "invalid_schema") {
    return {
      titleKey: "managePrompts.importError.schema.title",
      titleDefaultValue: "Import failed",
      descriptionKey: "managePrompts.importError.schema.description",
      descriptionDefaultValue:
        "File format not recognized. Expected a JSON array of prompts or an object with a 'prompts' array."
    }
  }

  return {
    titleKey: "managePrompts.importError.json.title",
    titleDefaultValue: "Invalid JSON file",
    descriptionKey: "managePrompts.importError.json.description",
    descriptionDefaultValue:
      typeof candidate.parsePosition === "number"
        ? "Invalid JSON near character {{position}}."
        : "Invalid JSON. Check file formatting and try again.",
    values:
      typeof candidate.parsePosition === "number"
        ? { position: candidate.parsePosition }
        : undefined
  }
}
