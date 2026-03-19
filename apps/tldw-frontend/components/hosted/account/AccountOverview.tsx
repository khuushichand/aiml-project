import React from "react"
import Link from "next/link"
import { CheckCircle2, HardDrive, ShieldCheck, UserCircle2 } from "lucide-react"

import type { AccountProfileResponse } from "@web/lib/api/account"

const formatStorage = (valueMb?: number | null): string => {
  if (typeof valueMb !== "number" || !Number.isFinite(valueMb) || valueMb <= 0) {
    return "0 GB"
  }

  const valueGb = valueMb / 1024
  const rounded = Number.isInteger(valueGb) ? valueGb.toFixed(0) : valueGb.toFixed(1)
  return `${rounded} GB`
}

const formatDate = (value?: string | null): string => {
  if (!value) return "Not available"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Not available"
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric"
  })
}

type AccountOverviewProps = {
  profile: AccountProfileResponse
}

export function AccountOverview({ profile }: AccountOverviewProps) {
  const user = profile.user ?? {}
  const quotas = profile.quotas ?? {}
  const memberships = Array.isArray(profile.memberships) ? profile.memberships : []
  const primaryMembership =
    memberships.find((membership) => membership?.is_default) ?? memberships[0]
  const storageQuota =
    typeof quotas.storage_quota_mb === "number"
      ? quotas.storage_quota_mb
      : user.storage_quota_mb
  const storageUsed =
    typeof quotas.storage_used_mb === "number"
      ? quotas.storage_used_mb
      : user.storage_used_mb

  const sections = [
    {
      title: "Identity",
      icon: UserCircle2,
      items: [
        { label: "Username", value: user.username || "Not available" },
        { label: "Email", value: user.email || "Not available" },
        { label: "Role", value: user.role || "user" }
      ]
    },
    {
      title: "Security",
      icon: ShieldCheck,
      items: [
        {
          label: "Email verification",
          value:
            profile.security?.verified ?? user.is_verified ? "Verified" : "Pending"
        },
        {
          label: "MFA",
          value: profile.security?.mfa_enabled ? "Enabled" : "Not enabled"
        },
        {
          label: "Last sign in",
          value: formatDate(user.last_login)
        }
      ]
    },
    {
      title: "Workspace",
      icon: CheckCircle2,
      items: [
        {
          label: "Default workspace",
          value: primaryMembership?.org_name || "Personal workspace"
        },
        {
          label: "Membership role",
          value: primaryMembership?.role || "owner"
        },
        {
          label: "Account status",
          value: user.is_active === false ? "Inactive" : "Active"
        }
      ]
    }
  ] as const

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <section className="overflow-hidden rounded-[2rem] border border-border/70 bg-[radial-gradient(circle_at_top_right,_rgba(217,119,6,0.16),_transparent_26%),linear-gradient(180deg,_rgba(255,255,255,0.88),_rgba(255,255,255,0.94))] p-6 shadow-[0_24px_70px_rgba(15,23,42,0.08)]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
              Account
            </p>
            <h1 className="font-serif text-4xl text-text">Your hosted account</h1>
            <p className="max-w-2xl text-sm leading-6 text-text-muted">
              Review your identity, workspace ownership, and quota posture without dropping into
              internal admin tooling.
            </p>
          </div>

          <div className="space-y-3">
            <div className="rounded-3xl border border-border/70 bg-bg/90 p-5 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="rounded-2xl bg-primary/10 p-3 text-primary">
                  <HardDrive className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm text-text-muted">Storage usage</p>
                  <p className="text-2xl font-semibold text-text">
                    {formatStorage(storageUsed)} / {formatStorage(storageQuota)}
                  </p>
                </div>
              </div>
            </div>

            <Link
              href="/billing"
              className="inline-flex items-center rounded-md border border-border px-4 py-2 text-sm font-medium text-text transition-colors hover:bg-surface2"
            >
              Open billing
            </Link>
          </div>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        {sections.map((section) => {
          const Icon = section.icon
          return (
            <section
              key={section.title}
              className="rounded-[1.75rem] border border-border/70 bg-bg/95 p-5 shadow-sm"
            >
              <div className="mb-4 flex items-center gap-3">
                <div className="rounded-2xl bg-primary/10 p-3 text-primary">
                  <Icon className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-text">{section.title}</h2>
                </div>
              </div>

              <dl className="space-y-4">
                {section.items.map((item) => (
                  <div
                    key={`${section.title}-${item.label}`}
                    className="rounded-2xl border border-border/60 bg-surface/60 px-4 py-3"
                  >
                    <dt className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                      {item.label}
                    </dt>
                    <dd className="mt-1 text-sm font-medium text-text">{item.value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )
        })}
      </div>
    </div>
  )
}
