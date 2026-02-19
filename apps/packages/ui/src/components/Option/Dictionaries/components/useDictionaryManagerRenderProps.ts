import React from "react"
import { DictionaryManagerOverlays } from "./DictionaryManagerOverlays"
import { DictionaryListSection } from "./DictionaryListSection"
import { useDictionaryManagerFocusRestoration } from "./useDictionaryManagerFocusRestoration"
import { useDictionaryManagerDataFlows } from "./useDictionaryManagerDataFlows"
import { useDictionaryManagerEnvironment } from "./useDictionaryManagerEnvironment"
import { useDictionaryManagerWorkspaceControls } from "./useDictionaryManagerWorkspaceControls"
import { useDictionaryManagerListRenderProps } from "./useDictionaryManagerListRenderProps"
import { useDictionaryManagerOverlayRenderProps } from "./useDictionaryManagerOverlayRenderProps"

type UseDictionaryManagerRenderPropsParams = {
  environment: ReturnType<typeof useDictionaryManagerEnvironment>
  dataFlows: ReturnType<typeof useDictionaryManagerDataFlows>
  workspaceControls: ReturnType<typeof useDictionaryManagerWorkspaceControls>
}

type DictionaryManagerRenderProps = {
  listSectionProps: React.ComponentProps<typeof DictionaryListSection>
  overlayProps: React.ComponentProps<typeof DictionaryManagerOverlays>
}

export function useDictionaryManagerRenderProps({
  environment,
  dataFlows,
  workspaceControls,
}: UseDictionaryManagerRenderPropsParams): DictionaryManagerRenderProps {
  useDictionaryManagerFocusRestoration({
    openEntries: dataFlows.openEntries,
    statsFor: environment.statsFor,
    versionHistoryFor: environment.versionHistoryFor,
    assignFor: dataFlows.assignFor,
    openImport: dataFlows.openImport,
    openCreate: workspaceControls.openCreate,
    openEdit: workspaceControls.openEdit,
    createDialogFocusReturnRef: environment.createDialogFocusReturnRef,
    editDialogFocusReturnRef: environment.editDialogFocusReturnRef,
    entriesDrawerFocusReturnRef: environment.entriesDrawerFocusReturnRef,
    importDialogFocusReturnRef: environment.importDialogFocusReturnRef,
    quickAssignFocusReturnRef: environment.quickAssignFocusReturnRef,
    statsDialogFocusReturnRef: environment.statsDialogFocusReturnRef,
    versionHistoryDialogFocusReturnRef:
      environment.versionHistoryDialogFocusReturnRef,
  })

  const listSectionProps = useDictionaryManagerListRenderProps({
    environment,
    dataFlows,
    workspaceControls,
  })

  const overlayProps = useDictionaryManagerOverlayRenderProps({
    environment,
    dataFlows,
    workspaceControls,
  })

  return {
    listSectionProps,
    overlayProps,
  }
}
