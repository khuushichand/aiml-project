type SessionStatus = "running" | "completed" | "failed" | "cancelled"

export type QuickIngestSessionStartAck = {
  ok: boolean
  sessionId: string
}

export type QuickIngestSessionCancelResponse = {
  ok: boolean
  error?: string
}

export type QuickIngestSessionRunContext = {
  sessionId: string
  isCancelled: () => boolean
  registerAbortController: (controller: AbortController) => void
  setJobIds: (jobIds: number[]) => void
  emitProgress: (payload: Record<string, unknown>) => void | Promise<void>
}

export type QuickIngestSessionRunResult = {
  results: Array<Record<string, unknown>>
  summary?: Record<string, unknown>
}

type RuntimeDeps = {
  run: (
    payload: Record<string, unknown>,
    context: QuickIngestSessionRunContext
  ) => Promise<QuickIngestSessionRunResult>
  emit: (type: string, payload: Record<string, unknown>) => void | Promise<void>
  createSessionId?: () => string
}

type QuickIngestSession = {
  sessionId: string
  status: SessionStatus
  cancelled: boolean
  jobIds: number[]
  abortControllers: Set<AbortController>
}

const secureSessionSuffix = (): string => {
  try {
    if (typeof globalThis !== "undefined" && typeof globalThis.crypto?.randomUUID === "function") {
      return globalThis.crypto.randomUUID().replace(/-/g, "")
    }
    if (typeof globalThis !== "undefined" && typeof globalThis.crypto?.getRandomValues === "function") {
      const bytes = new Uint8Array(8)
      globalThis.crypto.getRandomValues(bytes)
      return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("")
    }
  } catch {
    // Fall back to timestamp-only suffix below.
  }
  return Date.now().toString(36)
}

const defaultSessionId = () =>
  `qi-${Date.now()}-${secureSessionSuffix().slice(0, 16)}`

export const createQuickIngestSessionRuntime = (deps: RuntimeDeps) => {
  const sessions = new Map<string, QuickIngestSession>()

  const start = (payload: Record<string, unknown>): QuickIngestSessionStartAck => {
    const sessionId = deps.createSessionId?.() || defaultSessionId()
    const session: QuickIngestSession = {
      sessionId,
      status: "running",
      cancelled: false,
      jobIds: [],
      abortControllers: new Set()
    }
    sessions.set(sessionId, session)

    queueMicrotask(async () => {
      try {
        const result = await deps.run(payload, {
          sessionId,
          isCancelled: () => session.cancelled,
          registerAbortController: (controller: AbortController) => {
            session.abortControllers.add(controller)
          },
          setJobIds: (jobIds: number[]) => {
            session.jobIds = jobIds
          },
          emitProgress: async (progressPayload: Record<string, unknown>) => {
            await deps.emit("tldw:quick-ingest/progress", {
              sessionId,
              ...progressPayload
            })
          }
        })
        if (session.cancelled) {
          return
        }
        session.status = "completed"
        await deps.emit("tldw:quick-ingest/completed", {
          sessionId,
          results: Array.isArray(result?.results) ? result.results : [],
          summary: result?.summary || {}
        })
      } catch (error) {
        if (session.cancelled) {
          return
        }
        session.status = "failed"
        await deps.emit("tldw:quick-ingest/failed", {
          sessionId,
          error: error instanceof Error ? error.message : String(error || "Quick ingest failed.")
        })
      } finally {
        sessions.delete(sessionId)
      }
    })

    return {
      ok: true,
      sessionId
    }
  }

  const cancel = (
    sessionId: string,
    reason: string = "user_cancelled"
  ): QuickIngestSessionCancelResponse => {
    const normalizedSessionId = String(sessionId || "").trim()
    if (!normalizedSessionId) {
      return { ok: false, error: "Missing sessionId." }
    }
    const session = sessions.get(normalizedSessionId)
    if (!session) {
      return { ok: false, error: "Session not found." }
    }
    if (session.cancelled) {
      return { ok: true }
    }

    session.cancelled = true
    session.status = "cancelled"
    for (const controller of Array.from(session.abortControllers)) {
      try {
        controller.abort()
      } catch {
        // best effort
      }
    }
    void deps.emit("tldw:quick-ingest/cancelled", {
      sessionId: normalizedSessionId,
      reason,
      jobIds: session.jobIds
    })
    return { ok: true }
  }

  return {
    start,
    cancel,
    hasSession: (sessionId: string) => sessions.has(String(sessionId || "").trim())
  }
}
