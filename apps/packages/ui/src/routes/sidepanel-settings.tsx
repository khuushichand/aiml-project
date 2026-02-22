import { SettingsBody } from "~/components/Sidepanel/Settings/body"
import { SidepanelSettingsHeader } from "~/components/Sidepanel/Settings/header"

const SidepanelSettings = () => {
  return (
    <div className="flex bg-bg flex-col min-h-screen mx-auto max-w-7xl">
      <div className="sticky bg-surface top-0 z-10">
        <SidepanelSettingsHeader />
      </div>
      <SettingsBody />
    </div>
  )
}

export default SidepanelSettings
