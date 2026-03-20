import React from "react"
import { useMutation, useQuery, type QueryClient } from "@tanstack/react-query"
import {
  tldwClient,
  type CharacterVersionEntry
} from "@/services/tldw/TldwApiClient"
import type { useAntdNotification } from "@/hooks/useAntdNotification"
import type { ConfirmDangerOptions } from "@/components/Common/confirm-danger"

type ConfirmDanger = (options: ConfirmDangerOptions) => Promise<boolean>

const resolveCharacterNumericId = (record: any): number | null => {
  const raw = record?.id ?? record?.character_id ?? record?.characterId
  const parsed = Number(raw)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null
  }
  return parsed
}

export interface UseCharacterVersionHistoryDeps {
  /** i18n translator */
  t: (key: string, opts?: Record<string, any>) => string
  /** Notification API */
  notification: ReturnType<typeof useAntdNotification>
  /** React Query client for cache invalidation */
  qc: QueryClient
  /** Confirm danger dialog */
  confirmDanger: ConfirmDanger
}

export function useCharacterVersionHistory(deps: UseCharacterVersionHistoryDeps) {
  const { t, notification, qc, confirmDanger } = deps

  const [versionHistoryOpen, setVersionHistoryOpen] = React.useState(false)
  const [versionHistoryCharacter, setVersionHistoryCharacter] = React.useState<any | null>(null)
  const [versionFrom, setVersionFrom] = React.useState<number | null>(null)
  const [versionTo, setVersionTo] = React.useState<number | null>(null)
  const [versionRevertTarget, setVersionRevertTarget] = React.useState<number | null>(null)

  const versionHistoryCharacterId = React.useMemo(
    () => resolveCharacterNumericId(versionHistoryCharacter),
    [versionHistoryCharacter]
  )

  const versionHistoryCharacterName = React.useMemo(
    () =>
      versionHistoryCharacter?.name ||
      versionHistoryCharacter?.title ||
      versionHistoryCharacter?.slug ||
      t("settings:manageCharacters.preview.untitled", {
        defaultValue: "Untitled character"
      }),
    [t, versionHistoryCharacter]
  )

  const {
    data: versionHistoryResponse,
    isPending: versionHistoryLoading,
    isFetching: versionHistoryFetching
  } = useQuery({
    queryKey: ["tldw:characterVersions", versionHistoryCharacterId],
    queryFn: async () => {
      if (versionHistoryCharacterId == null) {
        return { items: [], total: 0 }
      }
      await tldwClient.initialize()
      return await tldwClient.listCharacterVersions(versionHistoryCharacterId, {
        limit: 100
      })
    },
    enabled: versionHistoryOpen && versionHistoryCharacterId != null,
    staleTime: 15 * 1000
  })

  const versionHistoryItems = React.useMemo(
    () =>
      Array.isArray(versionHistoryResponse?.items)
        ? versionHistoryResponse.items
        : ([] as CharacterVersionEntry[]),
    [versionHistoryResponse?.items]
  )

  const versionSelectOptions = React.useMemo(
    () =>
      versionHistoryItems.map((entry) => ({
        value: entry.version,
        label: `v${entry.version} \u2022 ${
          entry.timestamp
            ? new Date(entry.timestamp).toLocaleString()
            : t("settings:manageCharacters.versionHistory.unknownTimestamp", {
                defaultValue: "Unknown time"
              })
        }`
      })),
    [t, versionHistoryItems]
  )

  // Auto-select versions when history loads
  React.useEffect(() => {
    if (!versionHistoryOpen) return
    if (versionHistoryItems.length === 0) {
      setVersionFrom(null)
      setVersionTo(null)
      setVersionRevertTarget(null)
      return
    }

    const knownVersions = new Set(versionHistoryItems.map((entry) => entry.version))
    const latestVersion = versionHistoryItems[0]?.version ?? null
    const baselineVersion =
      versionHistoryItems.find((entry) => entry.version !== latestVersion)?.version ??
      latestVersion

    if (latestVersion != null && (versionTo == null || !knownVersions.has(versionTo))) {
      setVersionTo(latestVersion)
    }
    if (baselineVersion != null && (versionFrom == null || !knownVersions.has(versionFrom))) {
      setVersionFrom(baselineVersion)
    }
    if (
      baselineVersion != null &&
      (versionRevertTarget == null || !knownVersions.has(versionRevertTarget))
    ) {
      setVersionRevertTarget(baselineVersion)
    }
  }, [
    versionFrom,
    versionHistoryItems,
    versionHistoryOpen,
    versionRevertTarget,
    versionTo
  ])

  const {
    data: versionDiffResponse,
    isPending: versionDiffLoading,
    isFetching: versionDiffFetching
  } = useQuery({
    queryKey: [
      "tldw:characterVersionDiff",
      versionHistoryCharacterId,
      versionFrom,
      versionTo
    ],
    queryFn: async () => {
      if (
        versionHistoryCharacterId == null ||
        versionFrom == null ||
        versionTo == null
      ) {
        return null
      }
      await tldwClient.initialize()
      return await tldwClient.diffCharacterVersions(
        versionHistoryCharacterId,
        versionFrom,
        versionTo
      )
    },
    enabled:
      versionHistoryOpen &&
      versionHistoryCharacterId != null &&
      versionFrom != null &&
      versionTo != null &&
      versionFrom !== versionTo,
    staleTime: 15 * 1000
  })

  const { mutate: revertCharacterVersion, isPending: revertingCharacterVersion } =
    useMutation({
      mutationFn: async ({
        characterId,
        targetVersion
      }: {
        characterId: number
        targetVersion: number
      }) => tldwClient.revertCharacter(characterId, targetVersion),
      onSuccess: (updatedCharacter: any, variables) => {
        qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
        qc.invalidateQueries({
          queryKey: ["tldw:characterVersions", variables.characterId]
        })
        const updatedVersion = Number(updatedCharacter?.version)
        if (Number.isFinite(updatedVersion) && updatedVersion > 0) {
          setVersionTo(updatedVersion)
        }
        notification.success({
          message: t("settings:manageCharacters.versionHistory.revertSuccess", {
            defaultValue: "Character reverted"
          }),
          description: t(
            "settings:manageCharacters.versionHistory.revertSuccessDescription",
            {
              defaultValue:
                "Restored version {{target}} and created a new revision.",
              target: variables.targetVersion
            }
          )
        })
      },
      onError: (error: any) => {
        notification.error({
          message: t("settings:manageCharacters.versionHistory.revertError", {
            defaultValue: "Failed to revert character"
          }),
          description:
            error?.message ||
            t("settings:manageCharacters.notification.someError", {
              defaultValue: "Something went wrong. Please try again later"
            })
        })
      }
    })

  const openVersionHistory = React.useCallback(
    (record: any) => {
      const numericId = resolveCharacterNumericId(record)
      if (numericId == null) {
        notification.warning({
          message: t("settings:manageCharacters.versionHistory.unavailable", {
            defaultValue: "Version history unavailable"
          }),
          description: t(
            "settings:manageCharacters.versionHistory.unavailableDescription",
            {
              defaultValue:
                "Version history is available only for saved server characters."
            }
          )
        })
        return
      }
      setVersionHistoryCharacter(record)
      setVersionFrom(null)
      setVersionTo(null)
      setVersionRevertTarget(null)
      setVersionHistoryOpen(true)
    },
    [notification, t]
  )

  return {
    // state
    versionHistoryOpen,
    setVersionHistoryOpen,
    versionHistoryCharacter,
    setVersionHistoryCharacter,
    versionHistoryCharacterId,
    versionHistoryCharacterName,
    versionFrom,
    setVersionFrom,
    versionTo,
    setVersionTo,
    versionRevertTarget,
    setVersionRevertTarget,
    // query results
    versionHistoryItems,
    versionHistoryLoading,
    versionHistoryFetching,
    versionSelectOptions,
    versionDiffResponse,
    versionDiffLoading,
    versionDiffFetching,
    revertingCharacterVersion,
    // callbacks
    openVersionHistory,
    revertCharacterVersion
  }
}
