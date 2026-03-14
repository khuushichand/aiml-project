import React from "react"

import type { DeckSchedulerSettings } from "@/services/flashcards"
import type {
  SchedulerPresetId,
  SchedulerSettingsDraft,
  SchedulerValidationErrors
} from "../utils/scheduler-settings"
import {
  DEFAULT_SCHEDULER_SETTINGS,
  applySchedulerPreset,
  copySchedulerSettings,
  createSchedulerDraft,
  formatSchedulerSummary,
  validateSchedulerDraft
} from "../utils/scheduler-settings"

export type DeckSchedulerDraftState = {
  draft: SchedulerSettingsDraft
  errors: SchedulerValidationErrors
  summary: string | null
  updateField: <K extends keyof SchedulerSettingsDraft>(
    field: K,
    value: SchedulerSettingsDraft[K]
  ) => void
  applyPreset: (presetId: SchedulerPresetId) => void
  resetToDefaults: () => void
  replaceDraft: (settings: DeckSchedulerSettings) => void
  getValidatedSettings: () => DeckSchedulerSettings | null
  clearErrors: () => void
}

export const useDeckSchedulerDraft = (
  initialSettings: DeckSchedulerSettings = DEFAULT_SCHEDULER_SETTINGS
): DeckSchedulerDraftState => {
  const [draft, setDraft] = React.useState<SchedulerSettingsDraft>(() =>
    createSchedulerDraft(copySchedulerSettings(initialSettings))
  )
  const [errors, setErrors] = React.useState<SchedulerValidationErrors>({})

  const replaceDraft = React.useCallback((settings: DeckSchedulerSettings) => {
    setDraft(createSchedulerDraft(copySchedulerSettings(settings)))
    setErrors({})
  }, [])

  const updateField = React.useCallback(
    <K extends keyof SchedulerSettingsDraft>(field: K, value: SchedulerSettingsDraft[K]) => {
      setDraft((current) => ({ ...current, [field]: value }))
      setErrors((current) => {
        if (!current[field as keyof SchedulerValidationErrors]) return current
        const next = { ...current }
        delete next[field as keyof SchedulerValidationErrors]
        return next
      })
    },
    []
  )

  const applyPreset = React.useCallback((presetId: SchedulerPresetId) => {
    setDraft(createSchedulerDraft(applySchedulerPreset(presetId)))
    setErrors({})
  }, [])

  const resetToDefaults = React.useCallback(() => {
    setDraft(createSchedulerDraft(DEFAULT_SCHEDULER_SETTINGS))
    setErrors({})
  }, [])

  const getValidatedSettings = React.useCallback(() => {
    const parsed = validateSchedulerDraft(draft)
    setErrors(parsed.errors)
    return parsed.settings
  }, [draft])

  const clearErrors = React.useCallback(() => {
    setErrors({})
  }, [])

  const summary = React.useMemo(() => {
    const parsed = validateSchedulerDraft(draft)
    return parsed.settings ? formatSchedulerSummary(parsed.settings) : null
  }, [draft])

  return {
    draft,
    errors,
    summary,
    updateField,
    applyPreset,
    resetToDefaults,
    replaceDraft,
    getValidatedSettings,
    clearErrors
  }
}

export default useDeckSchedulerDraft
