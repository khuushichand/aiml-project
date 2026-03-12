import React from "react"
import { Button, Slider, Tooltip, Typography } from "antd"
import { Download, Pause, Play } from "lucide-react"
import WaveformCanvas from "@/components/Common/WaveformCanvas"

const { Text } = Typography

export type UnifiedAudioPlayerProps = {
  /** Object URL or data URL for the audio */
  audioUrl?: string
  /** Raw blob for download */
  audioBlob?: Blob
  /** Whether audio is currently streaming in */
  isStreaming?: boolean
  /** Label for accessibility */
  label?: string
  /** Compact mode reduces height */
  compact?: boolean
  /** Called when playback starts */
  onPlay?: () => void
  /** Called when playback pauses */
  onPause?: () => void
  /** Called when playback ends naturally */
  onEnd?: () => void
  /** Called on seek */
  onSeek?: (time: number) => void
  /** Filename for download (without extension) */
  downloadFilename?: string
  /** Audio format for download extension */
  format?: string
  /** Whether to show the waveform visualization */
  showWaveform?: boolean
  /** External control: force pause */
  forcePaused?: boolean
}

const formatTime = (seconds: number): string => {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00"
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, "0")}`
}

export const UnifiedAudioPlayer: React.FC<UnifiedAudioPlayerProps> = ({
  audioUrl,
  audioBlob,
  isStreaming = false,
  label = "Audio player",
  compact = false,
  onPlay,
  onPause,
  onEnd,
  onSeek,
  downloadFilename,
  format = "mp3",
  showWaveform = true,
  forcePaused
}) => {
  const audioRef = React.useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = React.useState(false)
  const [currentTime, setCurrentTime] = React.useState(0)
  const [duration, setDuration] = React.useState(0)

  // Load audio source
  React.useEffect(() => {
    const el = audioRef.current
    if (!el) return
    if (audioUrl) {
      el.src = audioUrl
      el.load()
    } else {
      el.removeAttribute("src")
    }
    setPlaying(false)
    setCurrentTime(0)
    setDuration(0)
  }, [audioUrl])

  // Force pause from parent
  React.useEffect(() => {
    if (forcePaused && playing) {
      audioRef.current?.pause()
      setPlaying(false)
    }
  }, [forcePaused, playing])

  const handlePlayPause = () => {
    const el = audioRef.current
    if (!el || !audioUrl) return
    if (playing) {
      el.pause()
      setPlaying(false)
      onPause?.()
    } else {
      el.play().catch(() => {})
      setPlaying(true)
      onPlay?.()
    }
  }

  const handleTimeUpdate = () => {
    const el = audioRef.current
    if (!el) return
    setCurrentTime(el.currentTime)
    setDuration(el.duration || 0)
  }

  const handleEnded = () => {
    setPlaying(false)
    setCurrentTime(0)
    onEnd?.()
  }

  const handleSeek = (value: number) => {
    const el = audioRef.current
    if (!el || !Number.isFinite(value)) return
    el.currentTime = value
    setCurrentTime(value)
    onSeek?.(value)
  }

  const handleDownload = () => {
    const blob = audioBlob
    const url = audioUrl
    if (!blob && !url) return

    const extension = format || "mp3"
    const name = downloadFilename || `audio-${Date.now()}`
    const filename = `${name}.${extension}`

    if (blob) {
      const blobUrl = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = blobUrl
      link.download = filename
      link.click()
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
    } else if (url) {
      const link = document.createElement("a")
      link.href = url
      link.download = filename
      link.click()
    }
  }

  const hasAudio = Boolean(audioUrl)
  const sliderMax = duration > 0 ? duration : 1
  const waveformHeight = compact ? 40 : 56

  return (
    <div
      role="region"
      aria-label={label}
      className="flex flex-col gap-1.5 rounded-md border border-border bg-surface/60 px-3 py-2"
    >
      {/* Hidden native audio element */}
      <audio
        ref={audioRef}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleTimeUpdate}
        onEnded={handleEnded}
        preload="metadata"
      />

      {/* Controls row */}
      <div className="flex items-center gap-2">
        <Button
          type="text"
          size="small"
          icon={
            playing ? (
              <Pause className="h-4 w-4" />
            ) : (
              <Play className="h-4 w-4" />
            )
          }
          disabled={!hasAudio && !isStreaming}
          onClick={handlePlayPause}
          aria-label={playing ? "Pause" : "Play"}
        />

        {/* Time display */}
        <Text className="min-w-[80px] text-xs tabular-nums text-text-muted">
          {formatTime(currentTime)} / {formatTime(duration)}
        </Text>

        {/* Seek slider */}
        <div className="flex-1">
          <Slider
            min={0}
            max={sliderMax}
            step={0.1}
            value={currentTime}
            onChange={handleSeek}
            disabled={!hasAudio || duration <= 0}
            tooltip={{ formatter: (v) => formatTime(v ?? 0) }}
            styles={{ track: { height: 3 }, rail: { height: 3 } }}
          />
        </div>

        {/* Download */}
        {(audioBlob || audioUrl) && (
          <Tooltip title="Download">
            <Button
              type="text"
              size="small"
              icon={<Download className="h-3.5 w-3.5" />}
              onClick={handleDownload}
              aria-label="Download audio"
            />
          </Tooltip>
        )}
      </div>

      {/* Waveform visualization */}
      {showWaveform && hasAudio && (
        <WaveformCanvas
          audioRef={audioRef as React.RefObject<HTMLAudioElement>}
          active={playing}
          label={`${label} waveform`}
          height={waveformHeight}
        />
      )}

      {/* Streaming indicator */}
      {isStreaming && (
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
          <Text className="text-xs text-text-muted">Streaming...</Text>
        </div>
      )}
    </div>
  )
}

export default UnifiedAudioPlayer
