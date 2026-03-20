import React from "react"

export interface UseWorldBookFilteringDeps {
  /** World books list from the query */
  data: any[] | undefined
  /** Reconciled attachment data keyed by world book ID */
  reconciledAttachmentsByBook: Record<number, any[]>
  /** Whether attachments are still loading */
  attachmentsLoading: boolean
}

export function useWorldBookFiltering(deps: UseWorldBookFilteringDeps) {
  const { data, reconciledAttachmentsByBook, attachmentsLoading } = deps

  const [listSearch, setListSearch] = React.useState("")
  const [enabledFilter, setEnabledFilter] = React.useState<"all" | "enabled" | "disabled">("all")
  const [attachmentFilter, setAttachmentFilter] = React.useState<"all" | "attached" | "unattached">("all")
  const [selectedWorldBookKeys, setSelectedWorldBookKeys] = React.useState<React.Key[]>([])
  const [tableSort, setTableSort] = React.useState<{
    field?: "name" | "entry_count" | "enabled"
    order?: "ascend" | "descend" | null
  }>({})

  const filteredWorldBooks = React.useMemo(() => {
    const source = Array.isArray(data) ? data : []
    const query = listSearch.trim().toLowerCase()

    let next = source
    if (query) {
      next = next.filter((book: any) => {
        const name = String(book?.name || "").toLowerCase()
        const description = String(book?.description || "").toLowerCase()
        return name.includes(query) || description.includes(query)
      })
    }

    if (enabledFilter !== "all") {
      const mustBeEnabled = enabledFilter === "enabled"
      next = next.filter((book: any) => Boolean(book?.enabled) === mustBeEnabled)
    }

    if (attachmentFilter !== "all" && !attachmentsLoading) {
      next = next.filter((book: any) => {
        const attachedCount = (reconciledAttachmentsByBook?.[book?.id] || []).length
        return attachmentFilter === "attached" ? attachedCount > 0 : attachedCount === 0
      })
    }

    return next
  }, [
    attachmentFilter,
    attachmentsLoading,
    data,
    enabledFilter,
    listSearch,
    reconciledAttachmentsByBook
  ])

  const hasActiveListFilters =
    listSearch.trim().length > 0 || enabledFilter !== "all" || attachmentFilter !== "all"

  const clearListFilters = React.useCallback(() => {
    setListSearch("")
    setEnabledFilter("all")
    setAttachmentFilter("all")
  }, [])

  const handleTableSortChange = React.useCallback((_: any, __: any, sorter: any) => {
    const resolvedSorter = Array.isArray(sorter) ? sorter[0] : sorter
    const field = resolvedSorter?.field
    setTableSort({
      field:
        field === "name" || field === "entry_count" || field === "enabled"
          ? field
          : undefined,
      order:
        resolvedSorter?.order === "ascend" || resolvedSorter?.order === "descend"
          ? resolvedSorter.order
          : null
    })
  }, [])

  return {
    // state
    listSearch,
    setListSearch,
    enabledFilter,
    setEnabledFilter,
    attachmentFilter,
    setAttachmentFilter,
    selectedWorldBookKeys,
    setSelectedWorldBookKeys,
    tableSort,
    setTableSort,
    // computed
    filteredWorldBooks,
    hasActiveListFilters,
    // callbacks
    clearListFilters,
    handleTableSortChange,
  }
}
