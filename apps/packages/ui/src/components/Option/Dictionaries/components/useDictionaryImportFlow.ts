import React from "react"
import {
  DictionaryImportConflictResolution,
  DictionaryImportFormat,
  DictionaryImportMode,
  DictionaryImportPreview,
} from "./dictionaryImportPreviewUtils"
import { useDictionaryImportExecution } from "./useDictionaryImportExecution"
import { useDictionaryImportState } from "./useDictionaryImportState"

type UseDictionaryImportFlowParams = {
  dictionaries: any[] | undefined
  queryClient: {
    invalidateQueries: (input: { queryKey: readonly unknown[] }) => Promise<unknown>
  }
  notification: {
    error: (config: { message: string; description?: string }) => void
  }
  confirmDanger: (config: {
    title: string
    content: string
    okText: string
    cancelText: string
  }) => Promise<boolean>
  t: (key: string, fallbackOrOptions?: any) => string
}

type UseDictionaryImportFlowResult = {
  openImport: boolean
  openImportModal: () => void
  closeImportModal: () => void
  importFormat: DictionaryImportFormat
  handleImportFormatChange: (value: DictionaryImportFormat) => void
  importMode: DictionaryImportMode
  handleImportModeChange: (value: DictionaryImportMode) => void
  importSourceContent: string
  handleImportSourceContentChange: (value: string) => void
  importMarkdownName: string
  handleImportMarkdownNameChange: (value: string) => void
  importFileName: string | null
  handleImportFileSelection: (event: React.ChangeEvent<HTMLInputElement>) => Promise<void>
  activateOnImport: boolean
  handleActivateOnImportChange: (value: boolean) => void
  importValidationErrors: string[]
  importPreview: DictionaryImportPreview | null
  buildImportPreview: () => void
  importing: boolean
  handleConfirmImport: () => Promise<void>
  importConflictResolution: DictionaryImportConflictResolution
  closeImportConflictResolution: () => void
  resolveImportConflictRename: () => Promise<void>
  resolveImportConflictReplace: () => Promise<void>
}

export function useDictionaryImportFlow({
  dictionaries,
  queryClient,
  notification,
  confirmDanger,
  t,
}: UseDictionaryImportFlowParams): UseDictionaryImportFlowResult {
  const [openImport, setOpenImport] = React.useState(false)
  const {
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
    importValidationErrors,
    importPreview,
    buildImportPreview: buildImportPreviewInternal,
    resetImportState,
  } = useDictionaryImportState()

  const openImportModal = React.useCallback(() => {
    setOpenImport(true)
  }, [])

  const {
    importing,
    importConflictResolution,
    clearImportConflictResolution,
    handleConfirmImport,
    resolveImportConflictRename,
    resolveImportConflictReplace,
  } = useDictionaryImportExecution({
    dictionaries,
    queryClient,
    notification,
    confirmDanger,
    t,
    activateOnImport,
    importPreview,
    onImportSuccess: React.useCallback(() => {
      setOpenImport(false)
      resetImportState()
    }, [resetImportState]),
  })

  const closeImportModal = React.useCallback(() => {
    setOpenImport(false)
    resetImportState()
    clearImportConflictResolution()
  }, [clearImportConflictResolution, resetImportState])

  const buildImportPreview = React.useCallback(() => {
    clearImportConflictResolution()
    buildImportPreviewInternal()
  }, [buildImportPreviewInternal, clearImportConflictResolution])

  return {
    openImport,
    openImportModal,
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
    importValidationErrors,
    importPreview,
    buildImportPreview,
    importing,
    handleConfirmImport,
    importConflictResolution,
    closeImportConflictResolution: clearImportConflictResolution,
    resolveImportConflictRename,
    resolveImportConflictReplace,
  }
}
