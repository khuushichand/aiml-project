import React from "react"

type SavedPreviewCase = {
  id: string
  name: string
  text: string
}

type UseDictionaryPreviewDraftsParams = {
  dictionaryId: number
  t: (key: string, fallback: string) => string
}

type DictionaryPreviewDraftsState = {
  previewText: string
  setPreviewText: React.Dispatch<React.SetStateAction<string>>
  previewCaseName: string
  setPreviewCaseName: React.Dispatch<React.SetStateAction<string>>
  handlePreviewCaseNameChange: (value: string) => void
  previewCaseError: string | null
  setPreviewCaseError: React.Dispatch<React.SetStateAction<string | null>>
  savedPreviewCases: SavedPreviewCase[]
  savePreviewCase: () => void
  loadPreviewCase: (caseId: string) => void
  deletePreviewCase: (caseId: string) => void
}

export function useDictionaryPreviewDrafts({
  dictionaryId,
  t,
}: UseDictionaryPreviewDraftsParams): DictionaryPreviewDraftsState {
  const [previewText, setPreviewText] = React.useState("")
  const [savedPreviewCases, setSavedPreviewCases] = React.useState<SavedPreviewCase[]>([])
  const [previewCaseName, setPreviewCaseName] = React.useState("")
  const [previewCaseError, setPreviewCaseError] = React.useState<string | null>(null)

  const previewDraftStorageKey = React.useMemo(
    () => `tldw:dictionaries:preview-draft:${dictionaryId}`,
    [dictionaryId]
  )
  const previewCasesStorageKey = React.useMemo(
    () => `tldw:dictionaries:preview-cases:${dictionaryId}`,
    [dictionaryId]
  )

  React.useEffect(() => {
    if (typeof window === "undefined") return
    try {
      const savedDraft = window.localStorage.getItem(previewDraftStorageKey)
      setPreviewText(savedDraft ?? "")
    } catch {
      setPreviewText("")
    }

    try {
      const rawSavedCases = window.localStorage.getItem(previewCasesStorageKey)
      if (!rawSavedCases) {
        setSavedPreviewCases([])
        return
      }
      const parsed = JSON.parse(rawSavedCases)
      if (!Array.isArray(parsed)) {
        setSavedPreviewCases([])
        return
      }
      const normalized = parsed
        .filter((item) => item && typeof item === "object")
        .map((item) => ({
          id: String((item as any).id || ""),
          name: String((item as any).name || "").trim(),
          text: String((item as any).text || ""),
        }))
        .filter((item) => item.id && item.name)
      setSavedPreviewCases(normalized)
    } catch {
      setSavedPreviewCases([])
    }
  }, [previewCasesStorageKey, previewDraftStorageKey])

  React.useEffect(() => {
    if (typeof window === "undefined") return
    try {
      window.localStorage.setItem(previewDraftStorageKey, previewText)
    } catch {
      // no-op (private mode or disabled storage)
    }
  }, [previewDraftStorageKey, previewText])

  React.useEffect(() => {
    if (typeof window === "undefined") return
    try {
      window.localStorage.setItem(
        previewCasesStorageKey,
        JSON.stringify(savedPreviewCases)
      )
    } catch {
      // no-op (private mode or disabled storage)
    }
  }, [previewCasesStorageKey, savedPreviewCases])

  const savePreviewCase = React.useCallback(() => {
    const trimmedText = previewText.trim()
    if (!trimmedText) {
      setPreviewCaseError(
        t(
          "option:dictionariesTools.saveCaseEmpty",
          "Enter sample text before saving a test case."
        )
      )
      return
    }

    const trimmedName = previewCaseName.trim()
    const fallbackName = `Case ${savedPreviewCases.length + 1}`
    const nextCase = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      name: trimmedName || fallbackName,
      text: previewText,
    }
    setSavedPreviewCases((previousCases) => [...previousCases, nextCase])
    setPreviewCaseName("")
    setPreviewCaseError(null)
  }, [previewCaseName, previewText, savedPreviewCases.length, t])

  const loadPreviewCase = React.useCallback(
    (caseId: string) => {
      const selectedCase = savedPreviewCases.find((item) => item.id === caseId)
      if (selectedCase) {
        setPreviewText(selectedCase.text)
      }
      setPreviewCaseError(null)
    },
    [savedPreviewCases]
  )

  const deletePreviewCase = React.useCallback((caseId: string) => {
    setSavedPreviewCases((currentCases) =>
      currentCases.filter((item) => item.id !== caseId)
    )
    setPreviewCaseError(null)
  }, [])

  const handlePreviewCaseNameChange = React.useCallback((value: string) => {
    setPreviewCaseName(value)
    setPreviewCaseError(null)
  }, [])

  return {
    previewText,
    setPreviewText,
    previewCaseName,
    setPreviewCaseName,
    handlePreviewCaseNameChange,
    previewCaseError,
    setPreviewCaseError,
    savedPreviewCases,
    savePreviewCase,
    loadPreviewCase,
    deletePreviewCase,
  }
}
