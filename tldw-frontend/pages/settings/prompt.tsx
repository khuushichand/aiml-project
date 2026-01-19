import dynamic from "next/dynamic"

export default dynamic(async () => {
  const { SettingsRoute } = await import("@/routes/settings-route")
  const mod = await import("@/components/Option/Settings/WorkspaceLinks")
  const Component = mod.PromptWorkspaceSettings
  const Page = () => (
    <SettingsRoute>
      <Component />
    </SettingsRoute>
  )
  return { default: Page }
}, { ssr: false })
