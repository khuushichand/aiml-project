import { useCallback, useRef, useState } from "react"

export type ComparisonResultStatus = "pending" | "running" | "done" | "error"

export interface ComparisonResult {
  model: string
  status: ComparisonResultStatus
  text: string
  error?: string
  latencyMs?: number
  startedAt?: number
}

export interface UseComparisonTranscribeOptions {
  sttOptions?: Record<string, any>
}

export interface UseComparisonTranscribeReturn {
  results: ComparisonResult[]
  isRunning: boolean
  transcribeAll: (blob: Blob, models: string[]) => void
  retryModel: (blob: Blob, model: string) => void
  clearResults: () => void
}

/**
 * Hook that manages parallel transcription of the same audio blob
 * across multiple STT models for side-by-side comparison.
 */
export function useComparisonTranscribe(
  options: UseComparisonTranscribeOptions = {}
): UseComparisonTranscribeReturn {
  const [results, setResults] = useState<ComparisonResult[]>([])
  const [isRunning, setIsRunning] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const transcribeOne = useCallback(
    async (blob: Blob, model: string) => {
      setResults((prev) =>
        prev.map((r) =>
          r.model === model ? { ...r, status: "running" as const, startedAt: Date.now() } : r
        )
      )
      try {
        const formData = new FormData()
        formData.append("file", blob, "recording.webm")
        formData.append("model", model)
        if (options.sttOptions) {
          for (const [k, v] of Object.entries(options.sttOptions)) {
            if (v != null) formData.append(k, String(v))
          }
        }
        const startTime = Date.now()
        const res = await fetch("/api/v1/audio/transcriptions", {
          method: "POST",
          body: formData,
        })
        const latencyMs = Date.now() - startTime
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`)
        }
        const data = await res.json()
        const text =
          typeof data === "string"
            ? data
            : data?.text ?? data?.transcript ?? ""
        setResults((prev) =>
          prev.map((r) =>
            r.model === model
              ? { ...r, status: "done" as const, text, latencyMs }
              : r
          )
        )
      } catch (e: any) {
        setResults((prev) =>
          prev.map((r) =>
            r.model === model
              ? { ...r, status: "error" as const, error: e?.message || "Unknown error" }
              : r
          )
        )
      }
    },
    [options.sttOptions]
  )

  const transcribeAll = useCallback(
    (blob: Blob, models: string[]) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      const initial: ComparisonResult[] = models.map((model) => ({
        model,
        status: "pending" as const,
        text: "",
      }))
      setResults(initial)
      setIsRunning(true)

      const promises = models.map((model) => transcribeOne(blob, model))
      Promise.allSettled(promises).then(() => {
        if (!controller.signal.aborted) {
          setIsRunning(false)
        }
      })
    },
    [transcribeOne]
  )

  const retryModel = useCallback(
    (blob: Blob, model: string) => {
      transcribeOne(blob, model)
    },
    [transcribeOne]
  )

  const clearResults = useCallback(() => {
    abortRef.current?.abort()
    setResults([])
    setIsRunning(false)
  }, [])

  return { results, isRunning, transcribeAll, retryModel, clearResults }
}
