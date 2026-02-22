import React from "react"
import { DictionaryListSection } from "./DictionaryListSection"
import { useDictionaryManagerDataFlows } from "./useDictionaryManagerDataFlows"
import { useDictionaryManagerEnvironment } from "./useDictionaryManagerEnvironment"
import { useDictionaryManagerListSectionProps } from "./useDictionaryManagerListSectionProps"
import { useDictionaryManagerWorkspaceControls } from "./useDictionaryManagerWorkspaceControls"

type UseDictionaryManagerListRenderPropsParams = {
  environment: ReturnType<typeof useDictionaryManagerEnvironment>
  dataFlows: ReturnType<typeof useDictionaryManagerDataFlows>
  workspaceControls: ReturnType<typeof useDictionaryManagerWorkspaceControls>
}

export function useDictionaryManagerListRenderProps({
  environment,
  dataFlows,
  workspaceControls,
}: UseDictionaryManagerListRenderPropsParams): React.ComponentProps<
  typeof DictionaryListSection
> {
  return useDictionaryManagerListSectionProps({
    dictionarySearch: environment.dictionarySearch,
    setDictionarySearch: environment.setDictionarySearch,
    dictionaryCategoryFilter: environment.dictionaryCategoryFilter,
    setDictionaryCategoryFilter: environment.setDictionaryCategoryFilter,
    dictionaryTagFilters: environment.dictionaryTagFilters,
    setDictionaryTagFilters: environment.setDictionaryTagFilters,
    openImportDictionaryModal: workspaceControls.openImportDictionaryModal,
    openCreateDictionaryModal: workspaceControls.openCreateDictionaryModal,
    status: dataFlows.status,
    dictionariesUnsupported: Boolean(workspaceControls.dictionariesUnsupported),
    dictionariesUnsupportedTitle: workspaceControls.dictionariesUnsupportedTitle,
    dictionariesUnsupportedDescription:
      workspaceControls.dictionariesUnsupportedDescription,
    dictionariesUnsupportedPrimaryActionLabel:
      workspaceControls.dictionariesUnsupportedPrimaryActionLabel,
    openHealthDiagnostics: workspaceControls.openHealthDiagnostics,
    data: dataFlows.data,
    filteredDictionaries: dataFlows.filteredDictionaries,
    categoryFilterOptions: dataFlows.categoryFilterOptions,
    tagFilterOptions: dataFlows.tagFilterOptions,
    columns: workspaceControls.columns,
    error: dataFlows.error,
    refetch: dataFlows.refetch,
  })
}
