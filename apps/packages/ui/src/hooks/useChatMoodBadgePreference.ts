import React from "react"
import { useStorage } from "@plasmohq/storage/hook"
import { createSafeStorage } from "@/utils/safe-storage"

export const CHAT_MOOD_BADGE_STORAGE_KEY = "chatShowMoodBadge"
export const CHAT_MOOD_BADGE_MIGRATION_STORAGE_KEY =
  "chatShowMoodBadgeMigrationV1"
export const CHAT_MOOD_BADGE_DEFAULT = false

type StorageHookMeta<T> =
  | {
      isLoading?: boolean
      setRenderValue?: (value: T | undefined) => void
    }
  | undefined

type StorageHookResult = readonly [
  boolean | undefined,
  (value: boolean | ((prev: boolean | undefined) => boolean)) => Promise<void> | void,
  StorageHookMeta<boolean>
]

const moodBadgeStorage = createSafeStorage({ area: "local" })

const normalizeBoolean = (value: unknown, fallback: boolean): boolean =>
  typeof value === "boolean" ? value : fallback

export const useChatMoodBadgePreference = () => {
  const preferenceResult = useStorage<boolean>(
    {
      key: CHAT_MOOD_BADGE_STORAGE_KEY,
      instance: moodBadgeStorage
    },
    CHAT_MOOD_BADGE_DEFAULT
  ) as StorageHookResult
  const migrationResult = useStorage<boolean>(
    {
      key: CHAT_MOOD_BADGE_MIGRATION_STORAGE_KEY,
      instance: moodBadgeStorage
    },
    false
  ) as StorageHookResult

  const [storedPreference, setStoredPreference, preferenceMeta] =
    preferenceResult
  const [migrationAppliedRaw, setMigrationApplied, migrationMeta] =
    migrationResult
  const migrationApplied = normalizeBoolean(migrationAppliedRaw, false)
  const showMoodBadge = migrationApplied
    ? normalizeBoolean(storedPreference, CHAT_MOOD_BADGE_DEFAULT)
    : CHAT_MOOD_BADGE_DEFAULT

  const setPreferenceRenderValueRef = React.useRef<
    ((value: boolean | undefined) => void) | undefined
  >(preferenceMeta?.setRenderValue)
  const setMigrationRenderValueRef = React.useRef<
    ((value: boolean | undefined) => void) | undefined
  >(migrationMeta?.setRenderValue)
  const migrationHandledRef = React.useRef(false)

  React.useEffect(() => {
    setPreferenceRenderValueRef.current = preferenceMeta?.setRenderValue
  }, [preferenceMeta?.setRenderValue])

  React.useEffect(() => {
    setMigrationRenderValueRef.current = migrationMeta?.setRenderValue
  }, [migrationMeta?.setRenderValue])

  React.useEffect(() => {
    if (preferenceMeta?.isLoading || migrationMeta?.isLoading) return
    if (migrationHandledRef.current) return
    migrationHandledRef.current = true

    if (migrationApplied) return

    setPreferenceRenderValueRef.current?.(CHAT_MOOD_BADGE_DEFAULT)
    setMigrationRenderValueRef.current?.(true)

    const applyMigration = async () => {
      try {
        await moodBadgeStorage.set(
          CHAT_MOOD_BADGE_STORAGE_KEY,
          CHAT_MOOD_BADGE_DEFAULT
        )
        await moodBadgeStorage.set(CHAT_MOOD_BADGE_MIGRATION_STORAGE_KEY, true)
      } catch {
        // Ignore storage failures and keep the default hidden render state.
      }
    }

    void applyMigration()
  }, [migrationApplied, migrationMeta?.isLoading, preferenceMeta?.isLoading])

  const updateShowMoodBadge = React.useCallback(
    async (next: boolean | ((prev: boolean) => boolean)) => {
      const resolved =
        typeof next === "function" ? next(showMoodBadge) : next
      const normalized = Boolean(resolved)

      setPreferenceRenderValueRef.current?.(normalized)
      setMigrationRenderValueRef.current?.(true)
      await setStoredPreference(normalized)
      if (!migrationApplied) {
        await setMigrationApplied(true)
      }
    },
    [migrationApplied, setMigrationApplied, setStoredPreference, showMoodBadge]
  )

  return [
    showMoodBadge,
    updateShowMoodBadge,
    {
      isLoading: Boolean(preferenceMeta?.isLoading || migrationMeta?.isLoading),
      setRenderValue: setPreferenceRenderValueRef.current
    }
  ] as const
}
