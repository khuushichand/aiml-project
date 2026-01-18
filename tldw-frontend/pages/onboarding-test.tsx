import dynamic from "next/dynamic"

export default dynamic(async () => {
  const { default: OptionLayout } = await import("@/components/Layouts/Layout")
  const { OnboardingWizard } = await import("@/components/Option/Onboarding/OnboardingWizard")
  const Page = () => (
    <OptionLayout hideHeader>
      <OnboardingWizard />
    </OptionLayout>
  )
  return { default: Page }
}, { ssr: false })
