import React from "react"
import { useRouter } from "next/router"

const getTokenFromQuery = (value: string | string[] | undefined): string =>
  Array.isArray(value) ? value[0] || "" : value || ""

export function VerifyEmailView() {
  const router = useRouter()
  const [status, setStatus] = React.useState<"pending" | "success" | "error">("pending")
  const [message, setMessage] = React.useState("Verifying your email...")

  React.useEffect(() => {
    const token = getTokenFromQuery(router.query.token)
    if (!token) {
      setStatus("error")
      setMessage("This verification link is incomplete.")
      return
    }

    let cancelled = false
    let redirectHandle: number | undefined

    const verify = async () => {
      try {
        const response = await fetch("/api/auth/verify-email", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ token })
        })

        const payload = await response.json().catch(() => null) as
          | { detail?: string; message?: string }
          | null

        if (!response.ok) {
          throw new Error(payload?.detail || payload?.message || "Verification failed")
        }

        if (cancelled) return
        setStatus("success")
        setMessage(payload?.message || "Email verified successfully")
        redirectHandle = window.setTimeout(() => {
          void router.push("/login?verified=1")
        }, 1200)
      } catch (error) {
        if (cancelled) return
        setStatus("error")
        setMessage(
          error instanceof Error ? error.message : "Verification failed"
        )
      }
    }

    void verify()

    return () => {
      cancelled = true
      if (redirectHandle) {
        window.clearTimeout(redirectHandle)
      }
    }
  }, [router])

  return (
    <div className="space-y-4">
      <h2 className="text-3xl font-semibold text-text">Verify email</h2>
      <p
        role={status === "error" ? "alert" : "status"}
        className="rounded-2xl border border-border/70 bg-surface/60 px-4 py-4 text-sm leading-6 text-text-muted"
      >
        {message}
      </p>
    </div>
  )
}
