import React from "react"
import { useTranslation } from "react-i18next"
import { Popover, Segmented, Tooltip } from "antd"
import { Settings, Sun, Moon, BookOpen, List, FileText } from "lucide-react"
import { useEpubSettings, THEME_INFO, SCROLL_MODE_INFO } from "@/hooks/document-workspace/useEpubSettings"
import type { EpubTheme, EpubScrollMode } from "../../types"

interface EpubSettingsPanelProps {
  onScrollModeChange?: (mode: EpubScrollMode) => void
}

/**
 * Settings popover for EPUB reader customization.
 *
 * Features:
 * - Theme selection (Light, Dark, Sepia)
 * - Scroll mode toggle (Paginated, Continuous)
 * - Visual previews for themes
 */
export const EpubSettingsPanel: React.FC<EpubSettingsPanelProps> = ({
  onScrollModeChange
}) => {
  const { t } = useTranslation(["option", "common"])
  const { theme, scrollMode, setTheme, setScrollMode } = useEpubSettings()

  const handleThemeChange = (value: string | number) => {
    setTheme(value as EpubTheme)
  }

  const handleScrollModeChange = (value: string | number) => {
    const newMode = value as EpubScrollMode
    setScrollMode(newMode)
    onScrollModeChange?.(newMode)
  }

  const themeIcon = (themeName: EpubTheme) => {
    switch (themeName) {
      case "light":
        return <Sun className="h-4 w-4" />
      case "dark":
        return <Moon className="h-4 w-4" />
      case "sepia":
        return <BookOpen className="h-4 w-4" />
    }
  }

  const content = (
    <div className="w-64 space-y-4">
      {/* Theme Selection */}
      <div>
        <div className="mb-2 text-xs font-medium text-text-secondary">
          {t("option:documentWorkspace.theme", "Theme")}
        </div>
        <Segmented
          value={theme}
          onChange={handleThemeChange}
          block
          options={Object.entries(THEME_INFO).map(([key, info]) => ({
            value: key,
            label: (
              <div className="flex items-center justify-center gap-1.5 py-0.5">
                {themeIcon(key as EpubTheme)}
                <span>{t(`option:documentWorkspace.theme${info.label}`, info.label)}</span>
              </div>
            )
          }))}
        />
        {/* Theme Preview */}
        <div className="mt-2 flex gap-2">
          {Object.entries(THEME_INFO).map(([key, info]) => (
            <button
              key={key}
              onClick={() => setTheme(key as EpubTheme)}
              className={`flex-1 rounded-md border-2 p-2 transition-colors ${
                theme === key
                  ? "border-primary"
                  : "border-transparent hover:border-border"
              }`}
              style={{ backgroundColor: info.preview.bg }}
            >
              <div
                className="text-[10px] font-medium leading-tight"
                style={{ color: info.preview.text }}
              >
                Aa
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Scroll Mode */}
      <div>
        <div className="mb-2 text-xs font-medium text-text-secondary">
          {t("option:documentWorkspace.scrollMode", "Scroll Mode")}
        </div>
        <Segmented
          value={scrollMode}
          onChange={handleScrollModeChange}
          block
          options={[
            {
              value: "paginated",
              label: (
                <div className="flex items-center justify-center gap-1.5 py-0.5">
                  <FileText className="h-4 w-4" />
                  <span>{t("option:documentWorkspace.paginated", "Paginated")}</span>
                </div>
              )
            },
            {
              value: "continuous",
              label: (
                <div className="flex items-center justify-center gap-1.5 py-0.5">
                  <List className="h-4 w-4" />
                  <span>{t("option:documentWorkspace.continuousScroll", "Continuous")}</span>
                </div>
              )
            }
          ]}
        />
        <p className="mt-1.5 text-[11px] text-text-muted">
          {scrollMode === "paginated"
            ? t("option:documentWorkspace.paginatedDescription", "Navigate page by page with arrow keys")
            : t("option:documentWorkspace.continuousDescription", "Scroll through content freely")}
        </p>
      </div>
    </div>
  )

  return (
    <Popover
      content={content}
      title={t("option:documentWorkspace.readerSettings", "Reader Settings")}
      trigger="click"
      placement="bottomRight"
    >
      <Tooltip title={t("option:documentWorkspace.readerSettings", "Reader Settings")}>
        <button
          className="rounded p-1.5 hover:bg-hover"
          aria-label={t("option:documentWorkspace.readerSettings", "Reader Settings")}
        >
          <Settings className="h-4 w-4" />
        </button>
      </Tooltip>
    </Popover>
  )
}

export default EpubSettingsPanel
