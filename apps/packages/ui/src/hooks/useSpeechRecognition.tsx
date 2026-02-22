import { useRef, useEffect, useState, useCallback } from "react"

type SpeechRecognitionEvent = {
  results: SpeechRecognitionResultList
  resultIndex: number
}

declare global {
  interface Window {
    SpeechRecognition: any
    webkitSpeechRecognition: any
  }
}

type SpeechRecognitionErrorEventLike = Event & {
  error?: string
}

type SpeechRecognition = {
  lang: string
  interimResults: boolean
  continuous: boolean
  maxAlternatives: number
  grammars: any
  onresult: (event: SpeechRecognitionEvent) => void
  onerror: (event: Event) => void
  onend: () => void
  start: () => void
  stop: () => void
}

type SpeechRecognitionProps = {
  onEnd?: () => void
  onResult?: (transcript: string) => void
  onError?: (event: Event) => void
  autoStop?: boolean
  autoStopTimeout?: number
  autoSubmit?: boolean
}

type ListenArgs = {
  lang?: string
  interimResults?: boolean
  continuous?: boolean
  maxAlternatives?: number
  grammars?: any
  autoStop?: boolean
  autoStopTimeout?: number
  autoSubmit?: boolean
}

type SpeechRecognitionHook = {
  start: (args?: ListenArgs) => void
  isListening: boolean
  stop: () => void
  supported: boolean
  transcript: string
  resetTranscript: () => void
}

const createSyntheticErrorEvent = (
  error: string,
  cause?: unknown
): SpeechRecognitionErrorEventLike => {
  const event = new Event("error") as SpeechRecognitionErrorEventLike & {
    cause?: unknown
  }
  ;(event as any).error = error
  if (typeof cause !== "undefined") {
    ;(event as any).cause = cause
  }
  return event
}

const useEventCallback = <T extends (...args: any[]) => any>(
  fn: T,
  dependencies: any[]
) => {
  const ref = useRef<T>()

  useEffect(() => {
    ref.current = fn
  }, [fn, ...dependencies])

  return useCallback(
    (...args: Parameters<T>) => {
      const fn = ref.current
      return fn!(...args)
    },
    [ref]
  )
}

