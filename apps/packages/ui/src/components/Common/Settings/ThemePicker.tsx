import React, { useState } from "react"
import { Segmented } from "antd"
import { Monitor, Moon, Sun, Pencil, Trash2, Plus } from "lucide-react"
import { useTheme } from "@/hooks/useTheme"
import { rgbTripleToHex } from "@/themes/antd-theme"
import type { ThemeDefinition } from "@/themes/types"
import type { ThemeValue } from "@/services/settings/ui-settings"
import { useTranslation } from "react-i18next"
import { ThemeEditorModal } from "./ThemeEditorModal"

const MODE_OPTIONS: { value: ThemeValue; icon: React.ReactNode; label: string }[] = [
  { value: "system", icon: <Monitor className="h-3.5 w-3.5" />, label: "System" },
  { value: "light", icon: <Sun className="h-3.5 w-3.5" />, label: "Light" },
  { value: "dark", icon: <Moon className="h-3.5 w-3.5" />, label: "Dark" },
]

const SWATCH_KEYS = ["bg", "primary", "accent", "surface", "text"] as const

function ThemeSwatch({
  theme,
  isActive,
  isDark,
  onClick,
  onEdit,
  onDelete,
}: {
  theme: ThemeDefinition
  isActive: boolean
  isDark: boolean
  onClick: () => void
  onEdit?: () => void
  onDelete?: () => void
}) {
  const palette = isDark ? theme.palette.dark : theme.palette.light

  return (
    <div className="relative group">
      <button
        type="button"
        onClick={onClick}
        className={[
          "flex flex-col items-center gap-1.5 rounded-lg border p-2.5 transition-colors",
          isActive
            ? "border-primary bg-surface2 ring-2 ring-primary/30"
            : "border-border bg-surface hover:border-primary/50",
        ].join(" ")}
        title={theme.description ?? theme.name}
      >
        <div className="flex gap-1">
          {SWATCH_KEYS.map((key) => (
            <div
              key={key}
              className="h-4 w-4 rounded-full border border-border"
              style={{ backgroundColor: rgbTripleToHex(palette[key]) }}
            />
          ))}
        </div>
        <span className="text-xs text-text-muted leading-none">{theme.name}</span>
      </button>
      {/* Edit/delete overlay for custom themes */}
      {(onEdit || onDelete) && (
        <div className="absolute -top-1.5 -right-1.5 hidden group-hover:flex gap-0.5">
          {onEdit && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onEdit() }}
              className="h-5 w-5 rounded-full bg-surface border border-border flex items-center justify-center shadow-sm hover:bg-surface2"
              title="Edit theme"
            >
              <Pencil className="h-2.5 w-2.5 text-text-muted" />
            </button>
          )}
          {onDelete && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onDelete() }}
              className="h-5 w-5 rounded-full bg-surface border border-border flex items-center justify-center shadow-sm hover:bg-danger/10"
              title="Delete theme"
            >
              <Trash2 className="h-2.5 w-2.5 text-danger" />
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export function ThemePicker() {
  const { t } = useTranslation("settings")
  const {
    mode,
    modePreference,
    setModePreference,
    themeId,
    setThemeId,
    presets,
    customThemes,
    saveCustomTheme,
    deleteCustomTheme,
  } = useTheme()
  const isDark = mode === "dark"

  const [editorOpen, setEditorOpen] = useState(false)
  const [editingTheme, setEditingTheme] = useState<ThemeDefinition | undefined>()

  const handleCreate = () => {
    setEditingTheme(undefined)
    setEditorOpen(true)
  }

  const handleEdit = (theme: ThemeDefinition) => {
    setEditingTheme(theme)
    setEditorOpen(true)
  }

  const handleSave = (theme: ThemeDefinition) => {
    saveCustomTheme(theme)
    setThemeId(theme.id)
  }

  const handleDelete = (id: string) => {
    deleteCustomTheme(id)
  }

  // Split presets into builtin and custom for separate rendering
  const builtinPresets = presets.filter((p) => p.builtin)
  const customPresets = presets.filter((p) => !p.builtin)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <span className="text-sm text-text">
          {t("generalSettings.settings.darkMode.label", "Appearance")}
        </span>
        <Segmented
          value={modePreference}
          onChange={(val) => setModePreference(val as ThemeValue)}
          options={MODE_OPTIONS.map((opt) => ({
            value: opt.value,
            label: (
              <div className="flex items-center gap-1.5 px-1">
                {opt.icon}
                <span>{t(`generalSettings.settings.darkMode.modes.${opt.value}`, opt.label)}</span>
              </div>
            ),
          }))}
        />
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-sm text-text">
          {t("generalSettings.settings.themePreset.label", "Theme")}
        </span>
        <div className="flex flex-wrap gap-2">
          {builtinPresets.map((preset) => (
            <ThemeSwatch
              key={preset.id}
              theme={preset}
              isActive={preset.id === themeId}
              isDark={isDark}
              onClick={() => setThemeId(preset.id)}
            />
          ))}
          {customPresets.map((preset) => (
            <ThemeSwatch
              key={preset.id}
              theme={preset}
              isActive={preset.id === themeId}
              isDark={isDark}
              onClick={() => setThemeId(preset.id)}
              onEdit={() => handleEdit(preset)}
              onDelete={() => handleDelete(preset.id)}
            />
          ))}
          <button
            type="button"
            onClick={handleCreate}
            className="flex flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-border p-2.5 transition-colors hover:border-primary/50 hover:bg-surface2 min-w-[90px]"
            title="Create custom theme"
          >
            <Plus className="h-4 w-4 text-text-muted" />
            <span className="text-xs text-text-muted leading-none">Create</span>
          </button>
        </div>
      </div>

      <ThemeEditorModal
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        onSave={handleSave}
        onDelete={handleDelete}
        editingTheme={editingTheme}
        isDark={isDark}
      />
    </div>
  )
}
