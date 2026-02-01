/**
 * useACPAgents - React Query hook for fetching available ACP agents
 */

import { useQuery } from "@tanstack/react-query"
import { useStorage } from "@plasmohq/storage/hook"
import { ACPRestClient } from "@/services/acp/client"
import type { ACPAgentListResponse } from "@/services/acp/types"

export interface UseACPAgentsOptions {
  enabled?: boolean
}

export interface UseACPAgentsReturn {
  agents: ACPAgentListResponse["agents"]
  defaultAgent: ACPAgentListResponse["default_agent"]
  isLoading: boolean
  isError: boolean
  error: Error | null
  refetch: () => void
}

export function useACPAgents(options: UseACPAgentsOptions = {}): UseACPAgentsReturn {
  const { enabled = true } = options

  // Server config from storage
  const [serverUrl] = useStorage("serverUrl", "http://localhost:8000")
  const [authMode] = useStorage("authMode", "single-user")
  const [apiKey] = useStorage("apiKey", "")
  const [accessToken] = useStorage("accessToken", "")

  // Create REST client
  const restClient = new ACPRestClient({
    serverUrl,
    getAuthHeaders: async () => {
      const headers: Record<string, string> = {}
      if (authMode === "single-user" && apiKey) {
        headers["X-API-KEY"] = apiKey
      } else if (authMode === "multi-user" && accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`
      }
      return headers
    },
    getAuthParams: async () => ({
      token: authMode === "multi-user" ? accessToken : undefined,
      api_key: authMode === "single-user" ? apiKey : undefined,
    }),
  })

  const query = useQuery({
    queryKey: ["acp", "agents", serverUrl],
    queryFn: () => restClient.getAvailableAgents(),
    enabled,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    retry: 2,
  })

  return {
    agents: query.data?.agents ?? [],
    defaultAgent: query.data?.default_agent ?? "claude_code",
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  }
}

export default useACPAgents
