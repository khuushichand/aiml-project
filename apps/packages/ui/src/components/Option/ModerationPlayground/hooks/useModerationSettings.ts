import React from "react"
import { useQuery } from "@tanstack/react-query"

import { useServerOnline } from "@/hooks/useServerOnline"
import {
  getEffectivePolicy,
  getModerationSettings,
  reloadModeration,
  updateModerationSettings,
  type ModerationSettingsResponse
} from "@/services/moderation"
import {
  isEqualJson,
  normalizeCategories,
  normalizeSettingsDraft,
  type SettingsDraft
} from "../moderation-utils"

export interface ModerationSettingsState {
  draft: SettingsDraft
  setDraft: React.Dispatch<React.SetStateAction<SettingsDraft>>
  baseline: SettingsDraft | null
  isDirty: boolean
  settingsQuery: ReturnType<typeof useQuery<ModerationSettingsResponse>>
  policyQuery: ReturnType<typeof useQuery<Record<string, any>>>
  save: () => Promise<void>
  reset: () => void
  reload: () => Promise<void>
}

export function useModerationSettings(activeUserId: string | null = null): ModerationSettingsState {
  const online = useServerOnline()

  const [draft, setDraft] = React.useState<SettingsDraft>({
    piiEnabled: false,
    categoriesEnabled: [],
    persist: false
  })
  const [baseline, setBaseline] = React.useState<SettingsDraft | null>(null)

  const settingsQuery = useQuery<ModerationSettingsResponse>({
    queryKey: ["moderation-settings"],
    queryFn: getModerationSettings,
    enabled: online
  })

  const policyQuery = useQuery<Record<string, any>>({
    queryKey: ["moderation-policy", activeUserId ?? "server"],
    queryFn: () => getEffectivePolicy(activeUserId || undefined),
    enabled: online
  })

  // Sync draft from settingsQuery.data
  React.useEffect(() => {
    if (!settingsQuery.data) return
    const data = settingsQuery.data
    const categories = normalizeCategories(
      data.categories_enabled ?? data.effective?.categories_enabled ?? []
    )
    const piiEnabled =
      data.pii_enabled ??
      (typeof data.effective?.pii_enabled === "boolean"
        ? data.effective.pii_enabled
        : false)
    setDraft((prev) => ({
      ...prev,
      piiEnabled,
      categoriesEnabled: categories
    }))
    setBaseline((prev) => ({
      piiEnabled,
      categoriesEnabled: categories,
      persist: prev?.persist ?? false
    }))
  }, [settingsQuery.data])

  const normalizedDraft = normalizeSettingsDraft(draft)
  const normalizedBaseline = normalizeSettingsDraft(baseline ?? draft)
  const isDirty = baseline !== null && !isEqualJson(normalizedDraft, normalizedBaseline)

  const save = React.useCallback(async () => {
    const payload = {
      pii_enabled: draft.piiEnabled,
      categories_enabled: draft.categoriesEnabled,
      persist: draft.persist
    }
    await updateModerationSettings(payload)
    setBaseline(normalizeSettingsDraft(draft))
    await settingsQuery.refetch()
    await policyQuery.refetch()
  }, [draft, settingsQuery, policyQuery])

  const reset = React.useCallback(() => {
    if (!baseline) return
    setDraft({
      piiEnabled: baseline.piiEnabled,
      categoriesEnabled: [...baseline.categoriesEnabled],
      persist: baseline.persist
    })
  }, [baseline])

  const reload = React.useCallback(async () => {
    await reloadModeration()
    await settingsQuery.refetch()
    await policyQuery.refetch()
  }, [settingsQuery, policyQuery])

  return { draft, setDraft, baseline, isDirty, settingsQuery, policyQuery, save, reset, reload }
}
