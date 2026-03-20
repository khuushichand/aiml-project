import React, { useEffect, useMemo, useState } from "react"
import { useMutation, useQuery, type QueryClient } from "@tanstack/react-query"
import { notification } from "antd"
import {
  listPromptCollectionsServer,
  createPromptCollectionServer,
  updatePromptCollectionServer,
  type PromptCollection
} from "@/services/prompts-api"
import {
  isPromptInCollection,
  mergePromptIdsForCollection
} from "../prompt-collections-utils"

export interface UsePromptCollectionsDeps {
  queryClient: QueryClient
  isOnline: boolean
  t: (key: string, opts?: Record<string, any>) => string
  setSelectedRowKeys: React.Dispatch<React.SetStateAction<React.Key[]>>
}

export function usePromptCollections(deps: UsePromptCollectionsDeps) {
  const { queryClient, isOnline, t, setSelectedRowKeys } = deps

  const [collectionFilter, setCollectionFilter] = useState<number | "all">("all")
  const [createCollectionModalOpen, setCreateCollectionModalOpen] = useState(false)
  const [newCollectionName, setNewCollectionName] = useState("")
  const [newCollectionDescription, setNewCollectionDescription] = useState("")

  const { data: promptCollectionsData, status: promptCollectionsStatus } = useQuery({
    queryKey: ["promptCollections"],
    queryFn: listPromptCollectionsServer,
    enabled: isOnline
  })

  const promptCollections = useMemo<PromptCollection[]>(() => {
    if (!Array.isArray(promptCollectionsData)) return []
    return promptCollectionsData
  }, [promptCollectionsData])

  const selectedCollection = useMemo(() => {
    if (collectionFilter === "all") return null
    return (
      promptCollections.find((item) => item.collection_id === collectionFilter) ||
      null
    )
  }, [collectionFilter, promptCollections])

  useEffect(() => {
    if (collectionFilter === "all") return
    if (!selectedCollection) {
      setCollectionFilter("all")
    }
  }, [collectionFilter, selectedCollection])

  const {
    mutate: createPromptCollectionMutation,
    isPending: isCreatingPromptCollection
  } = useMutation({
    mutationFn: async ({
      name,
      description
    }: {
      name: string
      description?: string
    }) =>
      createPromptCollectionServer({
        name: name.trim(),
        description: description?.trim() || undefined
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["promptCollections"] })
      setCreateCollectionModalOpen(false)
      setNewCollectionName("")
      setNewCollectionDescription("")
      notification.success({
        message: t("managePrompts.collections.createSuccess", {
          defaultValue: "Collection created"
        }),
        description: t("managePrompts.collections.createSuccessDesc", {
          defaultValue: "Prompt collection created successfully."
        })
      })
    },
    onError: (error: any) => {
      notification.error({
        message: t("managePrompts.notification.error"),
        description:
          error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  const {
    mutate: addPromptsToCollectionMutation,
    isPending: isAssigningPromptCollection
  } = useMutation({
    mutationFn: async ({
      collection,
      prompts
    }: {
      collection: PromptCollection
      prompts: any[]
    }) => {
      const merged = mergePromptIdsForCollection(
        collection.prompt_ids || [],
        prompts
      )
      if (merged.added === 0) {
        return {
          added: 0,
          skipped: merged.skipped,
          updatedCollection: null
        }
      }
      const updatedCollection = await updatePromptCollectionServer(
        collection.collection_id,
        { prompt_ids: merged.promptIds }
      )
      return {
        added: merged.added,
        skipped: merged.skipped,
        updatedCollection
      }
    },
    onSuccess: ({ added, skipped }, variables) => {
      queryClient.invalidateQueries({ queryKey: ["promptCollections"] })
      if (added === 0) {
        notification.info({
          message: t("managePrompts.collections.assignNoChanges", {
            defaultValue: "No prompts were added"
          }),
          description:
            skipped > 0
              ? t("managePrompts.collections.assignNoChangesSkipped", {
                  defaultValue:
                    "Selected prompts are already in this collection or not synced yet."
                })
              : t("managePrompts.collections.assignNoChangesDefault", {
                  defaultValue:
                    "Selected prompts are already in this collection."
                })
        })
        return
      }
      setSelectedRowKeys([])
      notification.success({
        message: t("managePrompts.collections.assignSuccess", {
          defaultValue: "Prompts added to collection"
        }),
        description: t("managePrompts.collections.assignSuccessDesc", {
          defaultValue:
            "Added {{added}} prompt(s) to {{name}}{{skippedLabel}}.",
          added,
          name: variables.collection.name,
          skippedLabel:
            skipped > 0
              ? t("managePrompts.collections.assignSkippedSuffix", {
                  defaultValue: " ({{count}} skipped)",
                  count: skipped
                })
              : ""
        })
      })
    },
    onError: (error: any) => {
      notification.error({
        message: t("managePrompts.notification.error"),
        description:
          error?.message || t("managePrompts.notification.someError")
      })
    }
  })

  return {
    // state
    collectionFilter,
    setCollectionFilter,
    createCollectionModalOpen,
    setCreateCollectionModalOpen,
    newCollectionName,
    setNewCollectionName,
    newCollectionDescription,
    setNewCollectionDescription,
    // computed
    promptCollections,
    promptCollectionsStatus,
    selectedCollection,
    // mutations
    createPromptCollectionMutation,
    isCreatingPromptCollection,
    addPromptsToCollectionMutation,
    isAssigningPromptCollection
  }
}
