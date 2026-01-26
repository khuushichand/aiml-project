import { browser } from "./wxt-browser"
import { createSafeStorage } from "@/utils/safe-storage"
import type { TldwConfig } from "@/services/tldw/TldwApiClient"

if (typeof globalThis !== "undefined") {
  const globalScope = globalThis as typeof globalThis & {
    browser?: typeof browser
    chrome?: typeof browser
  }
  if (!globalScope.browser) {
    globalScope.browser = browser
  }
  if (!globalScope.chrome) {
    globalScope.chrome = browser
  }
}

const normalizeBaseUrl = (value?: string | null): string | null => {
  const raw = (value || "").trim()
  if (!raw) return null
  return raw.replace(/\/$/, "")
}

const seedTldwConfigFromEnv = async (): Promise<void> => {
  if (typeof window === "undefined") return

  const serverUrl = normalizeBaseUrl(process.env.NEXT_PUBLIC_API_URL)
  const apiKey = (process.env.NEXT_PUBLIC_X_API_KEY || "").trim() || null
  const apiBearer = (process.env.NEXT_PUBLIC_API_BEARER || "").trim() || null

  if (!serverUrl && !apiKey && !apiBearer) return

  try {
    const storage = createSafeStorage()
    const existing = (await storage.get<TldwConfig>("tldwConfig").catch(() => null)) || null

    const next: TldwConfig = {
      ...(existing || {}),
      authMode: existing?.authMode || "single-user",
      serverUrl: existing?.serverUrl || ""
    }

    let changed = false

    if (!next.serverUrl && serverUrl) {
      next.serverUrl = serverUrl
      changed = true
    }

    if (!next.apiKey && !next.accessToken) {
      if (apiKey) {
        next.authMode = "single-user"
        next.apiKey = apiKey
        changed = true
      } else if (apiBearer) {
        next.authMode = "multi-user"
        next.accessToken = apiBearer
        changed = true
      }
    }

    if (changed) {
      await storage.set("tldwConfig", next)
      if (next.serverUrl) {
        await storage.set("tldwServerUrl", next.serverUrl)
      }
    }
  } catch {
    // Best-effort only; ignore storage failures in web contexts.
  }
}

void seedTldwConfigFromEnv()
