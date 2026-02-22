export const WORLD_BOOK_FORM_DEFAULTS = {
  enabled: true,
  scan_depth: 3,
  token_budget: 500,
  recursive_scanning: false
} as const

export type WorldBookStarterEntry = {
  keywords: string[]
  content: string
  priority?: number
  enabled?: boolean
  case_sensitive?: boolean
  regex_match?: boolean
  whole_word_match?: boolean
  appendable?: boolean
}

export type WorldBookStarterTemplate = {
  key: string
  label: string
  suggestedName: string
  description: string
  defaults?: Partial<typeof WORLD_BOOK_FORM_DEFAULTS>
  entries: WorldBookStarterEntry[]
}

export const WORLD_BOOK_STARTER_TEMPLATES: WorldBookStarterTemplate[] = [
  {
    key: "fantasy",
    label: "Fantasy Setting",
    suggestedName: "Fantasy Lore",
    description:
      "Core lore for a fantasy world, including factions, magic rules, and key locations.",
    defaults: { scan_depth: 4, token_budget: 700, recursive_scanning: true },
    entries: [
      {
        keywords: ["magic system", "mana"],
        content:
          "Magic in this world is fueled by ambient mana. Complex spells drain the caster and require a recovery period.",
        priority: 70
      },
      {
        keywords: ["capital city", "high council"],
        content:
          "The capital is governed by a seven-seat High Council that controls law, trade routes, and military charters.",
        priority: 60
      }
    ]
  },
  {
    key: "sci_fi",
    label: "Sci-Fi Lore",
    suggestedName: "Sci-Fi Codex",
    description:
      "Reference knowledge for a science-fiction setting with technology, factions, and mission context.",
    defaults: { scan_depth: 5, token_budget: 900, recursive_scanning: true },
    entries: [
      {
        keywords: ["jump drive", "ftl"],
        content:
          "Jump drives require a calibrated beacon and cannot be used inside a gravity well above safety threshold.",
        priority: 75
      },
      {
        keywords: ["station protocol", "command deck"],
        content:
          "Station protocol requires command-deck authorization for all high-risk maneuvers and emergency venting.",
        priority: 55
      }
    ]
  },
  {
    key: "product_knowledge",
    label: "Product Knowledge Base",
    suggestedName: "Product KB",
    description:
      "Reusable product facts for support and onboarding conversations, including workflows and guardrails.",
    defaults: { scan_depth: 3, token_budget: 650, recursive_scanning: false },
    entries: [
      {
        keywords: ["onboarding", "first steps"],
        content:
          "New users should complete workspace setup, connect integrations, and run the guided quickstart before advanced features.",
        priority: 80
      },
      {
        keywords: ["permissions", "roles"],
        content:
          "Role-based permissions determine feature access. Admin roles can manage settings; contributors can create and edit content.",
        priority: 65
      }
    ]
  }
]

const REQUEST_SUFFIX_PATTERN = /\s+\(([A-Z]+)\s+\/[^\)]*\)\s*$/i
const VERSION_CONFLICT_PATTERN = /\bversion mismatch\b|\bmodified by someone else\b/i
const WORLD_BOOK_VERSION_CONFLICT_FALLBACK =
  "This world book was modified by someone else. Reload the latest version and reapply your edits."

export const normalizeWorldBookName = (value: unknown): string => String(value ?? "").trim()

const normalizeWorldBookNameKey = (value: unknown): string => normalizeWorldBookName(value).toLowerCase()

export const toWorldBookFormValues = (worldBook: Record<string, any> | null | undefined) => ({
  ...WORLD_BOOK_FORM_DEFAULTS,
  ...(worldBook || {}),
  name: typeof worldBook?.name === "string" ? worldBook.name : "",
  description: typeof worldBook?.description === "string" ? worldBook.description : "",
  enabled:
    typeof worldBook?.enabled === "boolean"
      ? worldBook.enabled
      : WORLD_BOOK_FORM_DEFAULTS.enabled,
  scan_depth:
    typeof worldBook?.scan_depth === "number"
      ? worldBook.scan_depth
      : WORLD_BOOK_FORM_DEFAULTS.scan_depth,
  token_budget:
    typeof worldBook?.token_budget === "number"
      ? worldBook.token_budget
      : WORLD_BOOK_FORM_DEFAULTS.token_budget,
  recursive_scanning:
    typeof worldBook?.recursive_scanning === "boolean"
      ? worldBook.recursive_scanning
      : WORLD_BOOK_FORM_DEFAULTS.recursive_scanning
})

