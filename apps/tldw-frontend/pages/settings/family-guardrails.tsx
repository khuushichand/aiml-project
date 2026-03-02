import dynamic from "next/dynamic"

export default dynamic(async () => {
  const { SettingsRoute } = await import("@/routes/settings-route")
  const mod = await import("@/components/Option/Settings/FamilyGuardrailsWizard")
  const Component = mod.FamilyGuardrailsWizard
  const Page = () => (
    <SettingsRoute>
      <div style={{ maxWidth: 1120, margin: "0 auto", padding: "16px 0 32px" }}>
        <Component />
      </div>
    </SettingsRoute>
  )
  return { default: Page }
}, { ssr: false })
