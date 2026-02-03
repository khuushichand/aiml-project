import React from "react"
import { useQuery } from "@tanstack/react-query"
import { apiSend } from "@/services/api-send"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { useSetting } from "@/hooks/useSetting"
import {
  fetchMcpToolCatalogs,
  fetchMcpTools,
  fetchMcpToolCatalogsViaDiscovery,
  fetchMcpModulesViaDiscovery,
  fetchMcpToolsViaDiscovery,
  type McpToolCatalog,
  type McpToolDefinition
} from "@/services/tldw/mcp"
import {
  MCP_TOOL_CATALOG_SETTING,
  MCP_TOOL_CATALOG_ID_SETTING,
  MCP_TOOL_CATALOG_STRICT_SETTING,
  MCP_TOOL_MODULE_SETTING
} from "@/services/settings/ui-settings"
import { useMcpToolsStore, type McpHealthState } from "@/store/mcp-tools"

type McpToolsStatus = {
  hasMcp: boolean
  healthState: McpHealthState
  healthLoading: boolean
  tools: McpToolDefinition[]
  toolsLoading: boolean
  toolsAvailable: boolean | null
  catalogs: McpToolCatalog[]
  catalogsLoading: boolean
  toolCatalog: string
  toolCatalogId: number | null
  toolModules: string[]
  moduleOptions: string[]
  moduleOptionsLoading: boolean
  toolCatalogStrict: boolean
  setToolCatalog: (catalog: string) => void
  setToolCatalogId: (catalogId: number | null) => void
  setToolModules: (moduleIds: string[]) => void
  setToolCatalogStrict: (strict: boolean) => void
}

const normalizeModuleList = (modules: string[] | null | undefined): string[] => {
  const seen = new Set<string>()
  const result: string[] = []
  for (const moduleId of modules ?? []) {
    if (typeof moduleId !== "string") continue
    const trimmed = moduleId.trim()
    if (!trimmed || seen.has(trimmed)) continue
    seen.add(trimmed)
    result.push(trimmed)
  }
  return result
}

const areModuleListsEqual = (left: string[], right: string[]): boolean => {
  if (left.length !== right.length) return false
  return left.every((value, index) => value === right[index])
}

