import React from "react"

type UseDictionariesAvailabilityParams = {
  capsLoading: boolean
  capabilities: { hasChatDictionaries?: boolean } | null | undefined
  t: (key: string, options?: Record<string, unknown>) => string
}

type UseDictionariesAvailabilityResult = {
  dictionariesUnsupported: boolean
  dictionariesUnsupportedTitle: string
  dictionariesUnsupportedDescription: string
  dictionariesUnsupportedPrimaryActionLabel: string
  openHealthDiagnostics: () => void
}

export function useDictionariesAvailability({
  capsLoading,
  capabilities,
  t,
}: UseDictionariesAvailabilityParams): UseDictionariesAvailabilityResult {
  const dictionariesUnsupported = Boolean(
    !capsLoading && capabilities && !capabilities.hasChatDictionaries
  )
  const dictionariesUnsupportedTitle = t("option:dictionaries.offlineTitle", {
    defaultValue: "Chat dictionaries API not available on this server",
  })
  const dictionariesUnsupportedDescription = t(
    "option:dictionaries.offlineDescription",
    {
      defaultValue:
        "This tldw server does not advertise the /api/v1/chat/dictionaries endpoints. Upgrade your server to a version that includes chat dictionaries to use this workspace.",
    }
  )
  const dictionariesUnsupportedPrimaryActionLabel = t(
    "settings:healthSummary.diagnostics",
    {
      defaultValue: "Health & diagnostics",
    }
  )
  const openHealthDiagnostics = React.useCallback(() => {
    try {
      window.location.hash = "#/settings/health"
    } catch {
      // best-effort navigation
    }
  }, [])

  return {
    dictionariesUnsupported,
    dictionariesUnsupportedTitle,
    dictionariesUnsupportedDescription,
    dictionariesUnsupportedPrimaryActionLabel,
    openHealthDiagnostics,
  }
}
