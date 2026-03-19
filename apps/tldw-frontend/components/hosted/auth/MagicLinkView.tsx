import React from "react"
import { useRouter } from "next/router"

import { tldwAuth } from "@/services/tldw/TldwAuth"

const getTokenFromQuery = (value: string | string[] | undefined): string =>
  Array.isArray(value) ? value[0] || "" : value || ""

export function MagicLinkView() {
  const router = useRouter()
  const [status, setStatus] = React.useState<"pending" | "success" | "error">("pending")
  const [message, setMessage] = React.useState("Verifying your sign-in link...")

  React.useEffect(() => {
    const token = getTokenFromQuery(router.query.token)
    if (!token) {
      setStatus("error")
      setMessage("This sign-in link is incomplete.")
      return
    }

    let cancelled = false
    let redirectHandle: number | undefined

    const verify = async () => {
      try {
        await tldwAuth.verifyMagicLink(token)
        if (cancelled) return
        setStatus("success")
        setMessage("Signed in successfully. Redirecting you to chat...")
        redirectHandle = window.setTimeout(() => {
          void router.push("/chat")
        }, 1200)
      } catch (error) {
        if (cancelled) return
        setStatus("error")
        setMessage(
          error instanceof Error
            ? error.message
            : "Unable to verify this sign-in link."
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
      <h2 className="text-3xl font-semibold text-text">Finish sign-in</h2>
      <p
        role={status === "error" ? "alert" : "status"}
        className="rounded-2xl border border-border/70 bg-surface/60 px-4 py-4 text-sm leading-6 text-text-muted"
      >
        {message}
      </p>
    </div>
  )
}
