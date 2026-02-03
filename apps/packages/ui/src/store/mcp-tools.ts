import { createWithEqualityFn } from "zustand/traditional"
import type { McpToolDefinition } from "@/services/tldw/mcp"

export type McpHealthState =
  | "unknown"
  | "healthy"
  | "unhealthy"
  | "unavailable"

type McpToolsState = {
  tools: McpToolDefinition[]
  healthState: McpHealthState
  toolsLoading: boolean
  toolCatalog: string
  toolCatalogId: number | null
  toolModules: string[]
  toolCatalogStrict: boolean
  setTools: (tools: McpToolDefinition[]) => void
  setHealthState: (state: McpHealthState) => void
  setToolsLoading: (loading: boolean) => void
  setToolCatalog: (catalog: string) => void
  setToolCatalogId: (catalogId: number | null) => void
  setToolModules: (moduleIds: string[]) => void
  setToolCatalogStrict: (strict: boolean) => void
}

export const useMcpToolsStore = createWithEqualityFn<McpToolsState>((set) => ({
  tools: [],
  healthState: "unknown",
  toolsLoading: false,
  toolCatalog: "",
  toolCatalogId: null,
  toolModules: [],
  toolCatalogStrict: false,
  setTools: (tools) => set({ tools }),
  setHealthState: (healthState) => set({ healthState }),
  setToolsLoading: (toolsLoading) => set({ toolsLoading }),
  setToolCatalog: (toolCatalog) => set({ toolCatalog }),
  setToolCatalogId: (toolCatalogId) => set({ toolCatalogId }),
  setToolModules: (toolModules) => set({ toolModules }),
  setToolCatalogStrict: (toolCatalogStrict) => set({ toolCatalogStrict })
}))
