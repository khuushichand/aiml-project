import { createStore } from "zustand/vanilla"
import { createWithEqualityFn } from "zustand/traditional"
import {
  createJSONStorage,
  persist,
  type PersistStorage,
  type StateStorage
} from "zustand/middleware"

import type { PersonaBuddyPositionBucket } from "@/types/persona-buddy"

export type PersonaBuddyShellPosition = {
  x: number
  y: number
}

export type PersonaBuddyShellPositionMap = Record<
  PersonaBuddyPositionBucket,
  PersonaBuddyShellPosition
>

type PersonaBuddyShellPersistedState = {
  positions: Partial<PersonaBuddyShellPositionMap>
}

export type PersonaBuddyShellState = {
  isCompact: boolean
  isExpanded: boolean
  positions: PersonaBuddyShellPositionMap
  setCompact: () => void
  setExpanded: (expanded: boolean) => void
  toggleExpanded: () => void
  setPositionForBucket: (
    bucket: PersonaBuddyPositionBucket | string,
    position: PersonaBuddyShellPosition
  ) => void
  getPositionForBucket: (
    bucket: PersonaBuddyPositionBucket | string
  ) => PersonaBuddyShellPosition
  resetPositionForBucket: (bucket: PersonaBuddyPositionBucket | string) => void
  resetPositions: () => void
}

const STORAGE_KEY = "tldw-persona-buddy-shell"

const createMemoryStorage = (): StateStorage => ({
  getItem: () => null,
  setItem: () => {},
  removeItem: () => {}
})

const isValidPosition = (
  value: unknown
): value is PersonaBuddyShellPosition => {
  if (!value || typeof value !== "object") {
    return false
  }

  const candidate = value as Partial<PersonaBuddyShellPosition>
  return (
    typeof candidate.x === "number" &&
    Number.isFinite(candidate.x) &&
    typeof candidate.y === "number" &&
    Number.isFinite(candidate.y)
  )
}

export const DEFAULT_PERSONA_BUDDY_POSITION_BY_BUCKET: PersonaBuddyShellPositionMap =
  {
    "web-desktop": { x: 24, y: 80 },
    "sidepanel-desktop": { x: 20, y: 80 }
  }

const DEFAULT_BUCKET: PersonaBuddyPositionBucket = "web-desktop"

export const clampPersonaBuddyPositionBucket = (
  bucket: PersonaBuddyPositionBucket | string | null | undefined
): PersonaBuddyPositionBucket =>
  bucket === "web-desktop" || bucket === "sidepanel-desktop"
    ? bucket
    : DEFAULT_BUCKET

export const normalizePersonaBuddyShellPositions = (
  positions: Partial<Record<string, unknown>> | null | undefined
): PersonaBuddyShellPositionMap => {
  const next: PersonaBuddyShellPositionMap = {
    ...DEFAULT_PERSONA_BUDDY_POSITION_BY_BUCKET
  }

  if (!positions || typeof positions !== "object") {
    return next
  }

  for (const bucket of ["web-desktop", "sidepanel-desktop"] as const) {
    const candidate = positions[bucket]
    if (isValidPosition(candidate)) {
      next[bucket] = {
        x: candidate.x,
        y: candidate.y
      }
    }
  }

  return next
}

const createPersonaBuddyShellStorage = (): PersistStorage<
  PersonaBuddyShellPersistedState
> => createJSONStorage(() => {
  if (typeof localStorage !== "undefined") {
    return localStorage
  }
  return createMemoryStorage()
})

const createPersonaBuddyShellBaseState = (
  set: (partial: Partial<PersonaBuddyShellState> | ((state: PersonaBuddyShellState) => Partial<PersonaBuddyShellState>)) => void,
  get: () => PersonaBuddyShellState
): PersonaBuddyShellState => ({
  isCompact: true,
  isExpanded: false,
  positions: { ...DEFAULT_PERSONA_BUDDY_POSITION_BY_BUCKET },
  setCompact: () =>
    set((state) =>
      state.isCompact && !state.isExpanded
        ? state
        : { isCompact: true, isExpanded: false }
    ),
  setExpanded: (expanded) =>
    set((state) =>
      state.isExpanded === expanded && state.isCompact === !expanded
        ? state
        : { isExpanded: expanded, isCompact: !expanded }
    ),
  toggleExpanded: () =>
    set((state) => ({
      isExpanded: !state.isExpanded,
      isCompact: state.isExpanded
    })),
  setPositionForBucket: (bucket, position) => {
    const resolvedBucket = clampPersonaBuddyPositionBucket(bucket)
    set((state) => ({
      positions: {
        ...state.positions,
        [resolvedBucket]: {
          x: position.x,
          y: position.y
        }
      }
    }))
  },
  getPositionForBucket: (bucket) => {
    const resolvedBucket = clampPersonaBuddyPositionBucket(bucket)
    const position = get().positions[resolvedBucket]
    return position ?? DEFAULT_PERSONA_BUDDY_POSITION_BY_BUCKET[resolvedBucket]
  },
  resetPositionForBucket: (bucket) => {
    const resolvedBucket = clampPersonaBuddyPositionBucket(bucket)
    set((state) => ({
      positions: {
        ...state.positions,
        [resolvedBucket]:
          DEFAULT_PERSONA_BUDDY_POSITION_BY_BUCKET[resolvedBucket]
      }
    }))
  },
  resetPositions: () =>
    set({
      positions: { ...DEFAULT_PERSONA_BUDDY_POSITION_BY_BUCKET }
    })
})

const buildPersonaBuddyShellStore = () =>
  createStore<PersonaBuddyShellState>()(
    persist(
      (set, get) => createPersonaBuddyShellBaseState(set, get),
      {
        name: STORAGE_KEY,
        storage: createPersonaBuddyShellStorage(),
        partialize: (state): PersonaBuddyShellPersistedState => ({
          positions: state.positions
        }),
        merge: (persistedState, currentState) => {
          const persisted = persistedState as
            | Partial<PersonaBuddyShellPersistedState>
            | undefined
          return {
            ...currentState,
            positions: normalizePersonaBuddyShellPositions(
              persisted?.positions ?? currentState.positions
            )
          }
        }
      }
    )
  )

export const createPersonaBuddyShellStore = buildPersonaBuddyShellStore

export const usePersonaBuddyShellStore = createWithEqualityFn<PersonaBuddyShellState>()(
  persist(
    (set, get) => createPersonaBuddyShellBaseState(set, get),
    {
      name: STORAGE_KEY,
      storage: createPersonaBuddyShellStorage(),
      partialize: (state): PersonaBuddyShellPersistedState => ({
        positions: state.positions
      }),
      merge: (persistedState, currentState) => {
        const persisted = persistedState as
          | Partial<PersonaBuddyShellPersistedState>
          | undefined
        return {
          ...currentState,
          positions: normalizePersonaBuddyShellPositions(
            persisted?.positions ?? currentState.positions
          )
        }
      }
    }
  )
)
