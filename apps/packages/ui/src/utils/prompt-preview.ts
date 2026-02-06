export type PromptPreviewSectionKey =
  | "system_prompt"
  | "character_preset"
  | "author_note"
  | "message_steering"
  | "greeting"
  | "lorebook"
  | "actor_worldbook"

export type PromptPreviewConflictType =
  | "scalar_conflict"
  | "directive_conflict"

export type PromptPreviewConflict = {
  type: PromptPreviewConflictType
  message: string
}

export type PromptPreviewSection = {
  key: PromptPreviewSectionKey
  label: string
  active: boolean
  tokens: number
  overSuggestedCap: boolean
  preview: string
}

export type PromptPreviewBudgetStatus = "ok" | "caution" | "error"

export type PromptPreviewSummary = {
  sections: PromptPreviewSection[]
  supplementalTokens: number
  supplementalBudget: number
  budgetStatus: PromptPreviewBudgetStatus
  warnings: string[]
  conflicts: PromptPreviewConflict[]
  examples: string[]
}

type PreparedPromptMessage = {
  role?: unknown
  content?: unknown
}

const SUPPLEMENTAL_BUDGET = 1200
const BUDGET_CAUTION_THRESHOLD = Math.floor(SUPPLEMENTAL_BUDGET * 0.9)

const SECTION_LABELS: Record<PromptPreviewSectionKey, string> = {
  system_prompt: "System prompt",
  character_preset: "Character preset",
  author_note: "Author note",
  message_steering: "Message steering",
  greeting: "Greeting",
  lorebook: "Lorebook",
  actor_worldbook: "Actor / World book"
}

const SECTION_ORDER: PromptPreviewSectionKey[] = [
  "system_prompt",
  "character_preset",
  "author_note",
  "message_steering",
  "greeting",
  "lorebook",
  "actor_worldbook"
]

const SUPPLEMENTAL_SECTION_KEYS = new Set<PromptPreviewSectionKey>([
  "character_preset",
  "author_note",
  "message_steering",
  "greeting",
  "lorebook",
  "actor_worldbook"
])

const SUGGESTED_CAPS: Partial<Record<PromptPreviewSectionKey, number>> = {
  character_preset: 180,
  author_note: 240,
  message_steering: 120,
  greeting: 120,
  lorebook: 420,
  actor_worldbook: 240
}

const PREVIEW_EXAMPLES: string[] = [
  "Preset sets temperature=0.7; Actor/World Book sets temperature=0.2 -> effective temperature=0.2.",
  'Preset directive "Speak tersely"; later directive "Be verbose" -> later directive replaces earlier.',
  "Appendable preset examples + appendable Actor/World Book examples -> both append in order."
]

const CONTRADICTORY_PHRASE_PAIRS: Array<[string, string, string]> = [
  ["speak tersely", "be verbose", "Conflicting directives detected (terse vs verbose)."],
  ["concise", "detailed", "Conflicting directives detected (concise vs detailed)."],
  ["formal", "casual", "Conflicting directives detected (formal vs casual)."]
]

const normalizeRole = (value: unknown): string => {
  if (typeof value !== "string") return ""
  return value.trim().toLowerCase()
}

const normalizeText = (value: unknown): string => {
  if (typeof value !== "string") return ""
  return value.trim()
}

const toPreview = (value: string, max = 240): string => {
  if (value.length <= max) return value
  return `${value.slice(0, max).trimEnd()}...`
}

export const estimatePromptTokens = (value: string): number => {
  const text = value.trim()
  if (!text) return 0
  return Math.ceil(text.length / 4)
}

const extractScalarConflicts = (texts: string[]): PromptPreviewConflict[] => {
  const byKey = new Map<string, Set<string>>()
  const regex =
    /\b(temperature|top_p|top[\s-]?p|repetition_penalty|repetition[\s-]?penalty)\b\s*[:=]\s*(-?\d+(?:\.\d+)?)/gi

  texts.forEach((text) => {
    let match: RegExpExecArray | null
    while ((match = regex.exec(text)) !== null) {
      const rawKey = (match[1] || "").toLowerCase()
      const key = rawKey.includes("top") ? "top_p" : rawKey.replace(/[\s-]/g, "_")
      const value = match[2]
      if (!byKey.has(key)) {
        byKey.set(key, new Set())
      }
      byKey.get(key)?.add(value)
    }
  })

  const conflicts: PromptPreviewConflict[] = []
  byKey.forEach((values, key) => {
    if (values.size > 1) {
      conflicts.push({
        type: "scalar_conflict",
        message: `Overlapping values detected for ${key}: ${Array.from(values).join(", ")}`
      })
    }
  })
  return conflicts
}

