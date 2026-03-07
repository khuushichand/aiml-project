import { useCallback, useEffect, useRef, useState } from "react"

export type AudioRecorderStatus = "idle" | "recording"

export interface AudioRecorderResult {
  status: AudioRecorderStatus
  blob: Blob | null
  durationMs: number
  startRecording: () => Promise<void>
  stopRecording: () => void
  clearRecording: () => void
  loadBlob: (blob: Blob, durationMs: number) => void
}

const TIMER_INTERVAL_MS = 200

export function useAudioRecorder(): AudioRecorderResult {
  const [status, setStatus] = useState<AudioRecorderStatus>("idle")
  const [blob, setBlob] = useState<Blob | null>(null)
  const [durationMs, setDurationMs] = useState(0)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const startTimeRef = useRef<number>(0)

  const stopTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const stopMediaTracks = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
  }, [])

  const stopRecording = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state === "recording") {
      recorderRef.current.stop()
    }
  }, [])

  const startRecording = useCallback(async () => {
    chunksRef.current = []

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    streamRef.current = stream

    const recorder = new MediaRecorder(stream)
    recorderRef.current = recorder

    recorder.ondataavailable = (event: BlobEvent) => {
      if (event.data.size > 0) {
        chunksRef.current.push(event.data)
      }
    }

    recorder.onstop = () => {
      const recordedBlob = new Blob(chunksRef.current, {
        type: recorder.mimeType || "audio/webm"
      })
      const finalDuration = Date.now() - startTimeRef.current
      setBlob(recordedBlob)
      setDurationMs(finalDuration)
      stopTimer()
      stopMediaTracks()
      setStatus("idle")
      recorderRef.current = null
    }

    startTimeRef.current = Date.now()
    recorder.start()
    setStatus("recording")

    timerRef.current = setInterval(() => {
      setDurationMs(Date.now() - startTimeRef.current)
    }, TIMER_INTERVAL_MS)
  }, [stopTimer, stopMediaTracks])

  const clearRecording = useCallback(() => {
    setBlob(null)
    setDurationMs(0)
  }, [])

  const loadBlob = useCallback((externalBlob: Blob, externalDurationMs: number) => {
    setBlob(externalBlob)
    setDurationMs(externalDurationMs)
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopTimer()
      if (recorderRef.current && recorderRef.current.state === "recording") {
        recorderRef.current.stop()
      }
      stopMediaTracks()
    }
  }, [stopTimer, stopMediaTracks])

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
