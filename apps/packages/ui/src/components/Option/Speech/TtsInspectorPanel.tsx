import React from "react"
import { Button, Drawer, Segmented } from "antd"
import { X } from "lucide-react"
import { useTranslation } from "react-i18next"

type InspectorTab = "voice" | "output" | "advanced"

type Props = {
  open: boolean
  activeTab: InspectorTab
  onTabChange: (tab: InspectorTab) => void
  onClose: () => void
  voiceTab: React.ReactNode
  outputTab: React.ReactNode
  advancedTab: React.ReactNode
  useDrawer?: boolean
}

const TAB_OPTIONS: { label: string; value: InspectorTab }[] = [
  { label: "Voice", value: "voice" },
  { label: "Output", value: "output" },
  { label: "Advanced", value: "advanced" }
]

const PanelContent: React.FC<{
  activeTab: InspectorTab
  onTabChange: (tab: InspectorTab) => void
  onClose: () => void
  voiceTab: React.ReactNode
  outputTab: React.ReactNode
  advancedTab: React.ReactNode
}> = ({ activeTab, onTabChange, onClose, voiceTab, outputTab, advancedTab }) => {
  const { t } = useTranslation("playground")

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <span className="text-sm font-medium text-text">
          {t("tts.configuration", "Configuration")}
        </span>
        <Button
          type="text"
          size="small"
          icon={<X className="h-4 w-4" />}
          onClick={onClose}
          aria-label="Close configuration panel"
        />
      </div>
      <div className="px-4 py-3 border-b border-border">
        <Segmented
          block
          size="small"
          value={activeTab}
          onChange={(value) => onTabChange(value as InspectorTab)}
          options={TAB_OPTIONS}
        />
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {activeTab === "voice" && voiceTab}
        {activeTab === "output" && outputTab}
        {activeTab === "advanced" && advancedTab}
      </div>
    </div>
  )
}

export const TtsInspectorPanel: React.FC<Props> = ({
  open,
  activeTab,
  onTabChange,
  onClose,
  voiceTab,
  outputTab,
  advancedTab,
  useDrawer = false
}) => {
  if (useDrawer) {
    return (
      <Drawer
        placement="right"
        open={open}
        onClose={onClose}
        closable={false}
        styles={{ body: { padding: 0 }, wrapper: { maxWidth: 360 } }}
        width={360}
      >
        <PanelContent
          activeTab={activeTab}
          onTabChange={onTabChange}
          onClose={onClose}
          voiceTab={voiceTab}
          outputTab={outputTab}
          advancedTab={advancedTab}
        />
      </Drawer>
    )
  }

  if (!open) return null

  return (
    <aside
      role="complementary"
      aria-label="TTS Configuration"
      className="w-[320px] min-w-[300px] max-w-[360px] border-l border-border bg-surface"
    >
      <PanelContent
        activeTab={activeTab}
        onTabChange={onTabChange}
        onClose={onClose}
        voiceTab={voiceTab}
        outputTab={outputTab}
        advancedTab={advancedTab}
      />
    </aside>
  )
}