const extractDirectiveConflicts = (text: string): PromptPreviewConflict[] => {
  const lower = text.toLowerCase()
  const conflicts: PromptPreviewConflict[] = []

  CONTRADICTORY_PHRASE_PAIRS.forEach(([a, b, message]) => {
    if (lower.includes(a) && lower.includes(b)) {
      conflicts.push({
        type: "directive_conflict",
        message
      })
    }
  })

  return conflicts
}

export const buildPromptPreviewSummary = (
  preparedMessages: PreparedPromptMessage[]
): PromptPreviewSummary => {
  const contentBySection: Record<PromptPreviewSectionKey, string[]> = {
    system_prompt: [],
    character_preset: [],
    author_note: [],
    message_steering: [],
    greeting: [],
    lorebook: [],
    actor_worldbook: []
  }

  const firstUserIndex = preparedMessages.findIndex(
    (message) => normalizeRole(message?.role) === "user"
  )
  const greetingCutoff =
    firstUserIndex >= 0 ? firstUserIndex : Number.MAX_SAFE_INTEGER

  let assignedCharacterPreset = false

  preparedMessages.forEach((message, index) => {
    const role = normalizeRole(message?.role)
    const content = normalizeText(message?.content)
    if (!content) return

    if (role === "assistant" && index < greetingCutoff) {
      contentBySection.greeting.push(content)
      return
    }

    if (role !== "system") {
      return
    }

    const lower = content.toLowerCase()
    if (lower.startsWith("author's note:")) {
      contentBySection.author_note.push(content)
      return
    }

    if (lower.startsWith("steering instruction")) {
      contentBySection.message_steering.push(content)
      return
    }

    if (lower.includes("scene information:") || lower.includes("scene notes:")) {
      contentBySection.actor_worldbook.push(content)
      return
    }

    if (
      lower.includes("lorebook") ||
      lower.includes("world book") ||
      lower.includes("worldbook")
    ) {
      contentBySection.lorebook.push(content)
      return
    }

    if (!assignedCharacterPreset) {
      assignedCharacterPreset = true
      contentBySection.character_preset.push(content)
      return
    }

    contentBySection.system_prompt.push(content)
  })

  const sections: PromptPreviewSection[] = SECTION_ORDER.map((key) => {
    const content = contentBySection[key].join("\n\n").trim()
    const tokens = estimatePromptTokens(content)
    const cap = SUGGESTED_CAPS[key]
    return {
      key,
      label: SECTION_LABELS[key],
      active: content.length > 0,
      tokens,
      overSuggestedCap: typeof cap === "number" ? tokens > cap : false,
      preview: toPreview(content)
    }
  })

  const supplementalTokens = sections
    .filter((section) => SUPPLEMENTAL_SECTION_KEYS.has(section.key))
    .reduce((total, section) => total + section.tokens, 0)

  const budgetStatus: PromptPreviewBudgetStatus =
    supplementalTokens >= SUPPLEMENTAL_BUDGET
      ? "error"
      : supplementalTokens >= BUDGET_CAUTION_THRESHOLD
        ? "caution"
        : "ok"

  const warnings: string[] = []
  if (budgetStatus === "error") {
    warnings.push(
      `Supplemental prompt sections are at or above the ${SUPPLEMENTAL_BUDGET} token cap.`
    )
  } else if (budgetStatus === "caution") {
    warnings.push(
      `Supplemental prompt sections exceed ${BUDGET_CAUTION_THRESHOLD} tokens (90% of budget).`
    )
  }

  sections.forEach((section) => {
    if (!section.active) return
    if (!section.overSuggestedCap) return
    const cap = SUGGESTED_CAPS[section.key]
    if (typeof cap !== "number") return
    warnings.push(`${section.label} exceeds its suggested cap (${section.tokens}/${cap}).`)
  })

  const conflictSourceText = [
    contentBySection.character_preset.join("\n"),
    contentBySection.system_prompt.join("\n"),
    contentBySection.author_note.join("\n"),
    contentBySection.message_steering.join("\n"),
    contentBySection.actor_worldbook.join("\n"),
    contentBySection.lorebook.join("\n")
  ]
    .filter((value) => value.trim().length > 0)
    .join("\n")

  const conflicts: PromptPreviewConflict[] = [
    ...extractScalarConflicts([conflictSourceText]),
    ...extractDirectiveConflicts(conflictSourceText)
  ]

  return {
    sections,
    supplementalTokens,
    supplementalBudget: SUPPLEMENTAL_BUDGET,
    budgetStatus,
    warnings,
    conflicts,
    examples: PREVIEW_EXAMPLES
  }
}
