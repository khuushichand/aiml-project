import { useCallback, useEffect, useRef, useState } from "react"

export type RecorderStatus = "idle" | "recording" | "paused"

export interface UseAudioRecorderReturn {
  status: RecorderStatus
  blob: Blob | null
  durationMs: number
  startRecording: () => Promise<void>
  stopRecording: () => void
  clearRecording: () => void
  loadBlob: (file: Blob, durationMs: number) => void
}

export function useAudioRecorder(): UseAudioRecorderReturn {
  const [status, setStatus] = useState<RecorderStatus>("idle")
  const [blob, setBlob] = useState<Blob | null>(null)
  const [durationMs, setDurationMs] = useState(0)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])
  const startTimeRef = useRef<number>(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const startRecording = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const recorder = new MediaRecorder(stream)
    recorderRef.current = recorder
    chunksRef.current = []
    startTimeRef.current = Date.now()

    recorder.ondataavailable = (ev: BlobEvent) => {
      if (ev.data && ev.data.size > 0) {
        chunksRef.current.push(ev.data)
      }
    }

    recorder.onstop = () => {
      const finalBlob = new Blob(chunksRef.current, {
        type: recorder.mimeType || "audio/webm"
      })
      setBlob(finalBlob)
      setStatus("idle")
      clearTimer()
      stream.getTracks().forEach((t) => t.stop())
    }

    recorder.start()
    setStatus("recording")
    setDurationMs(0)

    timerRef.current = setInterval(() => {
      setDurationMs(Date.now() - startTimeRef.current)
    }, 200)
  }, [clearTimer])

  const stopRecording = useCallback(() => {
    const recorder = recorderRef.current
    if (recorder && recorder.state !== "inactive") {
      recorder.stop()
    }
  }, [])

  const clearRecording = useCallback(() => {
    setBlob(null)
    setDurationMs(0)
    chunksRef.current = []
  }, [])

  const loadBlob = useCallback((file: Blob, duration: number) => {
    setBlob(file)
    setDurationMs(duration)
    setStatus("idle")
  }, [])

  useEffect(() => {
    return () => {
      clearTimer()
    }
  }, [clearTimer])

  return {
    status,
    blob,
    durationMs,
    startRecording,
    stopRecording,
    clearRecording,
    loadBlob
  }
}
