import React from "react"
import Link from "next/link"

import { Button } from "@web/components/ui/Button"
import { Input } from "@web/components/ui/Input"

const readErrorMessage = async (response: Response): Promise<string> => {
  const payload = await response.json().catch(() => null) as
    | { detail?: string; message?: string }
    | null
  return payload?.detail || payload?.message || "Unable to create your account."
}

export function SignupForm() {
  const [username, setUsername] = React.useState("")
  const [email, setEmail] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [registrationCode, setRegistrationCode] = React.useState("")
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [status, setStatus] = React.useState<string | null>(null)

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setStatus(null)
    setLoading(true)

    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          username: username.trim(),
          email: email.trim(),
          password,
          registration_code: registrationCode.trim() || undefined
        })
      })

      if (!response.ok) {
        throw new Error(await readErrorMessage(response))
      }

      const payload = await response.json().catch(() => null) as
        | { requires_verification?: boolean }
        | null
      setStatus(
        payload?.requires_verification
          ? "Check your email to verify your account before signing in."
          : "Account created successfully. You can sign in right away."
      )
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unable to create your account."
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-3xl font-semibold text-text">Create account</h2>
        <p className="text-sm leading-6 text-text-muted">
          Start with the narrow hosted product surface now. Team and B2B controls can layer in later without changing this first-run path.
        </p>
      </div>

      <form className="space-y-4" onSubmit={onSubmit}>
        <Input
          id="signup-username"
          label="Username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
          placeholder="new-user"
          required
        />
        <Input
          id="signup-email"
          label="Email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="email"
          placeholder="you@example.com"
          required
        />
        <Input
          id="signup-password"
          label="Password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="new-password"
          placeholder="At least 10 characters"
          required
        />
        <Input
          id="signup-code"
          label="Registration code"
          value={registrationCode}
          onChange={(event) => setRegistrationCode(event.target.value)}
          placeholder="Optional for beta cohorts"
        />
        <Button className="w-full" type="submit" loading={loading}>
          Create account
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

      <p className="text-sm text-text-muted">
        Already have an account?{" "}
        <Link href="/login" className="font-semibold text-primary hover:underline">
          Sign in.
        </Link>
      </p>
    </div>
  )
}
