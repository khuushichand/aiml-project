import React from "react"
import Link from "next/link"
import { useRouter } from "next/router"

import { Button } from "@web/components/ui/Button"
import { Input } from "@web/components/ui/Input"
import { tldwAuth } from "@/services/tldw/TldwAuth"

const readErrorMessage = async (response: Response): Promise<string> => {
  const payload = await response.json().catch(() => null) as
    | { detail?: string; message?: string }
    | null
  return payload?.detail || payload?.message || "Request failed"
}

export function LoginForm() {
  const router = useRouter()
  const [identifier, setIdentifier] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [email, setEmail] = React.useState("")
  const [error, setError] = React.useState<string | null>(null)
  const [status, setStatus] = React.useState<string | null>(null)
  const [loginLoading, setLoginLoading] = React.useState(false)
  const [magicLinkLoading, setMagicLinkLoading] = React.useState(false)
  const [resetLoading, setResetLoading] = React.useState(false)

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setStatus(null)
    setLoginLoading(true)

    try {
      await tldwAuth.login({
        username: identifier.trim(),
        password
      })
      setStatus("Signed in successfully. Redirecting you to the workspace...")
      void router.push("/chat")
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unable to sign in right now."
      )
    } finally {
      setLoginLoading(false)
    }
  }

  const submitEmailAction = async (
    endpoint: string,
    successMessage: string,
    setLoading: (value: boolean) => void
  ) => {
    setError(null)
    setStatus(null)
    setLoading(true)

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ email: email.trim() })
      })

      if (!response.ok) {
        throw new Error(await readErrorMessage(response))
      }

      setStatus(successMessage)
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unable to send email right now."
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold text-text">Use your password</h2>
        <p className="text-sm leading-6 text-text-muted">
          Use your password or request a magic link. Hosted mode keeps auth on the server side and drops you into the core product surface.
        </p>
      </div>

      <form className="space-y-4" onSubmit={onSubmit}>
        <Input
          id="login-identifier"
          label="Account identifier"
          value={identifier}
          onChange={(event) => setIdentifier(event.target.value)}
          autoComplete="username"
          placeholder="you@example.com"
          required
        />
        <Input
          id="login-password"
          label="Password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          placeholder="Enter your password"
          required
        />
        <Button className="w-full" type="submit" loading={loginLoading}>
          Sign in
        </Button>
      </form>

      <div className="relative py-1">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-border" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-bg px-3 text-xs font-semibold uppercase tracking-[0.2em] text-text-muted">
            Or use email
          </span>
        </div>
      </div>

      <div className="space-y-4 rounded-2xl border border-border/70 bg-surface/60 p-4">
        <Input
          id="login-email"
          label="Email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="email"
          placeholder="user@example.com"
          required
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <Button
            type="button"
            variant="secondary"
            loading={magicLinkLoading}
            onClick={() =>
              void submitEmailAction(
                "/api/auth/magic-link/request",
                "Sign-in link sent. Check your inbox for the hosted magic link.",
                setMagicLinkLoading
              )
            }
          >
            Email me a sign-in link
          </Button>
          <Button
            type="button"
            variant="ghost"
            loading={resetLoading}
            onClick={() =>
              void submitEmailAction(
                "/api/auth/forgot-password",
                "Password reset link sent. Check your inbox for next steps.",
                setResetLoading
              )
            }
          >
            Email me a reset link
          </Button>
        </div>
      </div>

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

      <p className="text-sm text-text-muted">
        Need an account?{" "}
        <Link href="/signup" className="font-semibold text-primary hover:underline">
          Create one here.
        </Link>
      </p>
    </div>
  )
}
