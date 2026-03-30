import type { CompanionHomeSurface } from "@/services/companion-home"

export type CompanionHomeCardId =
  | "inbox-preview"
  | "needs-attention"
  | "resume-work"
  | "goals-focus"
  | "recent-activity"
  | "reading-queue"

export type CompanionHomeLayoutCard = {
  id: CompanionHomeCardId
  title: string
  kind: "system" | "core"
  fixed: boolean
  visible: boolean
}

type StoredCompanionHomeLayoutOverride = {
  order: CompanionHomeCardId[]
  hidden: CompanionHomeCardId[]
}

const STORAGE_KEY_PREFIX = "tldw:companion-home-layout:"

export const DEFAULT_COMPANION_HOME_LAYOUT: CompanionHomeLayoutCard[] = [
  {
    id: "inbox-preview",
    title: "Inbox Preview",
    kind: "system",
    fixed: true,
    visible: true
  },
  {
    id: "needs-attention",
    title: "Needs Attention",
    kind: "system",
    fixed: true,
    visible: true
  },
  {
    id: "resume-work",
    title: "Resume Work",
    kind: "core",
    fixed: false,
    visible: true
  },
  {
    id: "goals-focus",
    title: "Goals / Focus",
    kind: "core",
    fixed: false,
    visible: true
  },
  {
    id: "recent-activity",
    title: "Recent Activity",
    kind: "core",
    fixed: false,
    visible: true
  },
  {
    id: "reading-queue",
    title: "Reading Queue",
    kind: "core",
    fixed: false,
    visible: true
  }
]

const DEFAULT_CARD_IDS = DEFAULT_COMPANION_HOME_LAYOUT.map((card) => card.id)

const sanitizeStoredOverride = (
  value: unknown
): StoredCompanionHomeLayoutOverride | null => {
  if (!value || typeof value !== "object") {
    return null
  }

  const record = value as Partial<StoredCompanionHomeLayoutOverride>
  const order = Array.isArray(record.order)
    ? record.order.filter((id): id is CompanionHomeCardId =>
        DEFAULT_CARD_IDS.includes(id as CompanionHomeCardId)
      )
    : []
  const hidden = Array.isArray(record.hidden)
    ? record.hidden.filter((id): id is CompanionHomeCardId =>
        DEFAULT_CARD_IDS.includes(id as CompanionHomeCardId)
      )
    : []

  return {
    order,
    hidden
  }
}

const getStorageKey = (surface: CompanionHomeSurface): string =>
  `${STORAGE_KEY_PREFIX}${surface}`

const readStoredOverride = async (
  surface: CompanionHomeSurface
): Promise<StoredCompanionHomeLayoutOverride | null> => {
  const key = getStorageKey(surface)

  try {
    if (typeof chrome !== "undefined" && chrome.storage?.local) {
      const result = await chrome.storage.local.get(key)
      return sanitizeStoredOverride(result[key])
    }
  } catch {
    // Fall back to localStorage below.
  }

  try {
    const raw = localStorage.getItem(key)
    return sanitizeStoredOverride(raw ? JSON.parse(raw) : null)
  } catch {
    return null
  }
}

const writeStoredOverride = async (
  surface: CompanionHomeSurface,
  override: StoredCompanionHomeLayoutOverride
): Promise<void> => {
  const key = getStorageKey(surface)

  try {
    if (typeof chrome !== "undefined" && chrome.storage?.local) {
      await chrome.storage.local.set({ [key]: override })
      return
    }
  } catch {
    // Fall back to localStorage below.
  }

  try {
    localStorage.setItem(key, JSON.stringify(override))
  } catch {
    // Ignore persistence failures for local-only layout settings.
  }
}

const buildLayoutFromOverride = (
  override: StoredCompanionHomeLayoutOverride | null
): CompanionHomeLayoutCard[] => {
  const orderedIds = override?.order ?? []
  const hiddenIds = new Set(override?.hidden ?? [])
  const fixedCardIds = DEFAULT_COMPANION_HOME_LAYOUT
    .filter((card) => card.fixed)
    .map((card) => card.id)
  const movableCardIds = DEFAULT_COMPANION_HOME_LAYOUT
    .filter((card) => !card.fixed)
    .map((card) => card.id)
  const seen = new Set<CompanionHomeCardId>()
  const mergedMovableOrder = [...orderedIds, ...movableCardIds].filter((id) => {
    if (fixedCardIds.includes(id)) {
      return false
    }
    if (seen.has(id)) return false
    seen.add(id)
    return true
  })
  const mergedOrder = [...fixedCardIds, ...mergedMovableOrder]

  return mergedOrder.map((id) => {
    const card = DEFAULT_COMPANION_HOME_LAYOUT.find((entry) => entry.id === id)
    if (!card) {
      throw new Error(`Unknown companion home card id: ${id}`)
    }
    if (card.fixed) {
      return {
        ...card,
        visible: true
      }
    }
    return {
      ...card,
      visible: !hiddenIds.has(card.id)
    }
  })
}

const createStoredOverride = (
  layout: CompanionHomeLayoutCard[]
): StoredCompanionHomeLayoutOverride => ({
  order: layout
    .map((card) => card.id)
    .filter((id, index, items) => items.indexOf(id) === index),
  hidden: layout
    .filter((card) => !card.fixed && !card.visible)
    .map((card) => card.id)
})

export const loadCompanionHomeLayout = async (
  surface: CompanionHomeSurface
): Promise<CompanionHomeLayoutCard[]> => {
  const override = await readStoredOverride(surface)
  return buildLayoutFromOverride(override)
}

export const saveCompanionHomeLayout = async (
  surface: CompanionHomeSurface,
  layout: CompanionHomeLayoutCard[]
): Promise<void> => {
  await writeStoredOverride(surface, createStoredOverride(layout))
}

export const setCompanionHomeCardVisibility = (
  layout: CompanionHomeLayoutCard[],
  cardId: CompanionHomeCardId,
  visible: boolean
): CompanionHomeLayoutCard[] =>
  layout.map((card) =>
    card.id === cardId && !card.fixed
      ? {
          ...card,
          visible
        }
      : card.fixed
        ? {
            ...card,
            visible: true
          }
        : card
  )

export const moveCompanionHomeCard = (
  layout: CompanionHomeLayoutCard[],
  cardId: CompanionHomeCardId,
  direction: "up" | "down"
): CompanionHomeLayoutCard[] => {
  const currentIndex = layout.findIndex((card) => card.id === cardId)
  if (currentIndex === -1 || layout[currentIndex]?.fixed) {
    return layout
  }

  let targetIndex = -1
  if (direction === "up") {
    for (let index = currentIndex - 1; index >= 0; index -= 1) {
      if (!layout[index]?.fixed) {
        targetIndex = index
        break
      }
    }
  } else {
    for (let index = currentIndex + 1; index < layout.length; index += 1) {
      if (!layout[index]?.fixed) {
        targetIndex = index
        break
      }
    }
  }

  if (targetIndex === -1) {
    return layout
  }

  const nextLayout = [...layout]
  const [card] = nextLayout.splice(currentIndex, 1)
  nextLayout.splice(targetIndex, 0, card)
  return nextLayout
}
