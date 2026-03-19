import React from "react"
import { useRouter } from "next/router"

import { Button } from "@web/components/ui/Button"
import { Input } from "@web/components/ui/Input"

const getTokenFromQuery = (value: string | string[] | undefined): string =>
  Array.isArray(value) ? value[0] || "" : value || ""

export function ResetPasswordView() {
  const router = useRouter()
  const token = getTokenFromQuery(router.query.token)
  const [password, setPassword] = React.useState("")
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [status, setStatus] = React.useState<string | null>(null)

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!token) {
      setError("This reset link is incomplete.")
      return
    }

    setError(null)
    setStatus(null)
    setLoading(true)

    try {
      const response = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          token,
          new_password: password
        })
      })

      const payload = await response.json().catch(() => null) as
        | { detail?: string; message?: string }
        | null

      if (!response.ok) {
        throw new Error(payload?.detail || payload?.message || "Reset failed")
      }

      setStatus(payload?.message || "Password has been reset successfully")
      void router.push("/login?reset=1")
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Reset failed"
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-3xl font-semibold text-text">Reset password</h2>
        <p className="text-sm leading-6 text-text-muted">
          Choose a new password and we’ll return you to hosted sign-in.
        </p>
      </div>

      <form className="space-y-4" onSubmit={onSubmit}>
        <Input
          id="reset-password"
          label="New password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="new-password"
          placeholder="Create a strong password"
          required
        />
        <Button className="w-full" type="submit" loading={loading}>
          Reset password
        </Button>
      </form>

      {status ? (
        <p role="status" className="rounded-2xl border border-primary/20 bg-primary/10 px-4 py-3 text-sm text-primary">
          {status}
        </p>
      ) : null}

      {error ? (
        <p role="alert" className="rounded-2xl border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}
        </p>
      ) : null}
    </div>
  )
}
