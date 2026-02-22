import React from "react"
import { useQuery } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import {
  buildDictionaryEntryGroupOptions,
  filterDictionaryEntriesBySearchAndGroup,
} from "../entryListUtils"

type UseDictionaryEntryDataParams = {
  dictionaryId: number
  entrySearch: string
  entryGroupFilter?: string
}

type DictionaryEntryDataState = {
  normalizedEntryGroupFilter?: string
  entriesQueryKey: readonly [string, number, string]
  allEntriesQueryKey: readonly [string, number]
  entriesStatus: "pending" | "success" | "error" | string
  entriesError: unknown
  refetchEntries: () => Promise<unknown>
  entries: any[]
  allEntries: any[]
  entryGroupOptions: Array<{ label: string; value: string }>
  filteredEntries: any[]
  hasAnyEntries: boolean
  allEntriesById: Map<number, any>
  filteredEntryIds: number[]
  orderedEntryIds: number[]
  entryPriorityById: Map<number, number>
  canReorderEntries: boolean
}

export function useDictionaryEntryData({
  dictionaryId,
  entrySearch,
  entryGroupFilter,
}: UseDictionaryEntryDataParams): DictionaryEntryDataState {
  const normalizedEntryGroupFilter = React.useMemo(() => {
    if (typeof entryGroupFilter !== "string") return undefined
    const trimmed = entryGroupFilter.trim()
    return trimmed.length > 0 ? trimmed : undefined
  }, [entryGroupFilter])

  const entriesQueryKey = React.useMemo(
    () =>
      [
        "tldw:listDictionaryEntries",
        dictionaryId,
        normalizedEntryGroupFilter ?? "__all__",
      ] as const,
    [dictionaryId, normalizedEntryGroupFilter]
  )
  const allEntriesQueryKey = React.useMemo(
    () => ["tldw:listDictionaryEntriesAll", dictionaryId] as const,
    [dictionaryId]
  )

  const {
    data: entriesData,
    status: entriesStatus,
    error: entriesError,
    refetch: refetchEntries,
  } = useQuery({
    queryKey: entriesQueryKey,
    queryFn: async () => {
      await tldwClient.initialize()
      const response = await tldwClient.listDictionaryEntries(
        dictionaryId,
        normalizedEntryGroupFilter
      )
      return response?.entries || []
    },
  })

  const { data: allEntriesData } = useQuery({
    queryKey: allEntriesQueryKey,
    queryFn: async () => {
      await tldwClient.initialize()
      const response = await tldwClient.listDictionaryEntries(dictionaryId)
      return response?.entries || []
    },
  })

  const entries = Array.isArray(entriesData) ? entriesData : []
  const allEntries = Array.isArray(allEntriesData) ? allEntriesData : entries

  const entryGroupOptions = React.useMemo(
    () => buildDictionaryEntryGroupOptions(allEntries),
    [allEntries]
  )
  const filteredEntries = React.useMemo(
    () =>
      filterDictionaryEntriesBySearchAndGroup(
        entries,
        entrySearch,
        normalizedEntryGroupFilter
      ),
    [entries, entrySearch, normalizedEntryGroupFilter]
  )
  const hasAnyEntries = allEntries.length > 0

  const allEntriesById = React.useMemo(() => {
    const map = new Map<number, any>()
    for (const entry of allEntries) {
      const entryId = Number(entry?.id)
      if (Number.isFinite(entryId) && entryId > 0) {
        map.set(entryId, entry)
      }
    }
    return map
  }, [allEntries])

  const filteredEntryIds = React.useMemo(
    () =>
      filteredEntries
        .map((entry: any) => Number(entry?.id))
        .filter((entryId: number) => Number.isFinite(entryId) && entryId > 0),
    [filteredEntries]
  )
  const orderedEntryIds = React.useMemo(
    () =>
      allEntries
        .map((entry: any) => Number(entry?.id))
        .filter((entryId: number) => Number.isFinite(entryId) && entryId > 0),
    [allEntries]
  )
  const entryPriorityById = React.useMemo(() => {
    const map = new Map<number, number>()
    orderedEntryIds.forEach((entryId, index) => {
      map.set(entryId, index + 1)
    })
    return map
  }, [orderedEntryIds])

  const canReorderEntries =
    orderedEntryIds.length > 1 &&
    entrySearch.trim().length === 0 &&
    !normalizedEntryGroupFilter &&
    filteredEntries.length === allEntries.length

  return {
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
  }
}