export const useMcpTools = (): McpToolsStatus => {
  const { capabilities, loading } = useServerCapabilities()
  const hasMcp = Boolean(capabilities?.hasMcp) && !loading
  const setTools = useMcpToolsStore((state) => state.setTools)
  const setHealthState = useMcpToolsStore((state) => state.setHealthState)
  const setToolsLoading = useMcpToolsStore((state) => state.setToolsLoading)
  const toolCatalog = useMcpToolsStore((state) => state.toolCatalog)
  const toolCatalogId = useMcpToolsStore((state) => state.toolCatalogId)
  const toolModules = useMcpToolsStore((state) => state.toolModules)
  const toolCatalogStrict = useMcpToolsStore((state) => state.toolCatalogStrict)
  const setToolCatalog = useMcpToolsStore((state) => state.setToolCatalog)
  const setToolCatalogId = useMcpToolsStore((state) => state.setToolCatalogId)
  const setToolModules = useMcpToolsStore((state) => state.setToolModules)
  const setToolCatalogStrict = useMcpToolsStore((state) => state.setToolCatalogStrict)

  const [storedCatalog, persistCatalog] = useSetting(MCP_TOOL_CATALOG_SETTING)
  const [storedCatalogId, persistCatalogId] = useSetting(MCP_TOOL_CATALOG_ID_SETTING)
  const [storedModule, persistModule] = useSetting(MCP_TOOL_MODULE_SETTING)
  const [storedStrict, persistStrict] = useSetting(MCP_TOOL_CATALOG_STRICT_SETTING)
  const normalizedToolModules = React.useMemo(
    () => normalizeModuleList(toolModules),
    [toolModules]
  )
  const normalizedStoredModules = React.useMemo(
    () => normalizeModuleList(storedModule),
    [storedModule]
  )
  const healthQuery = useQuery({
    queryKey: ["mcp-health"],
    queryFn: async () => apiSend({ path: "/api/v1/mcp/health", method: "GET" }),
    enabled: hasMcp,
    staleTime: 60_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: false
  })

  let healthState: McpHealthState = "unknown"
  if (!hasMcp) {
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

  const toolsQuery = useQuery({
    queryKey: [
      "mcp-tools",
      toolCatalog,
      toolCatalogId,
      normalizedToolModules,
      toolCatalogStrict
    ],
    queryFn: async () => {
      try {
        const tools = await fetchMcpToolsViaDiscovery({
          catalog: toolCatalog,
          catalogId: toolCatalogId,
          module:
            normalizedToolModules.length > 0 ? normalizedToolModules : undefined,
          catalogStrict: toolCatalogStrict
        })
        return tools
      } catch {
        return await fetchMcpTools({
          catalog: toolCatalog,
          catalogId: toolCatalogId,
          module:
            normalizedToolModules.length > 0 ? normalizedToolModules : undefined,
          catalogStrict: toolCatalogStrict
        })
      }
    },
    enabled: hasMcp,
    staleTime: 60_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: false
  })

  const catalogsQuery = useQuery({
    queryKey: ["mcp-tool-catalogs"],
    queryFn: async () => {
      try {
        return await fetchMcpToolCatalogsViaDiscovery("all")
      } catch {
        return await fetchMcpToolCatalogs()
      }
    },
    enabled: hasMcp,
    staleTime: 60_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: false
  })

  const moduleOptionsQuery = useQuery({
    queryKey: ["mcp-tool-modules"],
    queryFn: async () => {
      try {
        return await fetchMcpModulesViaDiscovery()
      } catch {
        const tools = await fetchMcpTools()
        const seen = new Set<string>()
        const modules: string[] = []
        for (const tool of tools) {
          const moduleId =
            typeof tool?.module === "string" ? tool.module.trim() : ""
          if (!moduleId || seen.has(moduleId)) continue
          seen.add(moduleId)
          modules.push(moduleId)
        }
        return modules
      }
    },
    enabled: hasMcp,
    staleTime: 60_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: false
  })

  const tools = (toolsQuery.data ?? []).filter((tool) => {
    if (!tool || typeof tool !== "object") return false
    if (!("canExecute" in tool)) return true
    return Boolean((tool as McpToolDefinition).canExecute)
  })
  const toolsAvailable = toolsQuery.isLoading ? null : tools.length > 0
  const catalogs = catalogsQuery.data ?? []
  const moduleOptionsSource =
    moduleOptionsQuery.data && moduleOptionsQuery.data.length > 0
      ? moduleOptionsQuery.data
      : toolsQuery.data ?? []
  const moduleOptions = React.useMemo(() => {
    const seen = new Set<string>()
    const result: string[] = []
    for (const entry of moduleOptionsSource ?? []) {
      const moduleId =
        typeof entry === "string"
          ? entry.trim()
          : typeof (entry as McpToolDefinition)?.module === "string"
            ? String((entry as McpToolDefinition).module).trim()
            : ""
      if (!moduleId || seen.has(moduleId)) continue
      seen.add(moduleId)
      result.push(moduleId)
    }
    return result.sort((a, b) => a.localeCompare(b))
  }, [moduleOptionsSource])
  const moduleOptionsLoading =
    moduleOptionsQuery.isLoading && moduleOptionsSource.length === 0

  React.useEffect(() => {
    setHealthState(healthState)
  }, [healthState, setHealthState])

  React.useEffect(() => {
    if (storedCatalog !== toolCatalog) {
      setToolCatalog(storedCatalog)
    }
  }, [setToolCatalog, storedCatalog, toolCatalog])

  React.useEffect(() => {
    if (storedCatalogId !== toolCatalogId) {
      setToolCatalogId(storedCatalogId ?? null)
    }
  }, [setToolCatalogId, storedCatalogId, toolCatalogId])

  React.useEffect(() => {
    if (!areModuleListsEqual(normalizedStoredModules, normalizedToolModules)) {
      setToolModules(normalizedStoredModules)
    }
  }, [normalizedStoredModules, normalizedToolModules, setToolModules])

  React.useEffect(() => {
    if (storedStrict !== toolCatalogStrict) {
      setToolCatalogStrict(storedStrict)
    }
  }, [setToolCatalogStrict, storedStrict, toolCatalogStrict])

  React.useEffect(() => {
    if (!hasMcp && !loading) {
      setTools([])
      setToolsLoading(false)
      return
    }
    setToolsLoading(toolsQuery.isLoading)
    if (!toolsQuery.isLoading) {
      setTools(tools)
    }
  }, [hasMcp, loading, setTools, setToolsLoading, tools, toolsQuery.isLoading])

  const persistToolCatalog = React.useCallback(
    (catalog: string) => {
      setToolCatalog(catalog)
      void persistCatalog(catalog)
    },
    [persistCatalog, setToolCatalog]
  )

  const persistToolCatalogId = React.useCallback(
    (catalogId: number | null) => {
      setToolCatalogId(catalogId)
      void persistCatalogId(catalogId)
    },
    [persistCatalogId, setToolCatalogId]
  )

  const persistToolModule = React.useCallback(
    (moduleIds: string[]) => {
      const normalized = normalizeModuleList(moduleIds)
      if (areModuleListsEqual(normalized, normalizedToolModules)) return
      setToolModules(normalized)
      void persistModule(normalized)
    },
    [normalizedToolModules, persistModule, setToolModules]
  )

  const persistToolCatalogStrict = React.useCallback(
    (strict: boolean) => {
      setToolCatalogStrict(strict)
      void persistStrict(strict)
    },
    [persistStrict, setToolCatalogStrict]
  )

  return {
    hasMcp,
    healthState,
    healthLoading: healthQuery.isLoading,
    tools,
    toolsLoading: toolsQuery.isLoading,
    toolsAvailable,
    catalogs,
    catalogsLoading: catalogsQuery.isLoading,
    toolCatalog,
    toolCatalogId,
    toolModules: normalizedToolModules,
    moduleOptions,
    moduleOptionsLoading,
    toolCatalogStrict,
    setToolCatalog: persistToolCatalog,
    setToolCatalogId: persistToolCatalogId,
    setToolModules: persistToolModule,
    setToolCatalogStrict: persistToolCatalogStrict
  }
}
