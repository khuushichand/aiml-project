import { useMutation } from "@tanstack/react-query"
import React from "react"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { isDictionaryVersionConflictError } from "../listUtils"

type ValidationStatusValue = {
  status: "valid" | "warning" | "error" | "loading" | "unknown"
  message?: string
}

type UseDictionaryValidationAndActivationParams = {
  queryClient: {
    invalidateQueries: (input: { queryKey: readonly unknown[] }) => Promise<unknown>
  }
  notification: {
    error: (config: { message: string; description?: string }) => void
  }
  confirmDanger: (config: {
    title: string
    content: string
    okText: string
    cancelText: string
  }) => Promise<boolean>
  t: (key: string, fallbackOrOptions?: any) => string
  confirmDeactivationIfNeeded: (dictionary: any, nextIsActive: boolean) => Promise<boolean>
}

type UseDictionaryValidationAndActivationResult = {
  validationStatus: Record<number, ValidationStatusValue>
  activeUpdateMap: Record<number, boolean>
  validateDictionary: (dictionaryId: number) => Promise<void>
  handleDictionaryActiveToggle: (record: any, checked: boolean) => Promise<void>
}

export function useDictionaryValidationAndActivation({
  queryClient,
  notification,
  confirmDanger,
  t,
  confirmDeactivationIfNeeded,
}: UseDictionaryValidationAndActivationParams): UseDictionaryValidationAndActivationResult {
  const [validationStatus, setValidationStatus] = React.useState<
    Record<number, ValidationStatusValue>
  >({})
  const [activeUpdateMap, setActiveUpdateMap] = React.useState<Record<number, boolean>>({})

  const validateDictionary = React.useCallback(async (dictionaryId: number) => {
    setValidationStatus((previous) => ({
      ...previous,
      [dictionaryId]: { status: "loading" },
    }))
    try {
      await tldwClient.initialize()
      const dictionary = await tldwClient.getDictionary(dictionaryId)
      const entries = await tldwClient.listDictionaryEntries(dictionaryId)
      const entryList = entries?.entries || []

      const payload = {
        data: {
          name: dictionary?.name || undefined,
          description: dictionary?.description || undefined,
          entries: entryList.map((entry: any) => ({
            pattern: entry.pattern,
            replacement: entry.replacement,
            type: entry.type,
            probability: entry.probability,
            enabled: entry.enabled,
            case_sensitive: entry.case_sensitive,
            group: entry.group,
            timed_effects: entry.timed_effects,
            max_replacements: entry.max_replacements,
          })),
        },
        schema_version: 1,
        strict: false,
      }
      const result = await tldwClient.validateDictionary(payload)

      const errors = Array.isArray(result?.errors) ? result.errors : []
      const warnings = Array.isArray(result?.warnings) ? result.warnings : []

      if (errors.length > 0) {
        setValidationStatus((previous) => ({
          ...previous,
          [dictionaryId]: { status: "error", message: `${errors.length} error(s)` },
        }))
      } else if (warnings.length > 0) {
        setValidationStatus((previous) => ({
          ...previous,
          [dictionaryId]: {
            status: "warning",
            message: `${warnings.length} warning(s)`,
          },
        }))
      } else {
        setValidationStatus((previous) => ({
          ...previous,
          [dictionaryId]: { status: "valid", message: "Valid" },
        }))
      }
    } catch (error: any) {
      setValidationStatus((previous) => ({
        ...previous,
        [dictionaryId]: { status: "error", message: error?.message || "Validation failed" },
      }))
    }
  }, [])

  const { mutateAsync: updateDictionaryActive } = useMutation({
    mutationFn: async ({
      dictionaryId,
      isActive,
      version,
    }: {
      dictionaryId: number
      isActive: boolean
      version?: number
    }) => {
      setActiveUpdateMap((previous) => ({ ...previous, [dictionaryId]: true }))
      return await tldwClient.updateDictionary(dictionaryId, {
        is_active: isActive,
        ...(typeof version === "number" ? { version } : {}),
      })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["tldw:listDictionaries"] })
    },
    onSettled: (_result, _error, variables) => {
      setActiveUpdateMap((previous) => {
        const next = { ...previous }
        delete next[variables.dictionaryId]
        return next
      })
    },
  })

  const handleDictionaryActiveToggle = React.useCallback(
    async (record: any, checked: boolean) => {
      const confirmed = await confirmDeactivationIfNeeded(record, checked)
      if (!confirmed) return

      const dictionaryId = Number(record?.id)
      if (!Number.isFinite(dictionaryId) || dictionaryId <= 0) return

      const version = Number(record?.version)
      try {
        await updateDictionaryActive({
          dictionaryId,
          isActive: checked,
          version: Number.isFinite(version) && version > 0 ? version : undefined,
        })
      } catch (error: any) {
        if (isDictionaryVersionConflictError(error)) {
          const shouldReload = await confirmDanger({
            title: "Dictionary changed in another session",
            content:
              "This dictionary was updated elsewhere. Reload the latest dictionary list and try again.",
            okText: "Reload",
            cancelText: t("common:cancel", { defaultValue: "Cancel" }),
          })
          if (shouldReload) {
            await queryClient.invalidateQueries({ queryKey: ["tldw:listDictionaries"] })
          }
          return
        }
        notification.error({
          message: "Update failed",
          description: error?.message || "Failed to update dictionary status. Please retry.",
        })
      }
    },
    [confirmDanger, confirmDeactivationIfNeeded, notification, queryClient, t, updateDictionaryActive]
  )

  return {
    validationStatus,
    activeUpdateMap,
    validateDictionary,
    handleDictionaryActiveToggle,
  }
}
