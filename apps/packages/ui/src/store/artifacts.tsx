import { createWithEqualityFn } from "zustand/traditional"

export type ArtifactKind = "code" | "table" | "diagram"

export type ArtifactTableData = {
  headers: string[]
  rows: string[][]
}

export type ArtifactItem = {
  id: string
  title: string
  content: string
  language?: string
  kind: ArtifactKind
  lineCount?: number
  table?: ArtifactTableData
}

type ArtifactState = {
  active: ArtifactItem | null
  isOpen: boolean
  isPinned: boolean
  history: ArtifactItem[]
  unreadCount: number
  openArtifact: (artifact: ArtifactItem, options?: { auto?: boolean }) => void
  setOpen: (value: boolean) => void
  closeArtifact: () => void
  setPinned: (value: boolean) => void
  markRead: () => void
}

export const useArtifactsStore = createWithEqualityFn<ArtifactState>((set, get) => ({
  active: null,
  isOpen: false,
  isPinned: false,
  history: [],
  unreadCount: 0,
  openArtifact: (artifact, options) =>
    set((state) => {
      if (options?.auto && state.isPinned) {
        return state
      }
      const compactViewport =
        options?.auto &&
        typeof window !== "undefined" &&
        typeof window.matchMedia === "function" &&
        window.matchMedia("(max-width: 1023px)").matches
      const shouldOpenPanel = !options?.auto || !compactViewport
      const history = [
        artifact,
        ...state.history.filter((item) => item.id !== artifact.id)
      ].slice(0, 20)
      return {
        active: artifact,
        isOpen: shouldOpenPanel ? true : state.isOpen,
        history,
        unreadCount:
          shouldOpenPanel || state.isOpen ? 0 : Math.min(state.unreadCount + 1, 99)
      }
    }),
  setOpen: (value) =>
    set((state) => {
      if (value) {
        if (!state.active) {
          return { isOpen: false, unreadCount: 0 }
        }
        return {
          isOpen: true,
          unreadCount: 0
        }
      }
      return {
        isOpen: false
      }
    }),
  closeArtifact: () =>
    set(() => ({
      isOpen: false,
      isPinned: false
    })),
  setPinned: (value) =>
    set((state) => ({
      isPinned: value,
      isOpen: value ? state.isOpen || Boolean(state.active) : state.isOpen
    })),
  markRead: () =>
    set(() => ({
      unreadCount: 0
    }))
}))

if (typeof window !== "undefined") {
  ;(window as any).__tldw_useArtifactsStore = useArtifactsStore
}
