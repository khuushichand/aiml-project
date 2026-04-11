import React from "react"

import { apiSend } from "@/services/api-send"

type UseArchetypePreviewResult = {
  preview: Record<string, unknown> | null
  loading: boolean
  error: string | null
}

/**
 * Fetches a full archetype preview from
 * `GET /api/v1/persona/archetypes/{key}/preview`.
 *
 * Skips the fetch when `key` is null, and re-fetches whenever the key
 * changes.
 */
export function useArchetypePreview(
  key: string | null
): UseArchetypePreviewResult {
  const [preview, setPreview] = React.useState<Record<string, unknown> | null>(
    null
  )
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!key) {
      setPreview(null)
      setLoading(false)
      setError(null)
      return
    }

    let cancelled = false

    const fetchPreview = async () => {
      setLoading(true)
      setError(null)
      setPreview(null)
      try {
        const encodedKey = encodeURIComponent(key)
        const res = await apiSend<Record<string, unknown>>({
          path: `/api/v1/persona/archetypes/${encodedKey}/preview` as any,
          method: "GET"
        })
        if (cancelled) return
        if (res.ok && res.data && typeof res.data === "object") {
          setPreview(res.data)
        } else {
          setError(res.error ?? "Failed to load archetype preview")
        }
      } catch {
        if (!cancelled) {
          setError("Failed to load archetype preview")
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void fetchPreview()

    return () => {
      cancelled = true
    }
  }, [key])

  return { preview, loading, error }
}
