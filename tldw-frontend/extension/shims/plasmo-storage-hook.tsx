import { useCallback, useEffect, useMemo, useState } from "react"
import { Storage } from "./plasmo-storage"

type UseStorageOptions<T> = {
  key: string
  instance?: Storage
  defaultValue?: T
}

type UseStorageMeta = {
  isLoading: boolean
}

type SetValue<T> = (
  value: T | ((prev: T | undefined) => T)
) => Promise<void>

export function useStorage<T = unknown>(
  keyOrOptions: string | UseStorageOptions<T>,
  defaultValue?: T
): [T | undefined, SetValue<T>, UseStorageMeta] {
  const options: UseStorageOptions<T> =
    typeof keyOrOptions === "string"
      ? { key: keyOrOptions, defaultValue }
      : keyOrOptions

  const storage = useMemo(
    () => options.instance ?? new Storage(),
    [options.instance]
  )

  const [value, setValue] = useState<T | undefined>(options.defaultValue)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    storage
      .get<T>(options.key)
      .then((stored) => {
        if (cancelled) return
        if (stored === undefined) {
          setValue(options.defaultValue)
        } else {
          setValue(stored)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [options.key, options.defaultValue, storage])

  const setStoredValue = useCallback<SetValue<T>>(
    async (next) => {
      const resolved =
        typeof next === "function"
          ? (next as (prev: T | undefined) => T)(value)
          : next
      setValue(resolved)
      await storage.set(options.key, resolved)
    },
    [options.key, storage, value]
  )

  return [value, setStoredValue, { isLoading }]
}
