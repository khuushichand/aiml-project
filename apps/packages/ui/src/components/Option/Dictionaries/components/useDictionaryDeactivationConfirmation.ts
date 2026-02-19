import React from "react"
import { buildDictionaryDeactivationWarning } from "../listUtils"

type UseDictionaryDeactivationConfirmationParams = {
  confirmDanger: (config: {
    title: string
    content: string
    okText: string
    cancelText: string
  }) => Promise<boolean>
  t: (key: string, fallbackOrOptions?: any) => string
}

type UseDictionaryDeactivationConfirmationResult = {
  confirmDeactivationIfNeeded: (dictionary: any, nextIsActive: boolean) => Promise<boolean>
}

export function useDictionaryDeactivationConfirmation({
  confirmDanger,
  t,
}: UseDictionaryDeactivationConfirmationParams): UseDictionaryDeactivationConfirmationResult {
  const confirmDeactivationIfNeeded = React.useCallback(
    async (dictionary: any, nextIsActive: boolean) => {
      if (nextIsActive) return true
      const warning = buildDictionaryDeactivationWarning(
        dictionary,
        t("common:cancel", { defaultValue: "Cancel" })
      )
      if (!warning) return true
      return await confirmDanger(warning)
    },
    [confirmDanger, t]
  )

  return { confirmDeactivationIfNeeded }
}
