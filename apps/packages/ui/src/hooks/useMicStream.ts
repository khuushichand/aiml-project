import { useCallback, useEffect, useRef, useState } from 'react'

function floatTo16BitPCM(float32Array: Float32Array) {
  const buffer = new ArrayBuffer(float32Array.length * 2)
  const view = new DataView(buffer)
  let offset = 0
  for (let i = 0; i < float32Array.length; i++, offset += 2) {
    let s = Math.max(-1, Math.min(1, float32Array[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return buffer
}

export function useMicStream(onChunk: (pcmChunk: ArrayBuffer) => void) {
  const [active, setActive] = useState(false)
  const activeRef = useRef(false)
  const startingRef = useRef(false)
  const onChunkRef = useRef(onChunk)
  const startIdRef = useRef(0)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const ctxRef = useRef<AudioContext | null>(null)

  useEffect(() => {
    onChunkRef.current = onChunk
  }, [onChunk])

  const stop = useCallback(() => {
    startIdRef.current += 1
    try { processorRef.current?.disconnect() } catch {}
    try { sourceRef.current?.disconnect() } catch {}
    try { ctxRef.current?.close() } catch {}
    mediaStreamRef.current?.getTracks().forEach(t => t.stop())
    processorRef.current = null
    sourceRef.current = null
    mediaStreamRef.current = null
    ctxRef.current = null
    startingRef.current = false
    if (activeRef.current) {
      activeRef.current = false
      setActive(false)
    }
  }, [])

  const start = useCallback(async () => {
    if (activeRef.current || startingRef.current) return
    startingRef.current = true
    const startId = startIdRef.current + 1
    startIdRef.current = startId
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (startIdRef.current !== startId) {
        stream.getTracks().forEach((t) => t.stop())
        return
      }
      mediaStreamRef.current = stream
      const ctx = new AudioContext({ sampleRate: 16000 })
      ctxRef.current = ctx
      const source = ctx.createMediaStreamSource(stream)
      sourceRef.current = source
      const processor = ctx.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor
      source.connect(processor)
      processor.connect(ctx.destination)
      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0)
        const pcm = floatTo16BitPCM(input)
        try {
          onChunkRef.current(pcm)
        } catch {
          // ignore handler errors to keep the audio pipeline alive
        }
      }
      activeRef.current = true
      setActive(true)
    } catch (err) {
      stop()
      throw err
    } finally {
      startingRef.current = false
    }
  }, [stop])

  useEffect(() => {
    activeRef.current = active
  }, [active])

  useEffect(() => () => stop(), [stop])

  return { start, stop, active }
}
