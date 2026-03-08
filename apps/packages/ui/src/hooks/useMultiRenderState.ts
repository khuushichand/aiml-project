import { useCallback, useEffect, useRef, useState } from "react"
import {
  resolveTtsProviderContext,
  type TtsProviderOverrides
} from "@/services/tts-provider"
import type { RenderStripConfig, RenderStripState } from "@/components/Option/Speech/RenderStrip"

export type RenderEntry = {
  id: string
  config: RenderStripConfig
  state: RenderStripState
  audioUrl?: string
  audioBlob?: Blob
  errorMessage?: string
  progress?: number
}

let nextId = 1
const genId = () => `render-${Date.now()}-${nextId++}`

const configToOverrides = (config: RenderStripConfig): TtsProviderOverrides => {
  const overrides: TtsProviderOverrides = { provider: config.provider }
  if (config.provider === "tldw") {
    overrides.tldwModel = config.model
    overrides.tldwVoice = config.voice
    overrides.tldwResponseFormat = config.format
    overrides.tldwSpeed = config.speed
  } else if (config.provider === "openai") {
    overrides.openAiModel = config.model
    overrides.openAiVoice = config.voice
    overrides.openAiSpeed = config.speed
  } else if (config.provider === "elevenlabs") {
    overrides.elevenLabsModel = config.model
    overrides.elevenLabsVoiceId = config.voice
    overrides.elevenLabsSpeed = config.speed
  }
  return overrides
}

export const useMultiRenderState = () => {
  const [renders, setRenders] = useState<RenderEntry[]>([])
  const [playingId, setPlayingId] = useState<string | null>(null)
  const objectUrlsRef = useRef<Map<string, string>>(new Map())
  const abortControllersRef = useRef<Map<string, AbortController>>(new Map())

  // Cleanup object URLs on unmount
  useEffect(() => {
    return () => {
      for (const url of objectUrlsRef.current.values()) {
        try { URL.revokeObjectURL(url) } catch {}
      }
      objectUrlsRef.current.clear()
      for (const ctrl of abortControllersRef.current.values()) {
        try { ctrl.abort() } catch {}
      }
      abortControllersRef.current.clear()
    }
  }, [])

  const addRender = useCallback((config: RenderStripConfig): string => {
    const id = genId()
    setRenders((prev) => [
      ...prev,
      { id, config, state: "idle" }
    ])
    return id
  }, [])

  const removeRender = useCallback((id: string) => {
    // Revoke object URL
    const url = objectUrlsRef.current.get(id)
    if (url) {
      try { URL.revokeObjectURL(url) } catch {}
      objectUrlsRef.current.delete(id)
    }
    // Abort any in-progress generation
    const ctrl = abortControllersRef.current.get(id)
    if (ctrl) {
      try { ctrl.abort() } catch {}
      abortControllersRef.current.delete(id)
    }
    setRenders((prev) => prev.filter((r) => r.id !== id))
    setPlayingId((prev) => (prev === id ? null : prev))
  }, [])

  const updateRender = useCallback(
    (id: string, updates: Partial<RenderEntry>) => {
      setRenders((prev) =>
        prev.map((r) => (r.id === id ? { ...r, ...updates } : r))
      )
    },
    []
  )

  const updateConfig = useCallback(
    (id: string, config: RenderStripConfig) => {
      setRenders((prev) =>
        prev.map((r) => (r.id === id ? { ...r, config } : r))
      )
    },
    []
  )

  const generateRender = useCallback(
    async (id: string, text: string) => {
      if (!text.trim()) return

      updateRender(id, { state: "generating", progress: 0, errorMessage: undefined })

      const entry = renders.find((r) => r.id === id)
      if (!entry) return

      const controller = new AbortController()
      abortControllersRef.current.set(id, controller)

      try {
        const overrides = configToOverrides(entry.config)
        const context = await resolveTtsProviderContext(text, overrides)

        if (!context.supported || !context.synthesize) {
          updateRender(id, {
            state: "error",
            errorMessage: `Provider "${entry.config.provider}" is not supported`
          })
          return
        }

        if (controller.signal.aborted) return

        const audio = await context.synthesize(context.utterance)

        if (controller.signal.aborted) return

        const blob = new Blob([audio.buffer], { type: audio.mimeType })
        const url = URL.createObjectURL(blob)

        // Revoke old URL if any
        const oldUrl = objectUrlsRef.current.get(id)
        if (oldUrl) {
          try { URL.revokeObjectURL(oldUrl) } catch {}
        }
        objectUrlsRef.current.set(id, url)

        updateRender(id, {
          state: "ready",
          audioUrl: url,
          audioBlob: blob,
          progress: 100
        })
      } catch (error) {
        if (controller.signal.aborted) return
        updateRender(id, {
          state: "error",
          errorMessage:
            error instanceof Error ? error.message : "Generation failed"
        })
      } finally {
        abortControllersRef.current.delete(id)
      }
    },
    [renders, updateRender]
  )

  const generateAll = useCallback(
    async (text: string) => {
      const pending = renders.filter(
        (r) => r.state === "idle" || r.state === "error"
      )
      await Promise.allSettled(
        pending.map((r) => generateRender(r.id, text))
      )
    },
    [renders, generateRender]
  )

  const clearAll = useCallback(() => {
    for (const url of objectUrlsRef.current.values()) {
      try { URL.revokeObjectURL(url) } catch {}
    }
    objectUrlsRef.current.clear()
    for (const ctrl of abortControllersRef.current.values()) {
      try { ctrl.abort() } catch {}
    }
    abortControllersRef.current.clear()
    setRenders([])
    setPlayingId(null)
  }, [])

  // Play-one-at-a-time: setting playingId pauses all others
  const startPlaying = useCallback((id: string) => {
    setPlayingId(id)
  }, [])

  const stopPlaying = useCallback((id: string) => {
    setPlayingId((prev) => (prev === id ? null : prev))
  }, [])

  const playAllSequentially = useCallback(
    async (onStripPlay?: (id: string) => void) => {
      const readyStrips = renders.filter(
        (r) => r.state === "ready" && r.audioUrl
      )
      for (const strip of readyStrips) {
        setPlayingId(strip.id)
        onStripPlay?.(strip.id)
        // Wait for audio to finish by creating a temporary audio element
        await new Promise<void>((resolve) => {
          if (!strip.audioUrl) {
            resolve()
            return
          }
          const audio = new Audio(strip.audioUrl)
          audio.onended = () => resolve()
          audio.onerror = () => resolve()
          audio.play().catch(() => resolve())
        })
        // 1-second pause between strips
        await new Promise<void>((resolve) => setTimeout(resolve, 1000))
      }
      setPlayingId(null)
    },
    [renders]
  )

  const hasIdle = renders.some((r) => r.state === "idle" || r.state === "error")
  const hasReady = renders.some((r) => r.state === "ready")
  const isAnyGenerating = renders.some((r) => r.state === "generating")

  return {
    renders,
    playingId,
    addRender,
    removeRender,
    updateRender,
    updateConfig,
    generateRender,
    generateAll,
    clearAll,
    startPlaying,
    stopPlaying,
    playAllSequentially,
    hasIdle,
    hasReady,
    isAnyGenerating
  }
}
