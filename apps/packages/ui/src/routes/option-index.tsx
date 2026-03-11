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

const OptionIndex = () => {
  const { phase } = useConnectionState()
  const { hasCompletedFirstRun } = useConnectionUxState()
  const { checkOnce, beginOnboarding, markFirstRunComplete } = useConnectionActions()
  const { mode, toggleDarkMode } = useDarkMode()
  const onboardingInitiated = React.useRef(false)
  const [didHydrate, setDidHydrate] = React.useState(false)

  React.useEffect(() => {
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
  }, [checkOnce])

  React.useEffect(() => {
    if (hasCompletedFirstRun) {
      void checkOnce()
    }
  }, [checkOnce, hasCompletedFirstRun])

  React.useEffect(() => {
    if (!didHydrate) return
    if (hasCompletedFirstRun) return
    if (onboardingInitiated.current) return
    if (phase !== ConnectionPhase.UNCONFIGURED) return

    onboardingInitiated.current = true
    void beginOnboarding()
  }, [beginOnboarding, didHydrate, hasCompletedFirstRun, phase])

  useFocusComposerOnConnect(phase ?? null)

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
