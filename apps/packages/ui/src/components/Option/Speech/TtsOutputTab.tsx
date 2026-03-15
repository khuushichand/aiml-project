import React, { useEffect, useRef } from "react"
import { Select, Slider, Switch, Tooltip } from "antd"
import { useTranslation } from "react-i18next"

type Props = {
  format: string
  synthesisSpeed: number
  playbackSpeed: number
  responseSplitting: string
  streaming: boolean
  canStream: boolean
  streamFormatSupported: boolean
  onFormatChange: (value: string) => void
  onSynthesisSpeedChange: (value: number) => void
  onPlaybackSpeedChange: (value: number) => void
  onResponseSplittingChange: (value: string) => void
  onStreamingChange: (value: boolean) => void
  formatOptions: { label: string; value: string }[]
  normalize: boolean
  onNormalizeChange: (value: boolean) => void
  normalizeUnits: boolean
  onNormalizeUnitsChange: (value: boolean) => void
  normalizeUrls: boolean
  onNormalizeUrlsChange: (value: boolean) => void
  normalizeEmails: boolean
  onNormalizeEmailsChange: (value: boolean) => void
  normalizePhones: boolean
  onNormalizePhonesChange: (value: boolean) => void
  normalizePlurals: boolean
  onNormalizePluralsChange: (value: boolean) => void
  focusField: string | null
  onFocusHandled: () => void
}

export const TtsOutputTab: React.FC<Props> = (props) => {
  const { t } = useTranslation("playground")
  const formatRef = useRef<any>(null)

  useEffect(() => {
    if (!props.focusField) return
    const timer = setTimeout(() => {
      if (props.focusField === "format") formatRef.current?.focus?.()
      props.onFocusHandled()
    }, 100)
    return () => clearTimeout(timer)
  }, [props.focusField, props.onFocusHandled])

  const streamingDisabledReason = !props.canStream
    ? "Provider does not support streaming"
    : !props.streamFormatSupported
      ? `Format does not support streaming`
      : null

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm text-text mb-1 block">Format</label>
        <Select
          ref={formatRef}
          className="w-full"
          value={props.format}
          onChange={props.onFormatChange}
          options={props.formatOptions}
        />
      </div>
      <div>
        <label className="text-sm text-text mb-1 block">Synthesis Speed</label>
        <div className="flex items-center gap-3">
          <Slider
            className="flex-1"
            min={0.25}
            max={4}
            step={0.05}
            value={props.synthesisSpeed}
            onChange={props.onSynthesisSpeedChange}
          />
          <span className="text-xs text-text-subtle w-10 text-right">
            {props.synthesisSpeed.toFixed(2)}
          </span>
        </div>
      </div>
      <div>
        <label className="text-sm text-text mb-1 block">Playback Speed</label>
        <div className="flex items-center gap-3">
          <Slider
            className="flex-1"
            min={0.25}
            max={2}
            step={0.05}
            value={props.playbackSpeed}
            onChange={props.onPlaybackSpeedChange}
          />
          <span className="text-xs text-text-subtle w-10 text-right">
            {props.playbackSpeed.toFixed(2)}
          </span>
        </div>
      </div>
      <div>
        <label className="text-sm text-text mb-1 block">Response Splitting</label>
        <Select
          className="w-full"
          value={props.responseSplitting}
          onChange={props.onResponseSplittingChange}
          options={[
            { label: "None", value: "none" },
            { label: "Punctuation", value: "punctuation" },
            { label: "Paragraph", value: "paragraph" }
          ]}
        />
      </div>
      <div className="flex items-center justify-between">
        <div>
          <label className="text-sm text-text">Stream audio (WebSocket)</label>
          <div className="text-xs text-text-subtle">Low-latency playback while audio generates.</div>
        </div>
        <Tooltip title={streamingDisabledReason}>
          <Switch
            checked={props.streaming}
            onChange={props.onStreamingChange}
            disabled={Boolean(streamingDisabledReason)}
          />
        </Tooltip>
      </div>
      <div className="rounded-md border border-border p-3 space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-sm text-text">Smart normalization</label>
          <Switch checked={props.normalize} onChange={props.onNormalizeChange} />
        </div>
        <div className="text-xs text-text-subtle">
          Expands units, URLs, emails, and phone numbers to improve pronunciation.
        </div>
        {props.normalize && (
          <div className="grid gap-2 sm:grid-cols-2">
            {[
              { label: "Units", checked: props.normalizeUnits, onChange: props.onNormalizeUnitsChange },
              { label: "URLs", checked: props.normalizeUrls, onChange: props.onNormalizeUrlsChange },
              { label: "Emails", checked: props.normalizeEmails, onChange: props.onNormalizeEmailsChange },
              { label: "Phone", checked: props.normalizePhones, onChange: props.onNormalizePhonesChange },
              { label: "Pluralization", checked: props.normalizePlurals, onChange: props.onNormalizePluralsChange }
            ].map(({ label, checked, onChange }) => (
              <div key={label} className="flex items-center justify-between">
                <span className="text-xs text-text-subtle">{label}</span>
                <Switch size="small" checked={checked} onChange={onChange} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
