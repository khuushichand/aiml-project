export type QuickMessageAction =
  | "summarize"
  | "translate"
  | "shorten"
  | "explain"

const QUICK_ACTION_INSTRUCTIONS: Record<QuickMessageAction, string> = {
  summarize:
    "Summarize the response into concise bullet points while preserving important facts.",
  translate:
    "Translate the response into plain English while preserving meaning and citation markers.",
  shorten:
    "Rewrite the response to be shorter while preserving key points and citations.",
  explain:
    "Explain the response in simpler terms and keep citation markers attached to claims."
}

export const buildQuickMessageActionPrompt = ({
  action,
  message,
  lineage,
  sourceReferences = []
}: {
  action: QuickMessageAction
  message: string
  lineage: string
  sourceReferences?: string[]
}): string => {
  const normalizedMessage = message.trim()
  const normalizedReferences = sourceReferences
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0)

  const sections: string[] = [
    `Quick action: ${action}`,
    QUICK_ACTION_INSTRUCTIONS[action],
    "Keep citation markers like [1], [2], etc. in the rewritten output.",
    `Message lineage: ${lineage}`
  ]

  if (normalizedReferences.length > 0) {
    sections.push("Source references:")
    sections.push(normalizedReferences.join("\n"))
  }

  sections.push("Original response:")
  sections.push(normalizedMessage)
  return sections.join("\n\n")
}
