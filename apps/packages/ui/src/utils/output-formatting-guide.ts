export const PLAYGROUND_APPEND_FORMATTING_GUIDE_PROMPT_STORAGE_KEY =
  "playgroundAppendFormattingGuidePrompt"

export const OUTPUT_FORMATTING_GUIDE_SYSTEM_PROMPT_SUFFIX = [
  "Output formatting style guide:",
  "- Use Markdown for response formatting.",
  "- For plain text samples, use fenced code blocks like ```text ...```.",
  "- For code samples, use fenced code blocks with the correct language tag like ```python ...```.",
  "- Use standard Markdown headings, bullet lists, numbered lists, and tables when helpful.",
  "- Use inline code for commands, filenames, identifiers, and short snippets."
].join("\n")

export const resolveOutputFormattingGuideSuffix = (
  enabled: boolean
): string => (enabled ? OUTPUT_FORMATTING_GUIDE_SYSTEM_PROMPT_SUFFIX : "")

export const appendSystemPromptSuffix = (
  basePrompt: string,
  suffix?: string | null
): string => {
  const normalizedSuffix = (suffix || "").trim()
  if (!normalizedSuffix) return (basePrompt || "").trim()

  const normalizedBase = (basePrompt || "").trim()
  if (!normalizedBase) return normalizedSuffix
  if (normalizedBase.includes(normalizedSuffix)) return normalizedBase

  return `${normalizedBase}\n\n${normalizedSuffix}`
}
