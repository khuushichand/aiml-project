import { bgRequestClient, bgUpload } from "@/services/background-proxy"

export type TldwCustomVoice = {
  voice_id: string
  name: string
  description?: string | null
  provider: string
  duration: number
  format: string
  sample_rate?: number | null
  size_bytes?: number | null
  created_at?: string | null
  file_path?: string | null
  file_hash?: string | null
}

export type VoiceUploadResponse = {
  voice_id: string
  name: string
  file_path?: string
  duration?: number
  format?: string
  provider_compatible?: boolean
  warnings?: string[]
  info?: string
}

export type VoiceEncodeResponse = {
  voice_id: string
  provider: string
  cached?: boolean
  ref_codes_len?: number | null
  reference_text?: string | null
}

export const listCustomVoices = async (): Promise<TldwCustomVoice[]> => {
  const res = await bgRequestClient<{ voices?: TldwCustomVoice[] }>({
    path: "/api/v1/audio/voices",
    method: "GET"
  })
  const voices = Array.isArray(res?.voices) ? res.voices : []
  return voices
}

export const uploadCustomVoice = async (options: {
  file: File
  name: string
  description?: string
  provider: string
  referenceText?: string
}): Promise<VoiceUploadResponse> => {
  const data = await options.file.arrayBuffer()
  const fields: Record<string, any> = {
    name: options.name,
    provider: options.provider
  }
  if (options.description) fields.description = options.description
  if (options.referenceText) fields.reference_text = options.referenceText
  return await bgUpload<VoiceUploadResponse>({
    path: "/api/v1/audio/voices/upload",
    method: "POST",
    fields,
    file: {
      name: options.file.name || "voice",
      type: options.file.type || "application/octet-stream",
      data
    },
    fileFieldName: "file"
  })
}

export const encodeCustomVoice = async (payload: {
  voice_id: string
  provider: string
  reference_text?: string
  force?: boolean
}): Promise<VoiceEncodeResponse> => {
  return await bgRequestClient<VoiceEncodeResponse>({
    path: "/api/v1/audio/voices/encode",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload
  })
}

export const deleteCustomVoice = async (voiceId: string): Promise<void> => {
  await bgRequestClient({
    path: `/api/v1/audio/voices/${encodeURIComponent(voiceId)}`,
    method: "DELETE"
  })
}

export const VOICE_PROVIDER_REQUIREMENTS: Record<
  string,
  { formats: string[]; duration?: { min: number; max: number }; sample_rate?: number }
> = {
  vibevoice: {
    formats: [".wav", ".mp3", ".flac", ".ogg"],
    duration: { min: 0.1, max: 600 },
    sample_rate: 22050
  },
  higgs: {
    formats: [".wav", ".mp3"],
    duration: { min: 3, max: 10 },
    sample_rate: 16000
  },
  chatterbox: {
    formats: [".wav", ".mp3"],
    duration: { min: 5, max: 20 },
    sample_rate: 22050
  },
  elevenlabs: {
    formats: [".wav", ".mp3"],
    duration: { min: 1, max: 30 },
    sample_rate: 44100
  },
  neutts: {
    formats: [".wav", ".mp3", ".flac", ".ogg", ".m4a", ".opus"],
    duration: { min: 3, max: 15 },
    sample_rate: 16000
  },
  pocket_tts: {
    formats: [".wav", ".mp3", ".flac", ".ogg", ".m4a"],
    duration: { min: 1, max: 60 },
    sample_rate: 24000
  },
  qwen3_tts: {
    formats: [".wav", ".mp3", ".flac", ".ogg", ".m4a", ".opus"],
    duration: { min: 3, max: 30 },
    sample_rate: 24000
  }
}
