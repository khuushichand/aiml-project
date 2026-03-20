import type { WorkspaceSlice } from './types'
import type { WorkspaceState } from '../workspace'

// Extract UIActions from workspace.ts (action interface only)
type UIActions = Pick<
  WorkspaceState,
  | 'toggleLeftPane'
  | 'toggleRightPane'
  | 'setLeftPaneCollapsed'
  | 'setRightPaneCollapsed'
  | 'openAddSourceModal'
  | 'closeAddSourceModal'
  | 'setAddSourceModalTab'
  | 'setAddSourceProcessing'
  | 'setAddSourceError'
  | 'focusChatMessageById'
  | 'clearChatFocusTarget'
  | 'focusWorkspaceNote'
  | 'clearNoteFocusTarget'
>

export const createUISlice: WorkspaceSlice<UIActions> = (set, get) => ({
  toggleLeftPane: () =>
    set((state) => ({ leftPaneCollapsed: !state.leftPaneCollapsed })),

  toggleRightPane: () =>
    set((state) => ({ rightPaneCollapsed: !state.rightPaneCollapsed })),

  setLeftPaneCollapsed: (collapsed) => set({ leftPaneCollapsed: collapsed }),

  setRightPaneCollapsed: (collapsed) =>
    set({ rightPaneCollapsed: collapsed }),

  openAddSourceModal: (tab = "upload") =>
    set({
      addSourceModalOpen: true,
      addSourceModalTab: tab,
      addSourceError: null
    }),

  closeAddSourceModal: () =>
    set({
      addSourceModalOpen: false,
      addSourceProcessing: false,
      addSourceError: null
    }),

  setAddSourceModalTab: (tab) => set({ addSourceModalTab: tab }),

  setAddSourceProcessing: (processing) =>
    set({ addSourceProcessing: processing }),

  setAddSourceError: (error) => set({ addSourceError: error }),

  focusChatMessageById: (messageId) => {
    const normalizedMessageId = messageId.trim()
    if (!normalizedMessageId) return false
    set((state) => ({
      chatFocusTarget: {
        messageId: normalizedMessageId,
        token: (state.chatFocusTarget?.token ?? 0) + 1
      }
    }))
    return true
  },

  clearChatFocusTarget: () => set({ chatFocusTarget: null }),

  focusWorkspaceNote: (field = "content") =>
    set((state) => ({
      noteFocusTarget: {
        field,
        token: (state.noteFocusTarget?.token ?? 0) + 1
      }
    })),

  clearNoteFocusTarget: () => set({ noteFocusTarget: null })
})
