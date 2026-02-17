import { useQuery } from "@tanstack/react-query"
import { apiSend } from "@/services/api-send"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { fetchTldwVoices, type TldwVoice } from "@/services/tldw/audio-voices"

export type AudioHealthState =
  | "unknown"
  | "healthy"
  | "unhealthy"
  | "unavailable"

type Options = {
  requireVoices?: boolean
}

type AudioStatus = {
  hasAudio: boolean
  healthState: AudioHealthState
  healthLoading: boolean
  voices: TldwVoice[]
  voicesLoading: boolean
  voicesAvailable: boolean | null
}

type AudioHealthResponse = {
  ok?: boolean
  status?: number
}

export const useTldwAudioStatus = (options: Options = {}): AudioStatus => {
  const { capabilities, loading } = useServerCapabilities()
  const hasAudio = Boolean(capabilities?.hasAudio) && !loading

  const healthQuery = useQuery<AudioHealthResponse>({
    queryKey: ["audio-health"],
    queryFn: async () =>
      (await apiSend({
        path: "/api/v1/audio/health",
        method: "GET"
      })) as AudioHealthResponse,
    enabled: hasAudio,
    staleTime: 60_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: false
  })

  let healthState: AudioHealthState = "unknown"
  if (!hasAudio) {
    healthState = loading ? "unknown" : "unavailable"
  } else if (healthQuery.isLoading) {
    healthState = "unknown"
  } else if (healthQuery.data?.ok) {
    healthState = "healthy"
  } else if (healthQuery.data?.status === 404) {
    healthState = "unknown"
  } else {
    healthState = "unhealthy"
  }

  const voicesQuery = useQuery<TldwVoice[]>({
    queryKey: ["audio-voices"],
    queryFn: () => fetchTldwVoices(),
    enabled: hasAudio && Boolean(options.requireVoices),
    staleTime: 300_000,
    refetchOnWindowFocus: false
  })

  const voices = voicesQuery.data ?? []
  const voicesAvailable =
    options.requireVoices && !voicesQuery.isLoading ? voices.length > 0 : null

  return {
    hasAudio,
    healthState,
    healthLoading: healthQuery.isLoading,
    voices,
    voicesLoading: voicesQuery.isLoading,
    voicesAvailable
  }
}
