import React from "react"
import type { QueryClient } from "@tanstack/react-query"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import type { useAntdNotification } from "@/hooks/useAntdNotification"
import type { ConfirmDangerOptions } from "@/components/Common/confirm-danger"
import {
  applyTagOperationToTags,
  buildTagUsage,
  characterHasTag,
  parseCharacterTags,
  type CharacterTagOperation
} from "../tag-manager-utils"

type ConfirmDanger = (options: ConfirmDangerOptions) => Promise<boolean>

const isCharacterQueryRouteConflictError = (error: unknown): boolean => {
  const candidate = error as
    | { message?: unknown; details?: unknown; status?: unknown; response?: { status?: unknown } }
    | null
    | undefined
  const rawStatus = candidate?.status ?? candidate?.response?.status
  const statusCodeFromNumberLike =
    typeof rawStatus === "number"
      ? rawStatus
      : typeof rawStatus === "string"
        ? Number(rawStatus)
        : Number.NaN
  const statusCode = Number.isFinite(statusCodeFromNumberLike) ? statusCodeFromNumberLike : null
  const normalizedMessage = String(candidate?.message || "").toLowerCase()
  const normalizedDetails = (() => {
    const details = candidate?.details
    if (typeof details === "string") return details.toLowerCase()
    if (details == null) return ""
    try { return JSON.stringify(details).toLowerCase() } catch { return String(details).toLowerCase() }
  })()
  return (
    statusCode === 404 ||
    statusCode === 405 ||
    statusCode === 422 ||
    normalizedMessage.includes("path.character_id") ||
    normalizedMessage.includes("unable to parse string as an integer") ||
    normalizedMessage.includes('input":"query"') ||
    normalizedMessage.includes("/api/v1/characters/query") ||
    normalizedDetails.includes("path.character_id") ||
    normalizedDetails.includes("unable to parse string as an integer") ||
    normalizedDetails.includes('input":"query"') ||
    normalizedDetails.includes("/api/v1/characters/query")
  )
}

const CHARACTER_FOLDER_TOKEN_PREFIXES = [
  "__tldw_folder_id:",
  "__tldw_folder:"
] as const

const isCharacterFolderToken = (tag: unknown): boolean => {
  if (typeof tag !== "string") return false
  const normalized = tag.trim()
  if (!normalized) return false
  for (const prefix of CHARACTER_FOLDER_TOKEN_PREFIXES) {
    if (normalized.startsWith(prefix)) return true
  }
  return false
}

const getCharacterVisibleTags = (tags: unknown): string[] =>
  parseCharacterTags(tags).filter((tag) => !isCharacterFolderToken(tag))

export interface UseCharacterTagManagementDeps {
  /** i18n translator */
  t: (key: string, opts?: Record<string, any>) => string
  /** Notification API */
  notification: ReturnType<typeof useAntdNotification>
  /** React Query client for cache invalidation */
  qc: QueryClient
  /** Confirm danger dialog */
  confirmDanger: ConfirmDanger
}

