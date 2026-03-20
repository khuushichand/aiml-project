import React from "react"
import { Card, Tag, Typography } from "antd"
import type { TldwTtsProvidersInfo } from "@/services/tldw/audio-providers"
import { getProviderLabel } from "@/utils/provider-registry"
import { normalizeTtsProviderKey, toServerTtsProviderKey } from "@/services/tldw/tts-provider-keys"

const { Text } = Typography

type ProviderEntry = {
  key: string
  label: string
  category: "local" | "cloud" | "experimental"
  hint?: string
}

const KNOWN_TTS_ENGINES: ProviderEntry[] = [
  { key: "kokoro", label: "Kokoro", category: "local", hint: "Default local engine" },
  { key: "kitten_tts", label: "KittenTTS", category: "local", hint: "Fast local ONNX voices" },
  { key: "pocket_tts", label: "PocketTTS", category: "local", hint: "Voice cloning" },
  { key: "lux_tts", label: "LuxTTS", category: "local", hint: "ZipVoice cloning" },
  { key: "neutts", label: "NeuTTS", category: "local", hint: "Instant cloning" },
  { key: "index_tts", label: "IndexTTS", category: "local", hint: "Expressive zero-shot" },
  { key: "index_tts2", label: "IndexTTS2", category: "local", hint: "Expressive zero-shot" },
  { key: "qwen3_tts", label: "Qwen3-TTS", category: "local", hint: "Voice design + emotion" },
  { key: "higgs", label: "Higgs", category: "local" },
  { key: "dia", label: "Dia", category: "local" },
  { key: "chatterbox", label: "Chatterbox", category: "local", hint: "Emotion presets" },
  { key: "vibevoice", label: "VibeVoice", category: "local", hint: "Music + singing" },
  { key: "vibevoice_realtime", label: "VibeVoice Realtime", category: "local" },
  { key: "supertonic", label: "Supertonic", category: "local" },
  { key: "supertonic2", label: "Supertonic2", category: "local" },
  { key: "echo_tts", label: "Echo TTS", category: "local" },
  { key: "openai", label: "OpenAI", category: "cloud" },
  { key: "elevenlabs", label: "ElevenLabs", category: "cloud" }
]

const resolveCaps = (
  providersInfo: TldwTtsProvidersInfo | null | undefined,
  key: string
) => {
  if (!providersInfo?.providers) return null
  const direct = providersInfo.providers[key]
  if (direct) return direct
  const target = normalizeTtsProviderKey(key)
  const matchKey = Object.keys(providersInfo.providers).find(
    (candidate) => normalizeTtsProviderKey(candidate) === target
  )
  return matchKey ? providersInfo.providers[matchKey] : null
}

export const TtsProviderCatalog: React.FC<{
  providersInfo?: TldwTtsProvidersInfo | null
  withCard?: boolean
}> = ({ providersInfo, withCard = true }) => {
  const content = (
    <div className="space-y-2">
      <Text strong>Server TTS engines</Text>
      <div className="text-xs text-text-subtle">
        Engines listed here map to server-side providers (model names). Disabled entries
        can be enabled in `Config_Files/tts_providers_config.yaml` and by installing the
        required dependencies.
      </div>
      <div className="grid gap-2">
        {KNOWN_TTS_ENGINES.map((entry) => {
          const serverKey = toServerTtsProviderKey(entry.key)
          const caps = resolveCaps(providersInfo, serverKey)
          const label = getProviderLabel(entry.key, "tts-engine") || entry.label
          const available = Boolean(caps)
          return (
            <div
              key={entry.key}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-3 py-2"
            >
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <Text strong>{label}</Text>
                  <Tag color={available ? "green" : "default"} bordered>
                    {available ? "Available" : "Disabled"}
                  </Tag>
                  {entry.category === "cloud" && (
                    <Tag color="blue" bordered>
                      Cloud
                    </Tag>
                  )}
                  {entry.category === "experimental" && (
                    <Tag color="purple" bordered>
                      Experimental
                    </Tag>
                  )}
                </div>
                {entry.hint && (
                  <Text type="secondary" className="text-xs">
                    {entry.hint}
                  </Text>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-1">
                {caps?.supports_streaming && (
                  <Tag color="blue" bordered>
                    Streaming
                  </Tag>
                )}
                {caps?.supports_voice_cloning && (
                  <Tag color="magenta" bordered>
                    Voice cloning
                  </Tag>
                )}
                {caps?.supports_emotion_control && (
                  <Tag color="purple" bordered>
                    Emotion
                  </Tag>
                )}
                {caps?.supports_ssml && (
                  <Tag color="gold" bordered>
                    SSML
                  </Tag>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )

  if (!withCard) return content
  return <Card>{content}</Card>
}
