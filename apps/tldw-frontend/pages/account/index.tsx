import React from "react"

import { AccountOverview } from "@web/components/hosted/account/AccountOverview"
import {
  fetchCurrentUserProfile,
  type AccountProfileResponse
} from "@web/lib/api/account"

export default function AccountPage() {
  const [profile, setProfile] = React.useState<AccountProfileResponse | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let cancelled = false

    const loadProfile = async () => {
      setLoading(true)
      setError(null)

      try {
        const payload = await fetchCurrentUserProfile()
        if (!cancelled) {
          setProfile(payload)
        }
      } catch (caughtError) {
        if (!cancelled) {
          setError(
            caughtError instanceof Error
              ? caughtError.message
              : "Unable to load your account right now."
          )
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadProfile()

    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="rounded-[1.75rem] border border-border/70 bg-bg/95 p-6 text-sm text-text-muted shadow-sm">
          Loading account details...
        </div>
      </div>
    )
  }

  if (error || !profile) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="rounded-[1.75rem] border border-danger/30 bg-danger/5 p-6 text-sm text-text">
          {error || "Unable to load your account right now."}
        </div>
      </div>
    )
  }

  return <AccountOverview profile={profile} />
}
