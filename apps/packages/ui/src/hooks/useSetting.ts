import { useCallback, useEffect, useMemo } from "react"
import { useStorage } from "@plasmohq/storage/hook"
import type { SettingDef } from "@/services/settings/registry"
import {
  getSetting,
  getStorageForSetting,
  normalizeSettingValue,
  setSetting
} from "@/services/settings/registry"

export const useSetting = <T>(setting: SettingDef<T>) => {
  const storage = getStorageForSetting(setting)
  const [rawValue, , meta] = useStorage<T | undefined>(
    { key: setting.key, instance: storage },
    setting.defaultValue
  )

  useEffect(() => {
    if (meta?.isLoading) return
    void getSetting(setting)
  }, [meta?.isLoading, setting])

  const value = useMemo(
    () => normalizeSettingValue(setting, rawValue),
    [setting, rawValue]
  )

  const setValue = useCallback(
    async (next: T | ((prev: T) => T)) => {
      const resolved =
        typeof next === "function" ? (next as (prev: T) => T)(value) : next
      const normalized = normalizeSettingValue(setting, resolved)
      // Update local render state immediately for web mode (no storage watchers).
      meta?.setRenderValue?.(normalized)
      await setSetting(setting, normalized)
    },
    [meta, setting, value]
  )

  return [value, setValue, meta] as const
}
