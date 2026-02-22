import React from "react"
import { DictionaryManagerOverlays } from "./DictionaryManagerOverlays"

type UseDictionaryManagerOverlayPropsParams = {
  assignFor: any
  closeQuickAssignModal: () => void
  handleConfirmQuickAssign: () => Promise<void>
  assignChatIds: string[]
  assignSaving: boolean
  assignSearch: string
  setAssignSearch: React.Dispatch<React.SetStateAction<string>>
  assignableChatsStatus: "pending" | "error" | "success"
  assignableChatsError: unknown
  quickAssignChatOptions: Array<{
    chat: any
    chatId: string
    title: string
    state: string
  }>
  refetchAssignableChats: () => Promise<unknown>
  toggleAssignChatSelection: (chatId: string) => void
  openChatContextFromDictionary: (chatRef: any) => void
  openCreate: boolean
  closeCreateModal: () => void
  createForm: any
  handleCreateSubmit: (values: any) => void
  creating: boolean
  openEdit: boolean
  closeDictionaryEditModal: () => void
  editForm: any
  handleEditSubmit: (values: any) => Promise<void>
  updating: boolean
  activeEntriesDictionary: any | null
  openEntries: number | null
  closeDictionaryEntriesPanel: () => void
  useMobileEntriesDrawer: boolean
  entryForm: any
  openImport: boolean
  closeImportModal: () => void
  importFormat: "json" | "markdown"
  handleImportFormatChange: (value: "json" | "markdown") => void
  importMode: "file" | "paste"
  handleImportModeChange: (value: "file" | "paste") => void
  importSourceContent: string
  handleImportSourceContentChange: (value: string) => void
  importMarkdownName: string
  handleImportMarkdownNameChange: (value: string) => void
  importFileName: string | null
  handleImportFileSelection: (event: React.ChangeEvent<HTMLInputElement>) => Promise<void>
  activateOnImport: boolean
  handleActivateOnImportChange: (value: boolean) => void
  buildImportPreview: () => void
  importValidationErrors: string[]
  importPreview: any
  handleConfirmImport: () => Promise<void>
  importing: boolean
  importConflictResolution: any
  closeImportConflictResolution: () => void
  resolveImportConflictRename: () => Promise<void>
  resolveImportConflictReplace: () => Promise<void>
  statsFor: any | null
  setStatsFor: React.Dispatch<React.SetStateAction<any | null>>
  versionHistoryFor: any | null
  setVersionHistoryFor: React.Dispatch<React.SetStateAction<any | null>>
  handleVersionHistoryReverted: () => Promise<void>
}

export function useDictionaryManagerOverlayProps({
  assignFor,
  closeQuickAssignModal,
  handleConfirmQuickAssign,
  assignChatIds,
  assignSaving,
  assignSearch,
  setAssignSearch,
  assignableChatsStatus,
  assignableChatsError,
  quickAssignChatOptions,
  refetchAssignableChats,
  toggleAssignChatSelection,
  openChatContextFromDictionary,
  openCreate,
  closeCreateModal,
  createForm,
  handleCreateSubmit,
  creating,
  openEdit,
  closeDictionaryEditModal,
  editForm,
  handleEditSubmit,
  updating,
  activeEntriesDictionary,
  openEntries,
  closeDictionaryEntriesPanel,
  useMobileEntriesDrawer,
  entryForm,
  openImport,
  closeImportModal,
  importFormat,
  handleImportFormatChange,
  importMode,
  handleImportModeChange,
  importSourceContent,
  handleImportSourceContentChange,
  importMarkdownName,
  handleImportMarkdownNameChange,
  importFileName,
  handleImportFileSelection,
  activateOnImport,
  handleActivateOnImportChange,
  buildImportPreview,
  importValidationErrors,
  importPreview,
  handleConfirmImport,
  importing,
  importConflictResolution,
  closeImportConflictResolution,
  resolveImportConflictRename,
  resolveImportConflictReplace,
  statsFor,
  setStatsFor,
  versionHistoryFor,
  setVersionHistoryFor,
  handleVersionHistoryReverted,
}: UseDictionaryManagerOverlayPropsParams): React.ComponentProps<
  typeof DictionaryManagerOverlays
> {
  return React.useMemo(
    () => ({
      assignFor,
      closeQuickAssignModal,
      handleConfirmQuickAssign: () => {
        void handleConfirmQuickAssign()
      },
      assignChatIds,
      assignSaving,
      assignSearch,
      setAssignSearch,
      assignableChatsStatus,
      assignableChatsError,
      quickAssignChatOptions,
      refetchAssignableChats,
      toggleAssignChatSelection,
      openChatContextFromDictionary,
      openCreate,
      closeCreateModal,
      createForm,
      handleCreateSubmit,
      creating,
      openEdit,
      closeDictionaryEditModal,
      editForm,
      handleEditSubmit,
      updating,
      activeEntriesDictionary,
      openEntries,
      closeDictionaryEntriesPanel,
      useMobileEntriesDrawer,
      entryForm,
      openImport,
      closeImportModal,
      importFormat,
      handleImportFormatChange,
      importMode,
      handleImportModeChange,
      importSourceContent,
      handleImportSourceContentChange,
      importMarkdownName,
      handleImportMarkdownNameChange,
      importFileName,
      handleImportFileSelection,
      activateOnImport,
      handleActivateOnImportChange,
      buildImportPreview,
      importValidationErrors,
      importPreview,
      handleConfirmImport: () => {
        void handleConfirmImport()
      },
      importing,
      importConflictResolution,
      closeImportConflictResolution,
      resolveImportConflictRename,
      resolveImportConflictReplace,
      statsFor,
      setStatsFor,
      versionHistoryFor,
      setVersionHistoryFor,
      handleVersionHistoryReverted: () => {
        void handleVersionHistoryReverted()
      },
    }),
    [
      activeEntriesDictionary,
      activateOnImport,
      assignChatIds,
      assignFor,
      assignSaving,
      assignSearch,
      assignableChatsError,
      assignableChatsStatus,
      buildImportPreview,
      closeCreateModal,
      closeDictionaryEditModal,
      closeDictionaryEntriesPanel,
      closeImportConflictResolution,
      closeImportModal,
      closeQuickAssignModal,
      createForm,
      creating,
      editForm,
      entryForm,
      handleActivateOnImportChange,
      handleConfirmImport,
      handleConfirmQuickAssign,
      handleCreateSubmit,
      handleEditSubmit,
      handleImportFileSelection,
      handleImportFormatChange,
      handleImportMarkdownNameChange,
      handleImportModeChange,
      handleImportSourceContentChange,
      importConflictResolution,
      importFileName,
      importFormat,
      importMarkdownName,
      importMode,
      importPreview,
      importSourceContent,
      importValidationErrors,
      importing,
      openChatContextFromDictionary,
      openCreate,
      openEdit,
      openEntries,
      openImport,
      quickAssignChatOptions,
      refetchAssignableChats,
      resolveImportConflictRename,
      resolveImportConflictReplace,
      setAssignSearch,
      setStatsFor,
      setVersionHistoryFor,
      statsFor,
      versionHistoryFor,
      toggleAssignChatSelection,
      updating,
      useMobileEntriesDrawer,
      handleVersionHistoryReverted,
    ]
  )
}
