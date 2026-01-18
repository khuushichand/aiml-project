import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Storage } from "./plasmo-storage"

type UseStorageOptions<T> = {
  key: string
  instance?: Storage
  defaultValue?: T
}

type UseStorageMeta<T> = {
  isLoading: boolean
  setRenderValue: (value: T | undefined) => void
}

type SetValue<T> = (
  value: T | ((prev: T | undefined) => T)
) => Promise<void>

export function useStorage<T = unknown>(
  keyOrOptions: string | UseStorageOptions<T>,
  defaultValue?: T
): [T | undefined, SetValue<T>, UseStorageMeta<T>] {
  const options: UseStorageOptions<T> =
    typeof keyOrOptions === "string"
      ? { key: keyOrOptions, defaultValue }
      : keyOrOptions

  const storage = useMemo(
    () => options.instance ?? new Storage(),
    [options.instance]
  )

  const defaultValueRef = useRef<T | undefined>(options.defaultValue)
  const [value, setValue] = useState<T | undefined>(defaultValueRef.current)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    storage
      .get<T>(options.key)
      .then((stored) => {
        if (cancelled) return
        if (stored === undefined) {
          setValue(defaultValueRef.current)
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
  }, [options.key, storage])

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

  return [value, setStoredValue, { isLoading, setRenderValue: setValue }]
}
