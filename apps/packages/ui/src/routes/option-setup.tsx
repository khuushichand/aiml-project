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
    <OptionLayout hideHeader>
      <OnboardingWizard onFinish={handleFinish} />
    </OptionLayout>
  )
}

export default OptionSetup
