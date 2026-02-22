import React from "react"
import { useNavigate } from "react-router-dom"
import OptionLayout from "~/components/Layouts/Layout"
import { OnboardingWizard } from "@/components/Option/Onboarding/OnboardingWizard"

const OptionOnboardingTest = () => {
  const navigate = useNavigate()

  return (
    <OptionLayout hideHeader hideSidebar>
      <div className="mx-auto mb-4 w-full max-w-3xl rounded-lg border border-border bg-surface px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-base font-semibold text-text">
              Onboarding Test Harness
            </h1>
            <p className="mt-1 text-xs text-text-muted">
              Preview and validate onboarding UX changes without altering home/setup flow.
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate("/setup")}
            className="rounded border border-border px-3 py-1.5 text-xs font-medium text-text hover:bg-surface2"
          >
            Go to setup
          </button>
        </div>
      </div>
      <OnboardingWizard />
    </OptionLayout>
  )
}

export default OptionOnboardingTest
