import React from "react"
import { useTranslation } from "react-i18next"
import { Popover, Segmented, Select, Slider, Tooltip } from "antd"
import { Settings, Sun, Moon, BookOpen, List, FileText, Columns2, Minus, Plus } from "lucide-react"
import {
  useEpubSettings,
  THEME_INFO,
  SCROLL_MODE_INFO,
  SPREAD_MODE_INFO,
  FONT_FAMILY_INFO
} from "@/hooks/document-workspace/useEpubSettings"
import type { EpubTheme, EpubScrollMode, EpubSpreadMode, EpubFontFamily } from "../../types"

interface EpubSettingsPanelProps {
  onScrollModeChange?: (mode: EpubScrollMode) => void
}

/**
 * Settings popover for EPUB reader customization.
 *
 * Features:
 * - Theme selection (Light, Dark, Sepia)
 * - Scroll mode toggle (Paginated, Continuous)
 * - Spread mode (Single, Auto, Two-Page)
 * - Font size, font family, line height controls
 * - Visual previews for themes
 */
export const EpubSettingsPanel: React.FC<EpubSettingsPanelProps> = ({
  onScrollModeChange
}) => {
  const { t } = useTranslation(["option", "common"])
  const {
    theme, scrollMode, spreadMode,
    fontSize, fontFamily, lineHeight,
    setTheme, setScrollMode, setSpreadMode,
    setFontSize, setFontFamily, setLineHeight
  } = useEpubSettings()

  const handleThemeChange = (value: string | number) => {
    setTheme(value as EpubTheme)
  }

  const handleScrollModeChange = (value: string | number) => {
    const newMode = value as EpubScrollMode
    setScrollMode(newMode)
    onScrollModeChange?.(newMode)
  }

  const handleSpreadModeChange = (value: string | number) => {
    setSpreadMode(value as EpubSpreadMode)
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
    <div className="w-72 space-y-4">
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

      {/* Font Size */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-medium text-text-secondary">
            {t("option:documentWorkspace.fontSize", "Font Size")}
          </span>
          <span className="text-xs text-text-muted">{fontSize}%</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-label="Decrease font size"
            onClick={() => setFontSize(fontSize - 10)}
            disabled={fontSize <= 50}
            className="flex h-7 w-7 items-center justify-center rounded hover:bg-hover disabled:opacity-50"
          >
            <Minus className="h-3.5 w-3.5" />
          </button>
          <Slider
            className="flex-1"
            min={50}
            max={200}
            step={10}
            value={fontSize}
            onChange={setFontSize}
            tooltip={{ formatter: (v) => `${v}%` }}
          />
          <button
            type="button"
            aria-label="Increase font size"
            onClick={() => setFontSize(fontSize + 10)}
            disabled={fontSize >= 200}
            className="flex h-7 w-7 items-center justify-center rounded hover:bg-hover disabled:opacity-50"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Font Family */}
      <div>
        <div className="mb-1.5 text-xs font-medium text-text-secondary">
          {t("option:documentWorkspace.fontFamily", "Font")}
        </div>
        <Select
          value={fontFamily}
          onChange={(value) => setFontFamily(value as EpubFontFamily)}
          className="w-full"
          size="small"
          options={Object.entries(FONT_FAMILY_INFO).map(([key, info]) => ({
            value: key,
            label: info.label
          }))}
        />
      </div>

      {/* Line Height */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-medium text-text-secondary">
            {t("option:documentWorkspace.lineHeight", "Line Spacing")}
          </span>
          <span className="text-xs text-text-muted">{lineHeight.toFixed(1)}</span>
        </div>
        <Slider
          min={1.0}
          max={2.5}
          step={0.1}
          value={lineHeight}
          onChange={setLineHeight}
          marks={{ 1.0: "1.0", 1.6: "1.6", 2.5: "2.5" }}
          tooltip={{ formatter: (v) => `${v}` }}
        />
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

      {/* Spread Mode (only in paginated mode) */}
      {scrollMode === "paginated" && (
        <div>
          <div className="mb-2 text-xs font-medium text-text-secondary">
            {t("option:documentWorkspace.spreadMode", "Page Spread")}
          </div>
          <Segmented
            value={spreadMode}
            onChange={handleSpreadModeChange}
            block
            options={Object.entries(SPREAD_MODE_INFO).map(([key, info]) => ({
              value: key,
              label: (
                <div className="flex items-center justify-center gap-1.5 py-0.5">
                  {key === "always" ? <Columns2 className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
                  <span>{t(`option:documentWorkspace.spread${info.label}`, info.label)}</span>
                </div>
              )
            }))}
          />
          <p className="mt-1.5 text-[11px] text-text-muted">
            {SPREAD_MODE_INFO[spreadMode].description}
          </p>
        </div>
      )}
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
