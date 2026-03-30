import React from "react"
import type { InputRef } from "antd"

type CharacterListScope = "active" | "deleted"

const PAGE_SIZE_STORAGE_KEY = "characters-page-size"
const DEFAULT_PAGE_SIZE = 10
const PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const

const normalizePageSize = (value: unknown): number => {
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string"
        ? Number.parseInt(value, 10)
        : Number.NaN
  return PAGE_SIZE_OPTIONS.includes(parsed as (typeof PAGE_SIZE_OPTIONS)[number])
    ? parsed
    : DEFAULT_PAGE_SIZE
}

export interface UseCharacterFilteringDeps {
  /** i18n translator */
  t: (key: string, opts?: Record<string, any>) => string
}

export function useCharacterFiltering(deps: UseCharacterFilteringDeps) {
  const { t } = deps

  const searchInputRef = React.useRef<InputRef>(null)
  const searchDebounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  const [searchTerm, setSearchTerm] = React.useState("")
  const [debouncedSearchTerm, setDebouncedSearchTerm] = React.useState("")
  const [filterTags, setFilterTags] = React.useState<string[]>([])
  const [folderFilterId, setFolderFilterId] = React.useState<string | undefined>(undefined)
  const [matchAllTags, setMatchAllTags] = React.useState(false)
  const [creatorFilter, setCreatorFilter] = React.useState<string | undefined>(undefined)
  const [createdFromDate, setCreatedFromDate] = React.useState("")
  const [createdToDate, setCreatedToDate] = React.useState("")
  const [updatedFromDate, setUpdatedFromDate] = React.useState("")
  const [updatedToDate, setUpdatedToDate] = React.useState("")
  const [hasConversationsOnly, setHasConversationsOnly] = React.useState(false)
  const [favoritesOnly, setFavoritesOnly] = React.useState(false)
  const [advancedFiltersOpen, setAdvancedFiltersOpen] = React.useState(false)
  const [characterListScope, setCharacterListScope] = React.useState<CharacterListScope>("active")

  const [sortColumn, setSortColumn] = React.useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("characters-sort-column") || "activity"
    }
    return "activity"
  })
  const [sortOrder, setSortOrder] = React.useState<"ascend" | "descend" | null>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("characters-sort-order")
      return saved === "ascend" || saved === "descend" ? saved : "descend"
    }
    return "descend"
  })

  const [currentPage, setCurrentPage] = React.useState(1)
  const [pageSize, setPageSize] = React.useState<number>(() => {
    if (typeof window !== "undefined") {
      return normalizePageSize(localStorage.getItem(PAGE_SIZE_STORAGE_KEY))
    }
    return DEFAULT_PAGE_SIZE
  })

  // C8: Debounce search input to reduce API calls
  React.useEffect(() => {
    if (searchDebounceRef.current) {
      clearTimeout(searchDebounceRef.current)
    }
    searchDebounceRef.current = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm)
    }, 300)
    return () => {
      if (searchDebounceRef.current) {
        clearTimeout(searchDebounceRef.current)
        searchDebounceRef.current = null
      }
    }
  }, [searchTerm])

  // Persist sort preference
  React.useEffect(() => {
    if (typeof window !== "undefined") {
      if (sortColumn) {
        localStorage.setItem("characters-sort-column", sortColumn)
      } else {
        localStorage.removeItem("characters-sort-column")
      }
      if (sortOrder) {
        localStorage.setItem("characters-sort-order", sortOrder)
      } else {
        localStorage.removeItem("characters-sort-order")
      }
    }
  }, [sortColumn, sortOrder])

  // Persist page size
  React.useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(PAGE_SIZE_STORAGE_KEY, String(pageSize))
    }
  }, [pageSize])

  // Reset to page 1 when filters change
  React.useEffect(() => {
    setCurrentPage(1)
  }, [
    characterListScope,
    creatorFilter,
    debouncedSearchTerm,
    filterTags,
    favoritesOnly,
    folderFilterId,
    hasConversationsOnly,
    matchAllTags
  ])

  const hasFilters =
    searchTerm.trim().length > 0 ||
    (filterTags && filterTags.length > 0) ||
    !!folderFilterId ||
    !!creatorFilter ||
    createdFromDate.trim().length > 0 ||
    createdToDate.trim().length > 0 ||
    updatedFromDate.trim().length > 0 ||
    updatedToDate.trim().length > 0 ||
    hasConversationsOnly ||
    favoritesOnly

  const activeAdvancedFilterCount = React.useMemo(() => {
    let count = 0
    if (filterTags.length > 0) count += 1
    if (folderFilterId) count += 1
    if (creatorFilter) count += 1
    if (createdFromDate.trim().length > 0 || createdToDate.trim().length > 0) count += 1
    if (updatedFromDate.trim().length > 0 || updatedToDate.trim().length > 0) count += 1
    if (hasConversationsOnly) count += 1
    if (favoritesOnly) count += 1
    return count
  }, [
    filterTags,
    folderFilterId,
    creatorFilter,
    createdFromDate,
    createdToDate,
    updatedFromDate,
    updatedToDate,
    hasConversationsOnly,
    favoritesOnly
  ])

  const clearFilters = React.useCallback(() => {
    setSearchTerm("")
    setFilterTags([])
    setFolderFilterId(undefined)
    setMatchAllTags(false)
    setCreatorFilter(undefined)
    setCreatedFromDate("")
    setCreatedToDate("")
    setUpdatedFromDate("")
    setUpdatedToDate("")
    setHasConversationsOnly(false)
    setFavoritesOnly(false)
  }, [])

  React.useEffect(() => {
    if (activeAdvancedFilterCount > 0) {
      setAdvancedFiltersOpen(true)
    }
  }, [activeAdvancedFilterCount])

  return {
    // refs
    searchInputRef,
    // state
    searchTerm,
    setSearchTerm,
    debouncedSearchTerm,
    filterTags,
    setFilterTags,
    folderFilterId,
    setFolderFilterId,
    matchAllTags,
    setMatchAllTags,
    creatorFilter,
    setCreatorFilter,
    createdFromDate,
    setCreatedFromDate,
    createdToDate,
    setCreatedToDate,
    updatedFromDate,
    setUpdatedFromDate,
    updatedToDate,
    setUpdatedToDate,
    hasConversationsOnly,
    setHasConversationsOnly,
    favoritesOnly,
    setFavoritesOnly,
    advancedFiltersOpen,
    setAdvancedFiltersOpen,
    characterListScope,
    setCharacterListScope,
    sortColumn,
    setSortColumn,
    sortOrder,
    setSortOrder,
    currentPage,
    setCurrentPage,
    pageSize,
    setPageSize,
    // computed
    hasFilters,
    activeAdvancedFilterCount,
    // callbacks
    clearFilters
  }
}
