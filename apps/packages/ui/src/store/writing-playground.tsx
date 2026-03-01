import { createWithEqualityFn } from "zustand/traditional"

type WritingPlaygroundState = {
  activeSessionId: string | null
  activeSessionName: string | null
  workspaceMode: "draft" | "manage"
  setActiveSessionId: (activeSessionId: string | null) => void
  setActiveSessionName: (activeSessionName: string | null) => void
  setWorkspaceMode: (workspaceMode: "draft" | "manage") => void
}

export const useWritingPlaygroundStore = createWithEqualityFn<WritingPlaygroundState>((set) => ({
  activeSessionId: null,
  activeSessionName: null,
  workspaceMode: "draft",
  setActiveSessionId: (activeSessionId) => set({ activeSessionId }),
  setActiveSessionName: (activeSessionName) => set({ activeSessionName }),
  setWorkspaceMode: (workspaceMode) => set({ workspaceMode })
}))
