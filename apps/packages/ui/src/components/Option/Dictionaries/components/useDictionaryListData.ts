import { useQuery } from "@tanstack/react-query"
import React from "react"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import {
  buildDuplicateDictionaryName,
  filterDictionariesBySearch,
  normalizeDictionaryTags,
} from "../listUtils"

type UseDictionaryListDataParams = {
  isOnline: boolean
  dictionarySearch: string
  dictionaryCategoryFilter: string
  dictionaryTagFilters: string[]
  openEntries: number | null
  notification: {
    success: (config: { message: string; description?: string }) => void
    error: (config: { message: string; description?: string }) => void
  }
  queryClient: {
    invalidateQueries: (input: { queryKey: readonly unknown[] }) => Promise<unknown>
  }
}

type UseDictionaryListDataResult = {
  data: any[] | undefined
  status: "pending" | "error" | "success"
  error: unknown
  refetch: () => Promise<unknown>
  filteredDictionaries: any[]
  categoryFilterOptions: string[]
  tagFilterOptions: string[]
  activeEntriesDictionary: any | null
  dictionariesById: Map<number, any>
  duplicateDictionary: (dictionary: any) => Promise<void>
}

export function useDictionaryListData({
  isOnline,
  dictionarySearch,
  dictionaryCategoryFilter,
  dictionaryTagFilters,
  openEntries,
  notification,
  queryClient,
}: UseDictionaryListDataParams): UseDictionaryListDataResult {
  const { data, status, error, refetch } = useQuery({
    queryKey: ["tldw:listDictionaries"],
    queryFn: async () => {
      await tldwClient.initialize()
      const response = await tldwClient.listDictionaries(true, true)
      return response?.dictionaries || []
    },
    enabled: isOnline,
  })

  const categoryFilterOptions = React.useMemo(() => {
    const categories = new Set<string>()
    for (const dictionary of Array.isArray(data) ? data : []) {
      const category = typeof dictionary?.category === "string"
        ? dictionary.category.trim()
        : ""
      if (category) categories.add(category)
    }
    return Array.from(categories).sort((a, b) => a.localeCompare(b))
  }, [data])

  const tagFilterOptions = React.useMemo(() => {
    const tags = new Set<string>()
    for (const dictionary of Array.isArray(data) ? data : []) {
      for (const tag of normalizeDictionaryTags(dictionary?.tags)) {
        tags.add(tag)
      }
    }
    return Array.from(tags).sort((a, b) => a.localeCompare(b))
  }, [data])

  const filteredDictionaries = React.useMemo(() => {
    const normalizedCategoryFilter = dictionaryCategoryFilter.trim().toLowerCase()
    const normalizedTagFilters = dictionaryTagFilters
      .map((tag) => tag.trim().toLowerCase())
      .filter(Boolean)

    return filterDictionariesBySearch(Array.isArray(data) ? data : [], dictionarySearch)
      .filter((dictionary: any) => {
        if (!normalizedCategoryFilter) return true
        const dictionaryCategory = String(dictionary?.category || "").trim().toLowerCase()
        return dictionaryCategory === normalizedCategoryFilter
      })
      .filter((dictionary: any) => {
        if (normalizedTagFilters.length === 0) return true
        const dictionaryTags = normalizeDictionaryTags(dictionary?.tags).map((tag) =>
          tag.toLowerCase()
        )
        return normalizedTagFilters.some((tag) => dictionaryTags.includes(tag))
      })
  }, [data, dictionaryCategoryFilter, dictionarySearch, dictionaryTagFilters])

  const activeEntriesDictionary = React.useMemo(() => {
    if (openEntries == null) return null
    return (
      (Array.isArray(data) ? data : []).find(
        (dictionary: any) => Number(dictionary?.id) === Number(openEntries)
      ) || null
    )
  }, [data, openEntries])

  const dictionariesById = React.useMemo(() => {
    const next = new Map<number, any>()
    for (const item of Array.isArray(data) ? data : []) {
      const id = Number(item?.id)
      if (!Number.isNaN(id) && id > 0) {
        next.set(id, item)
      }
    }
    return next
  }, [data])

  const duplicateDictionary = React.useCallback(
    async (dictionary: any) => {
      try {
        const exported = await tldwClient.exportDictionaryJSON(dictionary.id)
        const existingNames = Array.isArray(data) ? data.map((item: any) => item?.name) : []
        const duplicateName = buildDuplicateDictionaryName(
          exported?.name || dictionary?.name || "Dictionary",
          existingNames
        )
        const duplicatePayload = {
          ...exported,
          name: duplicateName,
          description: exported?.description ?? dictionary?.description,
        }
        await tldwClient.importDictionaryJSON(
          duplicatePayload,
          Boolean(dictionary?.is_active)
        )
        notification.success({
          message: "Dictionary duplicated",
          description: `"${duplicateName}" created.`,
        })
        await queryClient.invalidateQueries({ queryKey: ["tldw:listDictionaries"] })
      } catch (error: any) {
        notification.error({
          message: "Duplicate failed",
          description: error?.message || "Unable to duplicate dictionary",
        })
      }
    },
    [data, notification, queryClient]
  )

  return {
    data: Array.isArray(data) ? data : undefined,
    status,
    error,
    refetch,
    filteredDictionaries,
    categoryFilterOptions,
    tagFilterOptions,
    activeEntriesDictionary,
    dictionariesById,
    duplicateDictionary,
  }
}
