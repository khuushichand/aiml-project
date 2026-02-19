import React from "react"
import { DictionaryListSection } from "./DictionaryListSection"

type UseDictionaryManagerListSectionPropsParams = {
  dictionarySearch: string
  setDictionarySearch: React.Dispatch<React.SetStateAction<string>>
  dictionaryCategoryFilter: string
  setDictionaryCategoryFilter: React.Dispatch<React.SetStateAction<string>>
  dictionaryTagFilters: string[]
  setDictionaryTagFilters: React.Dispatch<React.SetStateAction<string[]>>
  openImportDictionaryModal: () => void
  openCreateDictionaryModal: () => void
  status: "pending" | "error" | "success"
  dictionariesUnsupported: boolean
  dictionariesUnsupportedTitle: string
  dictionariesUnsupportedDescription: string
  dictionariesUnsupportedPrimaryActionLabel: string
  openHealthDiagnostics: () => void
  data: any[] | undefined
  filteredDictionaries: any[]
  categoryFilterOptions: string[]
  tagFilterOptions: string[]
  columns: any[]
  error: unknown
  refetch: () => Promise<unknown>
}

export function useDictionaryManagerListSectionProps({
  dictionarySearch,
  setDictionarySearch,
  dictionaryCategoryFilter,
  setDictionaryCategoryFilter,
  dictionaryTagFilters,
  setDictionaryTagFilters,
  openImportDictionaryModal,
  openCreateDictionaryModal,
  status,
  dictionariesUnsupported,
  dictionariesUnsupportedTitle,
  dictionariesUnsupportedDescription,
  dictionariesUnsupportedPrimaryActionLabel,
  openHealthDiagnostics,
  data,
  filteredDictionaries,
  categoryFilterOptions,
  tagFilterOptions,
  columns,
  error,
  refetch,
}: UseDictionaryManagerListSectionPropsParams): React.ComponentProps<
  typeof DictionaryListSection
> {
  const onRetry = React.useCallback(() => {
    void refetch()
  }, [refetch])

  return React.useMemo(
    () => ({
      dictionarySearch,
      onDictionarySearchChange: setDictionarySearch,
      categoryFilter: dictionaryCategoryFilter,
      onCategoryFilterChange: setDictionaryCategoryFilter,
      tagFilters: dictionaryTagFilters,
      onTagFiltersChange: setDictionaryTagFilters,
      categoryFilterOptions,
      tagFilterOptions,
      onOpenImport: openImportDictionaryModal,
      onOpenCreate: openCreateDictionaryModal,
      status,
      dictionariesUnsupported,
      unsupportedTitle: dictionariesUnsupportedTitle,
      unsupportedDescription: dictionariesUnsupportedDescription,
      unsupportedPrimaryActionLabel: dictionariesUnsupportedPrimaryActionLabel,
      onOpenHealthDiagnostics: openHealthDiagnostics,
      data,
      filteredDictionaries,
      columns,
      error,
      onRetry,
    }),
    [
      categoryFilterOptions,
      columns,
      data,
      dictionariesUnsupported,
      dictionariesUnsupportedDescription,
      dictionariesUnsupportedPrimaryActionLabel,
      dictionariesUnsupportedTitle,
      dictionarySearch,
      dictionaryCategoryFilter,
      dictionaryTagFilters,
      error,
      filteredDictionaries,
      onRetry,
      openCreateDictionaryModal,
      openHealthDiagnostics,
      openImportDictionaryModal,
      setDictionaryCategoryFilter,
      setDictionarySearch,
      setDictionaryTagFilters,
      status,
      tagFilterOptions,
    ]
  )
}
