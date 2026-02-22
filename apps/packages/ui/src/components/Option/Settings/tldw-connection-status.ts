export type CoreStatus = "unknown" | "checking" | "connected" | "failed"
export type RagStatus = "healthy" | "unhealthy" | "unknown" | "checking"

type TranslateFn = (key: string, defaultValue: string) => string

export const getCoreStatusLabel = (t: TranslateFn, status: CoreStatus) => {
  switch (status) {
    case "checking":
      return t("settings:tldw.connection.coreChecking", "Core: checking…")
    case "connected":
      return t("settings:tldw.connection.coreOk", "Core: reachable")
    case "failed":
      return t("settings:tldw.connection.coreFailed", "Core: unreachable")
    default:
      return t(
        "settings:tldw.connection.coreUnknown",
        "Core: not checked yet"
      )
  }
}

export const getRagStatusLabel = (t: TranslateFn, status: RagStatus) => {
  switch (status) {
    case "checking":
      return t("settings:tldw.connection.ragChecking", "RAG: checking…")
    case "healthy":
      return t("settings:tldw.connection.ragHealthy", "RAG: healthy")
    case "unhealthy":
      return t(
        "settings:tldw.connection.ragUnhealthy",
        "RAG: needs attention"
      )
    default:
      return t(
        "settings:tldw.connection.ragUnknown",
        "RAG: not checked yet"
      )
  }
}
