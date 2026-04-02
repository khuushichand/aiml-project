import React from "react"

const HEALTH_URL = `${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/health`
const MAX_WAIT_MS = 15_000
const RETRY_INTERVAL_MS = 2_000

type GateState = "checking" | "ready" | "waiting" | "timeout"

async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(HEALTH_URL, {
      method: "GET",
      signal: AbortSignal.timeout(3000)
    })
    return res.ok
  } catch {
    return false
  }
}

export const ServerReadinessGate: React.FC<{ children: React.ReactNode }> = ({
  children
}) => {
  const [gate, setGate] = React.useState<GateState>("checking")

  React.useEffect(() => {
    if (typeof window === "undefined") return

    let cancelled = false
    let retryTimer: number | undefined
    const deadline = Date.now() + MAX_WAIT_MS

    const attempt = async () => {
      const ok = await checkHealth()
      if (cancelled) return

      if (ok) {
        setGate("ready")
        return
      }

      if (Date.now() >= deadline) {
        setGate("timeout")
        return
      }

      setGate("waiting")
      retryTimer = window.setTimeout(() => {
        if (!cancelled) void attempt()
      }, RETRY_INTERVAL_MS)
    }

    void attempt()

    return () => {
      cancelled = true
      if (retryTimer) window.clearTimeout(retryTimer)
    }
  }, [])

  if (gate === "ready" || gate === "timeout") {
    return <>{children}</>
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        fontFamily: "system-ui, -apple-system, sans-serif",
        color: "#666",
        gap: "12px"
      }}
    >
      <div
        style={{
          width: "32px",
          height: "32px",
          border: "3px solid #e0e0e0",
          borderTopColor: "#666",
          borderRadius: "50%",
          animation: "tldw-spin 0.8s linear infinite"
        }}
      />
      <p style={{ margin: 0, fontSize: "14px" }}>Waiting for server...</p>
      <style>{`@keyframes tldw-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

export default ServerReadinessGate
