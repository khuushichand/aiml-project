import dynamic from "next/dynamic"

export default dynamic(async () => {
  const { SettingsRoute } = await import("@/routes/settings-route")
  const mod = await import("@/components/Option/Models")
  const Component = mod.ModelsBody
  const Page = () => (
    <SettingsRoute>
      <Component />
    </SettingsRoute>
  )
  return { default: Page }
}, { ssr: false })