export function useCharacterTagManagement(deps: UseCharacterTagManagementDeps) {
  const { t, notification, qc, confirmDanger } = deps

  const [tagManagerOpen, setTagManagerOpen] = React.useState(false)
  const [tagManagerLoading, setTagManagerLoading] = React.useState(false)
  const [tagManagerSubmitting, setTagManagerSubmitting] = React.useState(false)
  const [tagManagerCharacters, setTagManagerCharacters] = React.useState<any[]>([])
  const [tagManagerOperation, setTagManagerOperation] =
    React.useState<CharacterTagOperation>("rename")
  const [tagManagerSourceTag, setTagManagerSourceTag] = React.useState<
    string | undefined
  >(undefined)
  const [tagManagerTargetTag, setTagManagerTargetTag] = React.useState("")

  // Bulk tag operations state
  const [bulkTagModalOpen, setBulkTagModalOpen] = React.useState(false)
  const [bulkTagsToAdd, setBulkTagsToAdd] = React.useState<string[]>([])
  const [bulkOperationLoading, setBulkOperationLoading] = React.useState(false)

  const tagManagerTagUsageData = React.useMemo(
    () =>
      buildTagUsage(
        tagManagerCharacters.map((character: any) => ({
          ...character,
          tags: getCharacterVisibleTags(character?.tags)
        }))
      ),
    [tagManagerCharacters]
  )

  const loadTagManagerCharacters = React.useCallback(async () => {
    setTagManagerLoading(true)
    try {
      await tldwClient.initialize()
      const allCharacters: any[] = []
      let page = 1
      const maxPages = 50

      while (page <= maxPages) {
        const response = await tldwClient.listCharactersPage({
          page,
          page_size: 100,
          sort_by: "name",
          sort_order: "asc",
          include_image_base64: false
        })
        const pageItems = Array.isArray(response?.items) ? response.items : []
        allCharacters.push(...pageItems)
        if (!response?.has_more || pageItems.length === 0) break
        page += 1
      }

      setTagManagerCharacters(allCharacters)
    } catch (e: any) {
      if (isCharacterQueryRouteConflictError(e)) {
        try {
          const legacyCharacters = await tldwClient.listAllCharacters({
            pageSize: 250,
            maxPages: 50
          })
          setTagManagerCharacters(
            Array.isArray(legacyCharacters) ? legacyCharacters : []
          )
          return
        } catch {
          // Keep existing error notification flow when legacy fallback also fails.
        }
      }
      notification.error({
        message: t("settings:manageCharacters.tags.manageLoadErrorTitle", {
          defaultValue: "Couldn't load tags"
        }),
        description:
          e?.message ||
          t("settings:manageCharacters.tags.manageLoadErrorDescription", {
            defaultValue: "Unable to load tags right now. Please try again."
          })
      })
    } finally {
      setTagManagerLoading(false)
    }
  }, [notification, t])

  const openTagManager = React.useCallback(() => {
    setTagManagerOpen(true)
    setTagManagerOperation("rename")
    setTagManagerSourceTag(undefined)
    setTagManagerTargetTag("")
    void loadTagManagerCharacters()
  }, [loadTagManagerCharacters])

  const closeTagManager = React.useCallback(() => {
    setTagManagerOpen(false)
    setTagManagerSourceTag(undefined)
    setTagManagerTargetTag("")
    setTagManagerCharacters([])
  }, [])

  const handleApplyTagManagerOperation = React.useCallback(async () => {
    const sourceTag = String(tagManagerSourceTag || "").trim()
    const targetTag = tagManagerTargetTag.trim()

    if (!sourceTag) {
      notification.warning({
        message: t("settings:manageCharacters.tags.selectSource", {
          defaultValue: "Select a tag to modify."
        })
      })
      return
    }

    if (
      (tagManagerOperation === "rename" || tagManagerOperation === "merge") &&
      targetTag.length === 0
    ) {
      notification.warning({
        message: t("settings:manageCharacters.tags.enterTarget", {
          defaultValue: "Enter a destination tag."
        })
      })
      return
    }

    if (
      (tagManagerOperation === "rename" || tagManagerOperation === "merge") &&
      sourceTag === targetTag
    ) {
      notification.info({
        message: t("settings:manageCharacters.tags.sourceEqualsTarget", {
          defaultValue: "Source and destination tags are the same."
        })
      })
      return
    }

    if (tagManagerOperation === "delete") {
      const confirmed = await confirmDanger({
        title: t("settings:manageCharacters.tags.deleteConfirmTitle", {
          defaultValue: "Delete tag '{{tag}}'?",
          tag: sourceTag
        }),
        content: t("settings:manageCharacters.tags.deleteConfirmContent", {
          defaultValue:
            "This removes the tag from every character that currently uses it."
        }),
        okText: t("common:delete", { defaultValue: "Delete" }),
        cancelText: t("common:cancel", { defaultValue: "Cancel" })
      })
      if (!confirmed) return
    }

    const affectedCharacters = tagManagerCharacters.filter((character) =>
      characterHasTag(character, sourceTag)
    )

    if (affectedCharacters.length === 0) {
      notification.info({
        message: t("settings:manageCharacters.tags.noAffectedCharacters", {
          defaultValue: "No characters currently use that tag."
        })
      })
      return
    }

    setTagManagerSubmitting(true)
    let successCount = 0
    let failCount = 0

    try {
      for (const character of affectedCharacters) {
        const characterId = String(
          character?.id || character?.slug || character?.name || ""
        )
        if (!characterId) {
          failCount++
          continue
        }

        const currentTags = parseCharacterTags(character?.tags)
        const nextTags = applyTagOperationToTags(
          currentTags,
          tagManagerOperation,
          sourceTag,
          targetTag
        )

        const unchanged =
          currentTags.length === nextTags.length &&
          currentTags.every((tag, index) => tag === nextTags[index])

        if (unchanged) {
          continue
        }

        try {
          await tldwClient.updateCharacter(
            characterId,
            { tags: nextTags },
            character?.version
          )
          successCount++
        } catch {
          failCount++
        }
      }
    } finally {
      setTagManagerSubmitting(false)
    }

    qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
    await loadTagManagerCharacters()
    setTagManagerSourceTag(undefined)
    setTagManagerTargetTag("")

    if (failCount === 0) {
      notification.success({
        message: t("settings:manageCharacters.tags.manageSuccess", {
          defaultValue: "Updated tags on {{count}} characters.",
          count: successCount
        })
      })
    } else {
      notification.warning({
        message: t("settings:manageCharacters.tags.managePartial", {
          defaultValue: "Updated {{success}} characters, {{fail}} failed.",
          success: successCount,
          fail: failCount
        })
      })
    }
  }, [
    confirmDanger,
    loadTagManagerCharacters,
    notification,
    qc,
    tagManagerCharacters,
    tagManagerOperation,
    tagManagerSourceTag,
    tagManagerTargetTag,
    t
  ])

  const handleBulkAddTags = React.useCallback(
    async (
      selectedCharacterIds: Set<string>,
      data: any[]
    ) => {
      if (selectedCharacterIds.size === 0 || bulkTagsToAdd.length === 0) return

      setBulkOperationLoading(true)
      const selectedChars = (data || []).filter((c: any) =>
        selectedCharacterIds.has(String(c.id || c.slug || c.name))
      )

      let successCount = 0
      let failCount = 0

      for (const char of selectedChars) {
        try {
          const existingTags = parseCharacterTags(char.tags)
          const newTags = [...new Set([...existingTags, ...bulkTagsToAdd])]
          await tldwClient.updateCharacter(
            String(char.id || char.slug || char.name),
            { tags: newTags },
            char.version
          )
          successCount++
        } catch {
          failCount++
        }
      }

      setBulkOperationLoading(false)
      setBulkTagModalOpen(false)
      setBulkTagsToAdd([])
      qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })

      if (failCount === 0) {
        notification.success({
          message: t("settings:manageCharacters.bulk.tagSuccess", {
            defaultValue: "Added tags to {{count}} characters",
            count: successCount
          })
        })
      } else {
        notification.warning({
          message: t("settings:manageCharacters.bulk.tagPartial", {
            defaultValue:
              "Added tags to {{success}} characters, {{fail}} failed",
            success: successCount,
            fail: failCount
          })
        })
      }
    },
    [bulkTagsToAdd, notification, t, qc]
  )

  return {
    // state
    tagManagerOpen,
    setTagManagerOpen,
    tagManagerLoading,
    tagManagerSubmitting,
    tagManagerCharacters,
    tagManagerOperation,
    setTagManagerOperation,
    tagManagerSourceTag,
    setTagManagerSourceTag,
    tagManagerTargetTag,
    setTagManagerTargetTag,
    bulkTagModalOpen,
    setBulkTagModalOpen,
    bulkTagsToAdd,
    setBulkTagsToAdd,
    bulkOperationLoading,
    setBulkOperationLoading,
    // computed
    tagManagerTagUsageData,
    // callbacks
    openTagManager,
    closeTagManager,
    handleApplyTagManagerOperation,
    handleBulkAddTags,
    loadTagManagerCharacters
  }
}
