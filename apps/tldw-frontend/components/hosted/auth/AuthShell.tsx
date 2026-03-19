import React from "react"
import Link from "next/link"
import { BrainCircuit, SearchCheck, ShieldCheck } from "lucide-react"

type AuthShellProps = {
  title: string
  description: string
  children: React.ReactNode
  eyebrow?: string
}

const valuePoints = [
  {
    title: "Bring your media in fast",
    description: "Upload, transcribe, and search the core product surface without wrestling self-host setup.",
    icon: SearchCheck
  },
  {
    title: "Keep the good parts opinionated",
    description: "Hosted mode narrows the sprawl into a cleaner customer path for chat, ingest, and retrieval.",
    icon: BrainCircuit
  },
  {
    title: "Session security stays server-side",
    description: "The browser never gets bearer tokens. Hosted auth runs through same-origin routes and httpOnly cookies.",
    icon: ShieldCheck
  }
] as const

export function AuthShell({
  title,
  description,
  children,
  eyebrow = "Hosted tldw"
}: AuthShellProps) {
  return (
    <div className="min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top,_rgba(217,119,6,0.12),_transparent_32%),linear-gradient(180deg,_rgba(15,23,42,0.02),_rgba(15,23,42,0))] text-text">
      <div className="mx-auto grid min-h-screen max-w-6xl gap-10 px-6 py-10 lg:grid-cols-[1.1fr_0.9fr] lg:px-10">
        <section className="relative flex flex-col justify-between rounded-[2rem] border border-border/70 bg-surface/80 p-8 shadow-[0_30px_80px_rgba(15,23,42,0.08)] backdrop-blur md:p-10">
          <div className="absolute inset-x-10 top-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent" />

          <div className="space-y-8">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-primary">
              {eyebrow}
            </div>

            <div className="space-y-4">
              <Link href="/" className="inline-flex items-center text-sm font-semibold text-primary">
                tldw
              </Link>
              <h1 className="max-w-xl font-serif text-4xl leading-tight text-text md:text-5xl">
                {title}
              </h1>
              <p className="max-w-2xl text-base leading-7 text-text-muted md:text-lg">
                {description}
              </p>
            </div>

            <div className="grid gap-4">
              {valuePoints.map((point) => {
                const Icon = point.icon
                return (
                  <div
                    key={point.title}
                    className="rounded-2xl border border-border/70 bg-bg/70 p-4 shadow-sm"
                  >
                    <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                      <Icon className="h-5 w-5" />
                    </div>
                    <h2 className="text-base font-semibold text-text">
                      {point.title}
                    </h2>
                    <p className="mt-2 text-sm leading-6 text-text-muted">
                      {point.description}
                    </p>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="mt-8 flex flex-wrap items-center gap-4 text-sm text-text-muted">
            <span>No credit card required for account creation.</span>
            <span className="hidden h-1 w-1 rounded-full bg-border-strong md:inline-block" />
            <span>Internal admin tooling stays separate from this customer surface.</span>
          </div>
        </section>

        <section className="flex items-center">
          <div className="w-full rounded-[2rem] border border-border/70 bg-bg/95 p-6 shadow-[0_25px_60px_rgba(15,23,42,0.08)] backdrop-blur md:p-8">
            {children}
          </div>
        </section>
      </div>
    </div>
  )
}