export const useSpeechRecognition = (
  props: SpeechRecognitionProps = {}
): SpeechRecognitionHook => {
  const {
    onEnd = () => {},
    onResult = () => {},
    onError = () => {},
    autoStop = false,
    autoStopTimeout = 5000,
    autoSubmit = false
  } = props

  const recognition = useRef<SpeechRecognition | null>(null)
  const isMounted = useRef<boolean>(true)
  const [listening, setListening] = useState<boolean>(false)
  const [supported, setSupported] = useState<boolean>(false)
  const [liveTranscript, setLiveTranscript] = useState<string>("")
  const silenceTimer = useRef<NodeJS.Timeout | null>(null)
  const lastTranscriptRef = useRef<string>("")

  const clearSilenceTimer = useCallback(() => {
    if (silenceTimer.current) {
      clearTimeout(silenceTimer.current)
      silenceTimer.current = null
    }
  }, [])

  const setListeningSafe = useCallback((value: boolean) => {
    if (!isMounted.current) return
    setListening(value)
  }, [])

  const setLiveTranscriptSafe = useCallback((value: string) => {
    if (!isMounted.current) return
    setLiveTranscript(value)
  }, [])

  useEffect(() => {
    isMounted.current = true
    if (typeof window === "undefined") return
    window.SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition
    if (window.SpeechRecognition) {
      setSupported(true)
      recognition.current = new window.SpeechRecognition()
    } else {
      setSupported(false)
      recognition.current = null
    }
    return () => {
      isMounted.current = false
    }
  }, [])

  const resetTranscript = () => {
    setLiveTranscriptSafe("")
    lastTranscriptRef.current = ""
  }

  const processResult = (
    event: SpeechRecognitionEvent,
    shouldAutoStop: boolean,
    shouldAutoSubmit: boolean,
    stopTimeout: number
  ) => {
    const transcript = Array.from(event.results)
      .map((result) => result[0])
      .map((result) => result.transcript)
      .join("")

    onResult(transcript)

    // Reset silence timer if transcript changed
    if (shouldAutoStop && transcript !== lastTranscriptRef.current) {
      lastTranscriptRef.current = transcript

      clearSilenceTimer()

      silenceTimer.current = setTimeout(() => {
        stop()
        if (shouldAutoSubmit) {
          // Submit the final transcript
          onResult(transcript)
        }
      }, stopTimeout)
    }
  }

  const handleError = (event: Event) => {
    const errorCode = (event as SpeechRecognitionErrorEventLike).error
    if (errorCode === "not-allowed" || errorCode === "service-not-allowed") {
      if (recognition.current) {
        recognition.current.onend = null
      }
      clearSilenceTimer()
      setListeningSafe(false)
      onEnd()
    }
    onError(event)
  }

  const listen = useEventCallback(
    (args: ListenArgs = {}) => {
      if (listening || !supported) return
      const {
        lang = "",
        interimResults = true,
        continuous = false,
        maxAlternatives = 1,
        grammars,
        autoStop: argAutoStop = autoStop,
        autoStopTimeout: argAutoStopTimeout = autoStopTimeout,
        autoSubmit: argAutoSubmit = autoSubmit
      } = args

      setListeningSafe(true)
      setLiveTranscriptSafe("")
      lastTranscriptRef.current = ""
      clearSilenceTimer()

      if (recognition.current) {
        recognition.current.lang = lang
        recognition.current.interimResults = interimResults
        recognition.current.onresult = (event) => {
          processResult(event, argAutoStop, argAutoSubmit, argAutoStopTimeout)
          const transcript = Array.from(event.results)
            .map((result) => result[0])
            .map((result) => result.transcript)
            .join("")
          setLiveTranscriptSafe(transcript)
        }
        recognition.current.onerror = handleError
        recognition.current.continuous = continuous
        recognition.current.maxAlternatives = maxAlternatives

        if (grammars) {
          recognition.current.grammars = grammars
        }
        recognition.current.onend = () => {
          if (recognition.current && !argAutoStop) {
            try {
              recognition.current.start()
            } catch (error) {
              setListeningSafe(false)
              onError(createSyntheticErrorEvent("start-failed", error))
              onEnd()
            }
          } else {
            setListeningSafe(false)
            onEnd()
          }
        }
        if (recognition.current) {
          try {
            recognition.current.start()
          } catch (error) {
            setListeningSafe(false)
            onError(createSyntheticErrorEvent("start-failed", error))
          }
        }
      }
    },
    [
      listening,
      supported,
      recognition,
      autoStop,
      autoStopTimeout,
      autoSubmit,
      clearSilenceTimer,
      setListeningSafe,
      setLiveTranscriptSafe,
      onError,
      onEnd
    ]
  )

  const stop = useEventCallback(() => {
    if (!listening || !supported) return

    clearSilenceTimer()

    if (recognition.current) {
      recognition.current.onresult = null
      recognition.current.onend = null
      recognition.current.onerror = null
      setListeningSafe(false)
      try {
        recognition.current.stop()
      } catch (error) {
        onError(createSyntheticErrorEvent("stop-failed", error))
      }
    }
    onEnd()
  }, [listening, supported, recognition, clearSilenceTimer, setListeningSafe, onEnd, onError])

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      clearSilenceTimer()
      if (recognition.current) {
        recognition.current.onresult = null
        recognition.current.onend = null
        recognition.current.onerror = null
        try {
          recognition.current.stop()
        } catch {}
        recognition.current = null
      }
    }
  }, [clearSilenceTimer])

  return {
    start: listen,
    isListening: listening,
    stop,
    supported,
    transcript: liveTranscript,
    resetTranscript
  }
}
