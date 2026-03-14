import React from "react"

import type {
  DeckSchedulerSettingsEnvelope,
  DeckSchedulerType,
  FsrsSchedulerSettings
} from "@/services/flashcards"
import type {
  SchedulerPresetId,
  SchedulerSettingsDraft,
  SchedulerValidationErrors
} from "../utils/scheduler-settings"
import {
  DEFAULT_FSRS_SCHEDULER_SETTINGS,
  DEFAULT_SCHEDULER_SETTINGS,
  applySchedulerPreset,
  copySchedulerSettingsEnvelope,
  createSchedulerDraft,
  createFsrsSchedulerDraft,
  createSm2SchedulerDraft,
  formatSchedulerSummary,
  validateSchedulerDraft
} from "../utils/scheduler-settings"

export type DeckSchedulerDraftState = {
  draft: SchedulerSettingsDraft
  errors: SchedulerValidationErrors
  summary: string | null
  replaceDraftState: (draft: SchedulerSettingsDraft) => void
  updateSchedulerType: (schedulerType: DeckSchedulerType) => void
  updateSm2Field: <K extends keyof SchedulerSettingsDraft["sm2_plus"]>(
    field: K,
    value: SchedulerSettingsDraft["sm2_plus"][K]
  ) => void
  updateFsrsField: <K extends keyof SchedulerSettingsDraft["fsrs"]>(
    field: K,
    value: SchedulerSettingsDraft["fsrs"][K]
  ) => void
  applyPreset: (presetId: SchedulerPresetId) => void
  resetToDefaults: () => void
  replaceDraft: (config: {
    schedulerType: DeckSchedulerType
    settings: DeckSchedulerSettingsEnvelope
  }) => void
  getValidatedSettings: () => {
    scheduler_type: DeckSchedulerType
    scheduler_settings: DeckSchedulerSettingsEnvelope
  } | null
  clearErrors: () => void
}

export const useDeckSchedulerDraft = (
  initialConfig: {
    schedulerType?: DeckSchedulerType
    settings?: DeckSchedulerSettingsEnvelope
  } = {}
): DeckSchedulerDraftState => {
  const [draft, setDraft] = React.useState<SchedulerSettingsDraft>(() =>
    createSchedulerDraft({
      schedulerType: initialConfig.schedulerType ?? "sm2_plus",
      settings: initialConfig.settings
    })
  )
  const [errors, setErrors] = React.useState<SchedulerValidationErrors>({
    sm2_plus: {},
    fsrs: {}
  })

  const replaceDraft = React.useCallback(
    (config: { schedulerType: DeckSchedulerType; settings: DeckSchedulerSettingsEnvelope }) => {
      setDraft(
        createSchedulerDraft({
          schedulerType: config.schedulerType,
          settings: copySchedulerSettingsEnvelope(config.settings)
        })
      )
      setErrors({ sm2_plus: {}, fsrs: {} })
    },
    []
  )

  const replaceDraftState = React.useCallback((nextDraft: SchedulerSettingsDraft) => {
    setDraft(nextDraft)
    setErrors({ sm2_plus: {}, fsrs: {} })
  }, [])

  const clearErrors = React.useCallback(() => {
    setErrors({ sm2_plus: {}, fsrs: {} })
  }, [])

  const updateSchedulerType = React.useCallback((schedulerType: DeckSchedulerType) => {
    setDraft((current) => ({ ...current, scheduler_type: schedulerType }))
  }, [])

  const updateSm2Field = React.useCallback(
    <K extends keyof SchedulerSettingsDraft["sm2_plus"]>(
      field: K,
      value: SchedulerSettingsDraft["sm2_plus"][K]
    ) => {
      setDraft((current) => ({
        ...current,
        sm2_plus: {
          ...current.sm2_plus,
          [field]: value
        }
      }))
      setErrors((current) => {
        if (!current.sm2_plus[field as keyof typeof current.sm2_plus]) return current
        return {
          ...current,
          sm2_plus: {
            ...current.sm2_plus,
            [field]: undefined
          }
        }
      })
    },
    []
  )

  const updateFsrsField = React.useCallback(
    <K extends keyof SchedulerSettingsDraft["fsrs"]>(
      field: K,
      value: SchedulerSettingsDraft["fsrs"][K]
    ) => {
      setDraft((current) => ({
        ...current,
        fsrs: {
          ...current.fsrs,
          [field]: value
        }
      }))
      setErrors((current) => {
        if (!current.fsrs[field as keyof typeof current.fsrs]) return current
        return {
          ...current,
          fsrs: {
            ...current.fsrs,
            [field]: undefined
          }
        }
      })
    },
    []
  )

  const applyPreset = React.useCallback((presetId: SchedulerPresetId) => {
    setDraft((current) => {
      const presetEnvelope = applySchedulerPreset(current.scheduler_type, presetId)
      if (current.scheduler_type === "fsrs") {
        return {
          ...current,
          fsrs: createFsrsSchedulerDraft(presetEnvelope.fsrs)
        }
      }
      return {
        ...current,
        sm2_plus: createSm2SchedulerDraft(presetEnvelope.sm2_plus)
      }
    })
    setErrors({ sm2_plus: {}, fsrs: {} })
  }, [])

  const resetToDefaults = React.useCallback(() => {
    setDraft((current) =>
      current.scheduler_type === "fsrs"
        ? {
            ...current,
            fsrs: createFsrsSchedulerDraft(DEFAULT_FSRS_SCHEDULER_SETTINGS)
          }
        : {
            ...current,
            sm2_plus: createSm2SchedulerDraft(DEFAULT_SCHEDULER_SETTINGS)
          }
    )
    setErrors({ sm2_plus: {}, fsrs: {} })
  }, [])

  const getValidatedSettings = React.useCallback(() => {
    const parsed = validateSchedulerDraft(draft)
    setErrors(parsed.errors)
    if (!parsed.settings) return null
    return {
      scheduler_type: parsed.schedulerType,
      scheduler_settings: parsed.settings
    }
  }, [draft])

  const summary = React.useMemo(() => {
    const parsed = validateSchedulerDraft(draft)
    return parsed.settings ? formatSchedulerSummary(parsed.schedulerType, parsed.settings) : null
  }, [draft])

  return {
    draft,
    errors,
    summary,
    replaceDraftState,
    updateSchedulerType,
    updateSm2Field,
    updateFsrsField,
    applyPreset,
    resetToDefaults,
    replaceDraft,
    getValidatedSettings,
    clearErrors
  }
}

export default useDeckSchedulerDraft
