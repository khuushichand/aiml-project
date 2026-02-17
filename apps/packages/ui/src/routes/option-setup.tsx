import React from "react"
import { useNavigate } from "react-router-dom"
import OptionLayout from "~/components/Layouts/Layout"
import { OnboardingWizard } from "@/components/Option/Onboarding/OnboardingWizard"

const OptionSetup = () => {
  const navigate = useNavigate()

  const handleFinish = React.useCallback(() => {
    navigate("/")
  }, [navigate])

  return (
    <OptionLayout hideHeader hideSidebar>
      <div className="mx-auto mb-4 w-full max-w-3xl rounded-lg border border-border bg-surface px-4 py-3">
        <h1 className="text-base font-semibold text-text">Setup Wizard</h1>
        <p className="mt-1 text-xs text-text-muted">
          Guided connection setup for production use.
        </p>
      </div>
      <OnboardingWizard onFinish={handleFinish} />
    </OptionLayout>
  )
}

export default OptionSetup
