import React from "react"
import {
  buildDictionaryImportPreview,
  DictionaryImportFormat,
  DictionaryImportMode,
  DictionaryImportPreview,
  extractFileStem,
} from "./dictionaryImportPreviewUtils"

type UseDictionaryImportStateResult = {
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
  resetImportState: () => void
}

export function useDictionaryImportState(): UseDictionaryImportStateResult {
  const [importFormat, setImportFormat] = React.useState<DictionaryImportFormat>("json")
  const [importMode, setImportMode] = React.useState<DictionaryImportMode>("file")
  const [importSourceContent, setImportSourceContent] = React.useState("")
  const [importMarkdownName, setImportMarkdownName] = React.useState("")
  const [importPreview, setImportPreview] = React.useState<DictionaryImportPreview | null>(
    null
  )
  const [activateOnImport, setActivateOnImport] = React.useState(false)
  const [importValidationErrors, setImportValidationErrors] = React.useState<string[]>([])
  const [importFileName, setImportFileName] = React.useState<string | null>(null)

  const resetImportState = React.useCallback(() => {
    setImportValidationErrors([])
    setImportFileName(null)
    setImportSourceContent("")
    setImportPreview(null)
    setImportMarkdownName("")
    setImportFormat("json")
    setImportMode("file")
  }, [])

  const handleImportFileSelection = React.useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0]
      if (!file) return
      setImportValidationErrors([])
      setImportPreview(null)
      setImportFileName(file.name)

      const loweredName = file.name.toLowerCase()
      if (loweredName.endsWith(".md") || loweredName.endsWith(".markdown")) {
        setImportFormat("markdown")
      } else if (loweredName.endsWith(".json")) {
        setImportFormat("json")
      }

      try {
        const text = await file.text()
        setImportSourceContent(text)
        if (!importMarkdownName.trim()) {
          setImportMarkdownName(extractFileStem(file.name))
        }
      } catch (error: any) {
        setImportValidationErrors([error?.message || "Unable to read selected file."])
        setImportSourceContent("")
      } finally {
        event.target.value = ""
      }
    },
    [importMarkdownName]
  )

  const buildImportPreview = React.useCallback(() => {
    setImportValidationErrors([])
    setImportPreview(null)
    const result = buildDictionaryImportPreview({
      importFormat,
      importMode,
      importSourceContent,
      importMarkdownName,
    })
    if (result.preview) {
      setImportPreview(result.preview)
      return
    }
    setImportValidationErrors(result.errors)
  }, [importFormat, importMarkdownName, importMode, importSourceContent])

  const handleImportFormatChange = React.useCallback((value: DictionaryImportFormat) => {
    setImportFormat(value)
    setImportPreview(null)
    setImportValidationErrors([])
  }, [])

  const handleImportModeChange = React.useCallback((value: DictionaryImportMode) => {
    setImportMode(value)
    setImportPreview(null)
    setImportValidationErrors([])
  }, [])

  const handleImportSourceContentChange = React.useCallback((value: string) => {
    setImportSourceContent(value)
    setImportPreview(null)
    setImportValidationErrors([])
  }, [])

  const handleImportMarkdownNameChange = React.useCallback((value: string) => {
    setImportMarkdownName(value)
  }, [])

  const handleActivateOnImportChange = React.useCallback((value: boolean) => {
    setActivateOnImport(value)
  }, [])

  return {
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
    resetImportState,
  }
}
