import React from "react"
import { useTranslation } from "react-i18next"

const getPersistenceModeLabel = (
  t: (...args: any[]) => any,
  temporaryChat: boolean,
  isConnectionReady: boolean,
  serverChatId: string | null
) => {
  if (temporaryChat) {
    return t(
      "playground:composer.persistence.ephemeral",
      "Not saved: cleared when you close this window."
    )
  }
  if (serverChatId || isConnectionReady) {
    return t(
      "playground:composer.persistence.server",
      "Saved to your tldw server (and locally)."
    )
  }
  return t(
    "playground:composer.persistence.local",
    "Saved locally until your tldw server is connected."
  )
}

export type UsePersistenceModeParams = {
  temporaryChat: boolean
  serverChatId: string | null
  isConnectionReady: boolean
}

export function usePersistenceMode({
  temporaryChat,
  serverChatId,
  isConnectionReady
}: UsePersistenceModeParams) {
  const { t } = useTranslation(["playground", "common"])

  const persistenceModeLabel = React.useMemo(
    () =>
      getPersistenceModeLabel(
        t,
        temporaryChat,
        isConnectionReady,
        serverChatId
      ),
    [isConnectionReady, serverChatId, temporaryChat, t]
  )

  const persistencePillLabel = React.useMemo(() => {
    if (temporaryChat) {
      return t(
        "playground:composer.persistence.ephemeralPill",
        "Not saved"
      )
    }
    if (serverChatId || isConnectionReady) {
      return t(
        "playground:composer.persistence.serverPill",
        "Server"
      )
    }
    return t(
      "playground:composer.persistence.localPill",
      "Local"
    )
  }, [isConnectionReady, serverChatId, temporaryChat, t])

  const persistenceTooltip = React.useMemo(
    () => (
      <div className="flex flex-col gap-0.5 text-xs">
        <span className="font-medium">{persistencePillLabel}</span>
        <span className="text-text-subtle">{persistenceModeLabel}</span>
      </div>
    ),
    [persistenceModeLabel, persistencePillLabel]
  )

  const focusConnectionCard = React.useCallback(() => {
    try {
      const card = document.getElementById("server-connection-card")
      if (card) {
        card.scrollIntoView({ block: "nearest", behavior: "smooth" })
        ;(card as HTMLElement).focus()
        return
      }
    } catch {
      // ignore DOM errors and fall through to hash navigation
    }
    try {
      const base =
        window.location.href.replace(/#.*$/, "") || "/options.html"
      const target = `${base}#/settings/tldw`
      window.location.href = target
    } catch {
      // ignore navigation failures
    }
  }, [])

  return {
    persistenceModeLabel,
    persistencePillLabel,
    persistenceTooltip,
    focusConnectionCard,
    /** Re-exported for callers that need the raw function (e.g. toggle handler) */
    getPersistenceModeLabel
  }
}
