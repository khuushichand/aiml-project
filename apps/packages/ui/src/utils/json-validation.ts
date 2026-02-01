/**
 * JSON validation utilities with detailed error positioning.
 * Provides line/column information for JSON parse errors.
 */

export type JsonValidationResult<T = unknown> = {
  success: true
  data: T
} | {
  success: false
  error: JsonValidationError
}

export type JsonValidationError = {
  message: string
  line?: number
  column?: number
  position?: number
  excerpt?: string
}

/**
 * Parse JSON position from error message.
 * Different browsers report position differently:
 * - Chrome/V8: "at position N"
 * - Firefox: "at line L column C"
 * - Safari: "at character N"
 */
function parseErrorPosition(errorMessage: string, input: string): { line?: number; column?: number; position?: number } {
  // Try Chrome/V8 format: "at position N" or "at character N"
  const positionMatch = errorMessage.match(/at (?:position|character) (\d+)/i)
  if (positionMatch) {
    const position = parseInt(positionMatch[1], 10)
    const { line, column } = positionToLineColumn(input, position)
    return { line, column, position }
  }

  // Try Firefox format: "at line L column C"
  const lineColMatch = errorMessage.match(/at line (\d+) column (\d+)/i)
  if (lineColMatch) {
    return {
      line: parseInt(lineColMatch[1], 10),
      column: parseInt(lineColMatch[2], 10)
    }
  }

  // Try generic "line N" or "position N" pattern
  const genericLineMatch = errorMessage.match(/line (\d+)/i)
  const genericColMatch = errorMessage.match(/column (\d+)/i)
  if (genericLineMatch || genericColMatch) {
    return {
      line: genericLineMatch ? parseInt(genericLineMatch[1], 10) : undefined,
      column: genericColMatch ? parseInt(genericColMatch[1], 10) : undefined
    }
  }

  return {}
}

/**
 * Convert a character position to line and column numbers.
 */
function positionToLineColumn(input: string, position: number): { line: number; column: number } {
  const lines = input.substring(0, position).split('\n')
  return {
    line: lines.length,
    column: lines[lines.length - 1].length + 1
  }
}

/**
 * Get an excerpt of the input around the error position.
 */
function getErrorExcerpt(input: string, line?: number, column?: number): string | undefined {
  if (!line) return undefined

  const lines = input.split('\n')
  if (line > lines.length || line < 1) return undefined

  const errorLine = lines[line - 1]
  if (!errorLine) return undefined

  // Show a few characters around the error position
  if (column && column > 0) {
    const start = Math.max(0, column - 20)
    const end = Math.min(errorLine.length, column + 20)
    let excerpt = errorLine.substring(start, end)
    if (start > 0) excerpt = '...' + excerpt
    if (end < errorLine.length) excerpt = excerpt + '...'

    // Add pointer to error location
    const pointerPosition = column - start - 1 + (start > 0 ? 3 : 0)
    const pointer = ' '.repeat(Math.max(0, pointerPosition)) + '^'

    return `${excerpt}\n${pointer}`
  }

  return errorLine.length > 60 ? errorLine.substring(0, 60) + '...' : errorLine
}

/**
 * Clean up the error message for display.
 */
function cleanErrorMessage(message: string): string {
  // Remove "JSON.parse: " prefix (Firefox)
  let cleaned = message.replace(/^JSON\.parse:\s*/i, '')

  // Remove "Unexpected token" repetition
  cleaned = cleaned.replace(/Unexpected token .+ in JSON/, (match) => match)

  // Make common errors more readable
  if (cleaned.includes('Unexpected end of JSON')) {
    cleaned = 'Unexpected end of input - check for missing closing brackets or quotes'
  } else if (cleaned.includes('Unexpected token')) {
    // Extract the actual token for clarity
    const tokenMatch = cleaned.match(/Unexpected token (.)/);
    if (tokenMatch) {
      const token = tokenMatch[1]
      if (token === ',') {
        cleaned = 'Unexpected comma - remove extra comma or add missing value'
      } else if (token === '}' || token === ']') {
        cleaned = `Unexpected ${token === '}' ? 'closing brace' : 'closing bracket'} - check for missing value or extra comma`
      }
    }
  } else if (cleaned.includes('Expected')) {
    // Keep as-is, these are usually helpful
  }

  return cleaned
}

/**
 * Validate and parse JSON with detailed error information.
 * Returns a result object with either the parsed data or error details.
 *
 * @param input - The JSON string to parse
 * @returns Validation result with data or error details
 */
export function validateJson<T = unknown>(input: string): JsonValidationResult<T> {
  if (!input || input.trim() === '') {
    return {
      success: false,
      error: {
        message: 'Empty input - provide valid JSON'
      }
    }
  }

  try {
    const data = JSON.parse(input) as T
    return { success: true, data }
  } catch (e: unknown) {
    const error = e as Error
    const { line, column, position } = parseErrorPosition(error.message, input)
    const excerpt = getErrorExcerpt(input, line, column)
    const message = cleanErrorMessage(error.message)

    return {
      success: false,
      error: {
        message,
        line,
        column,
        position,
        excerpt
      }
    }
  }
}

/**
 * Parse JSON with a fallback value.
 * Similar to the original parseJson but with better error reporting.
 *
 * @param input - The JSON string to parse
 * @param fallback - Value to return if parsing fails
 * @returns Parsed data or fallback
 */
export function parseJsonSafe<T>(input: string | undefined | null, fallback: T): T {
  if (!input || input.trim() === '') return fallback

  const result = validateJson<T>(input)
  if (result.success) return result.data
  return fallback
}

/**
 * Create a Form field validator for JSON fields.
 * Returns an Ant Design Form validator function.
 *
 * @param fieldName - Name of the field for error messages
 * @param required - Whether the field is required
 */
export function createJsonFieldValidator(fieldName: string = 'JSON', required: boolean = false) {
  return (_: unknown, value: string | undefined) => {
    if (!value || value.trim() === '') {
      if (required) {
        return Promise.reject(new Error(`${fieldName} is required`))
      }
      return Promise.resolve()
    }

    const result = validateJson(value)
    if ("error" in result) {
      const { error } = result
      let errorText = error.message
      if (error.line && error.column) {
        errorText = `Line ${error.line}, Column ${error.column}: ${error.message}`
      } else if (error.line) {
        errorText = `Line ${error.line}: ${error.message}`
      }

      return Promise.reject(new Error(errorText))
    }

    return Promise.resolve()
  }
}

/**
 * Format a JSON validation error for display.
 */
export function formatJsonError(error: JsonValidationError): string {
  let formatted = error.message

  if (error.line && error.column) {
    formatted = `Line ${error.line}, Column ${error.column}: ${formatted}`
  } else if (error.line) {
    formatted = `Line ${error.line}: ${formatted}`
  }

  return formatted
}
