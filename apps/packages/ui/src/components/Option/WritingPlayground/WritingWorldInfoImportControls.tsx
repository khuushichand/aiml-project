import React from "react"
import { Button, Select } from "antd"
import type { WritingWorldInfoSettings } from "./writing-context-utils"
import {
  applyWorldInfoImport,
  parseWorldInfoImportPayload,
  type WritingWorldInfoImportMode
} from "./writing-world-info-transfer-utils"

type TranslateFn = (...args: unknown[]) => unknown

type WritingWorldInfoImportControlsProps = {
  disabled?: boolean
  worldInfo: WritingWorldInfoSettings
  onImported: (
    nextWorldInfo: WritingWorldInfoSettings,
    mode: WritingWorldInfoImportMode
  ) => void
  onImportError: (detail: string) => void
  t: TranslateFn
  initialMode?: WritingWorldInfoImportMode
}

export const WritingWorldInfoImportControls = ({
  disabled = false,
  worldInfo,
  onImported,
  onImportError,
  t,
  initialMode = "replace"
}: WritingWorldInfoImportControlsProps) => {
  const [mode, setMode] = React.useState<WritingWorldInfoImportMode>(initialMode)
  const fileInputRef = React.useRef<HTMLInputElement | null>(null)

  const handleImport = React.useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0]
      if (!file) return
      try {
        const text = await file.text()
        const parsedJson = JSON.parse(text)
        const parsed = parseWorldInfoImportPayload(parsedJson)
        if (parsed.error || !parsed.value) {
          throw new Error(
            parsed.error ??
              String(
                t(
                  "option:writingPlayground.worldInfoImportInvalid",
                  "Invalid world info import payload."
                )
              )
          )
        }
        const nextWorldInfo = applyWorldInfoImport(worldInfo, parsed.value, mode)
        onImported(nextWorldInfo, mode)
      } catch (error) {
        const detail =
          error instanceof Error
            ? error.message
            : String(t("option:error", "Error"))
        onImportError(detail)
      } finally {
        event.target.value = ""
      }
    },
    [mode, onImportError, onImported, t, worldInfo]
  )

  return (
    <>
      <Select<WritingWorldInfoImportMode>
        size="small"
        value={mode}
        disabled={disabled}
        onChange={(value) => setMode(value)}
        options={[
          {
            value: "replace",
            label: String(
              t(
                "option:writingPlayground.worldInfoImportModeReplace",
                "Import mode: replace"
              )
            )
          },
          {
            value: "append",
            label: String(
              t(
                "option:writingPlayground.worldInfoImportModeAppend",
                "Import mode: append"
              )
            )
          }
        ]}
        popupMatchSelectWidth={false}
        className="min-w-[170px]"
      />
      <Button
        size="small"
        disabled={disabled}
        onClick={() => fileInputRef.current?.click()}>
        {String(t("option:writingPlayground.worldInfoImportAction", "Import"))}
      </Button>
      <input
        ref={fileInputRef}
        type="file"
        accept=".json,application/json"
        onChange={handleImport}
        data-testid="writing-world-info-import"
        className="hidden"
      />
    </>
  )
}