export const hasDuplicateWorldBookName = (
  value: unknown,
  worldBooks: Array<{ id?: number; name?: string }> | undefined,
  options?: { excludeId?: number | null }
): boolean => {
  const candidate = normalizeWorldBookNameKey(value)
  if (!candidate) return false
  const excludeId = options?.excludeId
  return Boolean(
    (worldBooks || []).some((book) => {
      if (excludeId != null && book.id === excludeId) return false
      return normalizeWorldBookNameKey(book.name) === candidate
    })
  )
}

export const getWorldBookStarterTemplate = (
  key: string | null | undefined
): WorldBookStarterTemplate | null =>
  WORLD_BOOK_STARTER_TEMPLATES.find((template) => template.key === key) || null

export const buildDuplicateWorldBookName = (
  originalName: unknown,
  worldBooks: Array<{ name?: string }> | undefined
): string => {
  const baseName = normalizeWorldBookName(originalName) || "World Book"
  const existing = new Set((worldBooks || []).map((book) => normalizeWorldBookNameKey(book.name)))

  const firstCandidate = `Copy of ${baseName}`
  if (!existing.has(normalizeWorldBookNameKey(firstCandidate))) return firstCandidate

  let suffix = 2
  while (suffix <= 999) {
    const candidate = `Copy of ${baseName} (${suffix})`
    if (!existing.has(normalizeWorldBookNameKey(candidate))) return candidate
    suffix += 1
  }
  return `Copy of ${baseName} (${Date.now()})`
}

export const buildWorldBookFormPayload = (
  values: Record<string, any>,
  mode: "create" | "edit"
): Record<string, any> => {
  const payload = mode === "create" ? { ...WORLD_BOOK_FORM_DEFAULTS, ...values } : { ...values }
  const templateKey =
    typeof payload.template_key === "string" ? payload.template_key : undefined
  const scanDepth =
    typeof payload.scan_depth === "number" && Number.isFinite(payload.scan_depth)
      ? payload.scan_depth
      : WORLD_BOOK_FORM_DEFAULTS.scan_depth
  const tokenBudget =
    typeof payload.token_budget === "number" && Number.isFinite(payload.token_budget)
      ? payload.token_budget
      : WORLD_BOOK_FORM_DEFAULTS.token_budget

  const normalized: Record<string, any> = {
    ...payload,
    name: normalizeWorldBookName(payload.name),
    description:
      typeof payload.description === "string" ? payload.description.trim() : payload.description,
    enabled:
      typeof payload.enabled === "boolean"
        ? payload.enabled
        : WORLD_BOOK_FORM_DEFAULTS.enabled,
    scan_depth: scanDepth,
    token_budget: tokenBudget,
    recursive_scanning:
      typeof payload.recursive_scanning === "boolean"
        ? payload.recursive_scanning
        : WORLD_BOOK_FORM_DEFAULTS.recursive_scanning
  }
  delete normalized.template_key
  if (templateKey) normalized.template_key = templateKey
  return normalized
}

const cleanErrorMessage = (message?: string | null): string => {
  if (!message) return ""
  return String(message).replace(REQUEST_SUFFIX_PATTERN, "").trim()
}

const getErrorStatus = (error: unknown): number | null =>
  typeof error === "object" && error && typeof (error as { status?: unknown }).status === "number"
    ? (error as { status: number }).status
    : null

const getErrorMessage = (error: unknown): string =>
  typeof error === "object" && error && typeof (error as { message?: unknown }).message === "string"
    ? cleanErrorMessage((error as { message: string }).message)
    : ""

export const isWorldBookVersionConflictError = (error: unknown): boolean => {
  const status = getErrorStatus(error)
  const message = getErrorMessage(error)
  return status === 409 && VERSION_CONFLICT_PATTERN.test(message)
}

export const buildWorldBookMutationErrorMessage = (
  error: unknown,
  options?: { attemptedName?: string; fallback?: string }
): string => {
  const fallback = options?.fallback || "Failed to save world book"
  const status = getErrorStatus(error)
  const message = getErrorMessage(error)

  if (status === 409) {
    if (isWorldBookVersionConflictError(error)) {
      return message || WORLD_BOOK_VERSION_CONFLICT_FALLBACK
    }
    if (message) return message
    const attemptedName = normalizeWorldBookName(options?.attemptedName)
    if (attemptedName) {
      return `A world book named "${attemptedName}" already exists.`
    }
    return "A world book with this name already exists."
  }

  return message || fallback
}
