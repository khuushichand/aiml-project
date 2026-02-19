import { useQueryClient } from "@tanstack/react-query"
import { Form } from "antd"
import React from "react"
import { useTranslation } from "react-i18next"
import { useConfirmDanger } from "@/components/Common/confirm-danger"
import { useMobile } from "@/hooks/useMediaQuery"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import { useUndoNotification } from "@/hooks/useUndoNotification"
import { useDictionaryPreviewDrafts } from "./useDictionaryPreviewDrafts"
import { useDictionaryEntryData } from "./useDictionaryEntryData"
import { useValidationRowHighlight } from "./useValidationRowHighlight"
import { useDictionaryMetadata } from "./useDictionaryMetadata"

type UseDictionaryEntryManagerContextParams = {
  dictionaryId: number
}

export function useDictionaryEntryManagerContext({
  dictionaryId,
}: UseDictionaryEntryManagerContextParams) {
  const { t } = useTranslation(["common", "option"])
  const isMobileViewport = useMobile()
  const queryClient = useQueryClient()
  const confirmDanger = useConfirmDanger()
  const notification = useAntdNotification()
  const { showUndoNotification } = useUndoNotification()

  const {
    previewText,
    setPreviewText,
    previewCaseName,
    handlePreviewCaseNameChange,
    previewCaseError,
    savedPreviewCases,
    savePreviewCase,
    loadPreviewCase,
    deletePreviewCase,
  } = useDictionaryPreviewDrafts({ dictionaryId, t })

  const [toolsPanelKeys, setToolsPanelKeys] = React.useState<string[]>([])
  const [entrySearch, setEntrySearch] = React.useState("")
  const [entryGroupFilter, setEntryGroupFilter] = React.useState<string | undefined>(undefined)
  const [editEntryForm] = Form.useForm()

  const { data: dictionaryMeta } = useDictionaryMetadata(dictionaryId)

  const {
    normalizedEntryGroupFilter,
    entriesQueryKey,
    allEntriesQueryKey,
    entriesStatus,
    entriesError,
    refetchEntries,
    entries,
    allEntries,
    entryGroupOptions,
    filteredEntries,
    hasAnyEntries,
    allEntriesById,
    filteredEntryIds,
    orderedEntryIds,
    entryPriorityById,
    canReorderEntries,
  } = useDictionaryEntryData({
    dictionaryId,
    entrySearch,
    entryGroupFilter,
  })

  const { highlightedValidationEntryId, jumpToValidationEntry } =
    useValidationRowHighlight(entries)

  return {
    t,
    isMobileViewport,
    queryClient,
    confirmDanger,
    notification,
    showUndoNotification,
    previewText,
    setPreviewText,
    previewCaseName,
    handlePreviewCaseNameChange,
    previewCaseError,
    savedPreviewCases,
    savePreviewCase,
    loadPreviewCase,
    deletePreviewCase,
    toolsPanelKeys,
    setToolsPanelKeys,
    entrySearch,
    setEntrySearch,
    entryGroupFilter,
    setEntryGroupFilter,
    editEntryForm,
    dictionaryMeta,
    normalizedEntryGroupFilter,
    entriesQueryKey,
    allEntriesQueryKey,
    entriesStatus,
    entriesError,
    refetchEntries,
    entries,
    allEntries,
    entryGroupOptions,
    filteredEntries,
    hasAnyEntries,
    allEntriesById,
    filteredEntryIds,
    orderedEntryIds,
    entryPriorityById,
    canReorderEntries,
    highlightedValidationEntryId,
    jumpToValidationEntry,
  }
}
