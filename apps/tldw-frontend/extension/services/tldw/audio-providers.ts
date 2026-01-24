import { bgRequestClient } from "@/services/background-proxy"

export type TldwTtsVoiceInfo = {
  id?: string
  name?: string
  language?: string
  gender?: string
  description?: string | null
  preview_url?: string | null
  [key: string]: unknown
}

export type TldwTtsProviderCapabilities = {
  provider_name?: string
  formats?: string[]
  supports_streaming?: boolean
  supports_voice_cloning?: boolean
  supports_ssml?: boolean
  supports_speech_rate?: boolean
  supports_emotion_control?: boolean
  [key: string]: unknown
}

export type TldwTtsProvidersInfo = {
  providers: Record<string, TldwTtsProviderCapabilities>
  voices: Record<string, TldwTtsVoiceInfo[]>
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null

export const fetchTtsProviders = async (): Promise<TldwTtsProvidersInfo | null> => {
  try {
    const res = await bgRequestClient<unknown>({
      path: "/api/v1/audio/providers",
      method: "GET"
    })

    if (!isRecord(res)) {
      return null
    }

    const rawProviders =
      isRecord(res.providers) ? res.providers : res
    const rawVoices =
      isRecord(res.voices) ? res.voices : {}

    const providers: Record<string, TldwTtsProviderCapabilities> = {}
    const voices: Record<string, TldwTtsVoiceInfo[]> = {}

    if (isRecord(rawProviders)) {
      for (const key of Object.keys(rawProviders)) {
        const value = rawProviders[key]
        if (isRecord(value)) {
          providers[key] = value as TldwTtsProviderCapabilities
        }
      }
    }

    if (isRecord(rawVoices)) {
      for (const key of Object.keys(rawVoices)) {
        const list = Array.isArray(rawVoices[key]) ? rawVoices[key] : []
        voices[key] = list as TldwTtsVoiceInfo[]
      }
    }

    if (Object.keys(providers).length === 0 && Object.keys(voices).length === 0) {
      return null
    }

    return { providers, voices }
  } catch {
    return null
  }
}
