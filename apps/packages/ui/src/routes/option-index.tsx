import React from "react"
import { Moon, Sun } from "lucide-react"

import {
  useConnectionActions,
  useConnectionState,
  useConnectionUxState
} from "@/hooks/useConnectionState"
import { ConnectionPhase } from "@/types/connection"
import { useFocusComposerOnConnect } from "@/hooks/useComposerFocus"
import { useDarkMode } from "@/hooks/useDarkmode"
import { OnboardingWizard } from "@/components/Option/Onboarding/OnboardingWizard"
import OptionLayout from "~/components/Layouts/Layout"
import { LandingHub } from "~/components/Option/LandingHub"
import { isHostedTldwDeployment } from "@/services/tldw/deployment-mode"

const OptionIndex = () => {
  const hostedMode = isHostedTldwDeployment()
  const { phase } = useConnectionState()
  const { hasCompletedFirstRun } = useConnectionUxState()
  const { checkOnce, beginOnboarding, markFirstRunComplete } = useConnectionActions()
  const { mode, toggleDarkMode } = useDarkMode()
  const onboardingInitiated = React.useRef(false)
  const [didHydrate, setDidHydrate] = React.useState(false)

  React.useEffect(() => {
    if (hostedMode) {
      setDidHydrate(true)
      return
    }
    let cancelled = false
    const run = async () => {
      try {
        await checkOnce()
      } finally {
        if (!cancelled) setDidHydrate(true)
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [checkOnce, hostedMode])

  React.useEffect(() => {
    if (hostedMode) return
    if (hasCompletedFirstRun) {
      void checkOnce()
    }
  }, [checkOnce, hasCompletedFirstRun, hostedMode])

  React.useEffect(() => {
    if (hostedMode) return
    if (!didHydrate) return
    if (hasCompletedFirstRun) return
    if (onboardingInitiated.current) return
    if (phase !== ConnectionPhase.UNCONFIGURED) return

    onboardingInitiated.current = true
    void beginOnboarding()
  }, [beginOnboarding, didHydrate, hasCompletedFirstRun, hostedMode, phase])

  useFocusComposerOnConnect(phase ?? null)

  if (hostedMode) {
    return (
      <OptionLayout hideHeader hideSidebar>
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-10">
          <section className="overflow-hidden rounded-[2rem] border border-border/70 bg-[radial-gradient(circle_at_top_right,_rgba(217,119,6,0.16),_transparent_24%),linear-gradient(180deg,_rgba(255,255,255,0.88),_rgba(255,255,255,0.94))] p-8 shadow-[0_24px_70px_rgba(15,23,42,0.08)]">
            <div className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
              <div className="space-y-5">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
                  Hosted tldw
                </p>
                <h1 className="max-w-3xl font-serif text-5xl leading-tight text-text">
                  Start with the narrow hosted path, keep self-host when you need full control.
                </h1>
                <p className="max-w-2xl text-base leading-7 text-text-muted">
                  The hosted launch is intentionally focused on signup, ingest, chat, and retrieval for solo customers. The broader experimental surface still belongs to self-host.
                </p>

                <div className="flex flex-wrap gap-3">
                  <a
                    href="/signup"
                    className="inline-flex items-center rounded-md bg-primary px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-primaryStrong"
                  >
                    Start trial
                  </a>
                  <a
                    href="/login"
                    className="inline-flex items-center rounded-md border border-border px-5 py-3 text-sm font-medium text-text transition-colors hover:bg-surface2"
                  >
                    Sign in
                  </a>
                  <a
                    href="/docs/self-hosting"
                    className="inline-flex items-center rounded-md border border-border px-5 py-3 text-sm font-medium text-text transition-colors hover:bg-surface2"
                  >
                    View self-host docs
                  </a>
                </div>
              </div>

              <div className="grid gap-4">
                {[
                  {
                    title: "Core product only",
                    description: "Hosted mode trims the surface down to media ingest, chat, search, and account/billing flows."
                  },
                  {
                    title: "Admin stays internal",
                    description: "Server setup, runtime configuration, and operator tooling remain out of the customer-facing app."
                  },
                  {
                    title: "Segment-specific entry points",
                    description: "Journalists, researchers, and OSINT users can branch into narrower hosted messaging without pretending every workflow is live."
                  }
                ].map((card) => (
                  <div
                    key={card.title}
                    className="rounded-[1.5rem] border border-border/70 bg-bg/90 p-5 shadow-sm"
                  >
                    <h2 className="text-lg font-semibold text-text">{card.title}</h2>
                    <p className="mt-2 text-sm leading-6 text-text-muted">
                      {card.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-3">
            {[
              {
                href: "/for/journalists",
                title: "For journalists",
                description: "Hosted messaging for solo investigative workflows, with self-host still positioned for sensitive source handling."
              },
              {
                href: "/for/researchers",
                title: "For researchers",
                description: "A cleaner narrative for qualitative research teams that want hosted convenience before labs and teams arrive."
              },
              {
                href: "/for/osint",
                title: "For OSINT",
                description: "Honest positioning for hosted evaluation while keeping air-gapped and operationally sensitive work on self-host."
              }
            ].map((card) => (
              <a
                key={card.href}
                href={card.href}
                className="rounded-[1.5rem] border border-border/70 bg-bg/95 p-5 shadow-sm transition-colors hover:border-primary/40 hover:bg-primary/5"
              >
                <h2 className="text-lg font-semibold text-text">{card.title}</h2>
                <p className="mt-2 text-sm leading-6 text-text-muted">
                  {card.description}
                </p>
              </a>
            ))}
          </section>
        </div>
      </OptionLayout>
    )
  }

  // During first-time setup, hide the connection shell entirely and show only
  // the onboarding wizard (“Welcome — Let’s get you connected”).
  if (!hasCompletedFirstRun) {
    const themeToggleLabel =
      mode === "dark" ? "Switch to light theme" : "Switch to dark theme"
    return (
      <OptionLayout hideHeader hideSidebar>
        <div className="mx-auto mb-4 w-full max-w-3xl rounded-lg border border-border bg-surface px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h1 className="text-base font-semibold text-text">Home Onboarding</h1>
              <p className="mt-1 text-xs text-text-muted">
                Start here to connect your server or try local demo mode.
              </p>
            </div>
            <button
              type="button"
              onClick={toggleDarkMode}
              aria-label={themeToggleLabel}
              title={themeToggleLabel}
              data-testid="chat-header-theme-toggle"
              className="inline-flex items-center justify-center rounded-md border border-border bg-surface px-2 py-2 text-text-muted transition-colors hover:bg-surface2 hover:text-text"
            >
              {mode === "dark" ? (
                <Sun className="size-4" aria-hidden="true" />
              ) : (
                <Moon className="size-4" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>
        <OnboardingWizard
          onFinish={async () => {
            try {
              await markFirstRunComplete()
            } catch {
              // ignore markFirstRunComplete failures here; connection state will self-heal on next load
            }
            void checkOnce().catch(() => undefined)
          }}
        />
      </OptionLayout>
    )
  }

  return (
    <OptionLayout>
      <LandingHub />
    </OptionLayout>
  )
}

export default OptionIndex
