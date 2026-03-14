import { useQuery } from "@tanstack/react-query"
import React from "react"
import { useTranslation } from "react-i18next"

import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import {
  fetchMcpToolCatalogs,
  fetchMcpToolCatalogsViaDiscovery,
  fetchMcpModulesViaDiscovery,
  fetchMcpTools,
  fetchMcpToolsViaDiscovery,
  type McpToolCatalog,
  type McpToolDefinition
} from "@/services/tldw/mcp"

type McpToolPickerProps = {
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  autoClearStaleTool?: boolean
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
  return result.sort((left, right) => left.localeCompare(right))
}

const getToolName = (tool: McpToolDefinition): string =>
  typeof tool?.name === "string" ? tool.name.trim() : ""

const getToolModule = (tool: McpToolDefinition): string =>
  typeof tool?.module === "string" ? String(tool.module).trim() : ""

const getToolOptionKey = (tool: McpToolDefinition, index: number): string => {
  const toolName = getToolName(tool) || `tool-${index}`
  const rawToolId = tool?.id
  const rawCatalog = tool?.catalog
  const uniqueSuffix =
    typeof rawToolId === "string" || typeof rawToolId === "number"
      ? String(rawToolId)
      : typeof rawCatalog === "string" || typeof rawCatalog === "number"
        ? String(rawCatalog)
        : getToolModule(tool) || String(index)
  return `${toolName}-${uniqueSuffix}`
}

const filterExecutableTools = (tools: McpToolDefinition[]): McpToolDefinition[] =>
  tools.filter((tool) => {
    if (!tool || typeof tool !== "object") return false
    if (!("canExecute" in tool)) return true
    return tool.canExecute !== false
  })

const deriveModulesFromTools = (tools: McpToolDefinition[]): string[] =>
  normalizeModuleList(tools.map((tool) => getToolModule(tool)))

export const McpToolPicker: React.FC<McpToolPickerProps> = ({
  value,
  onChange,
  disabled = false,
  autoClearStaleTool = false
}) => {
  const { t } = useTranslation(["sidepanel", "common"])
  const { capabilities, loading: capabilitiesLoading } = useServerCapabilities()
  const hasMcp = Boolean(capabilities?.hasMcp) && !capabilitiesLoading
  const mcpUnavailable = !capabilitiesLoading && !capabilities?.hasMcp
  const [catalogId, setCatalogId] = React.useState<number | null>(null)
  const [selectedModule, setSelectedModule] = React.useState("")
  const [manualMode, setManualMode] = React.useState(false)
  const [draftValue, setDraftValue] = React.useState(value)
  const [showStaleToolWarning, setShowStaleToolWarning] = React.useState(false)

  const catalogsQuery = useQuery({
    queryKey: ["persona-garden", "mcp-tool-picker", "catalogs"],
    queryFn: async () => {
      try {
        return await fetchMcpToolCatalogsViaDiscovery("all")
      } catch {
        return await fetchMcpToolCatalogs()
      }
    },
    enabled: hasMcp,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: false,
    placeholderData: (previousData) => previousData
  })

  const modulesQuery = useQuery({
    queryKey: ["persona-garden", "mcp-tool-picker", "modules"],
    queryFn: async () => {
      try {
        return await fetchMcpModulesViaDiscovery()
      } catch {
        const tools = await fetchMcpTools()
        return deriveModulesFromTools(filterExecutableTools(tools))
      }
    },
    enabled: hasMcp,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: false,
    placeholderData: (previousData) => previousData
  })

  const toolsQuery = useQuery({
    queryKey: [
      "persona-garden",
      "mcp-tool-picker",
      "tools",
      catalogId,
      selectedModule
    ],
    queryFn: async () => {
      const params = {
        catalogId,
        module: selectedModule || undefined
      }
      try {
        return await fetchMcpToolsViaDiscovery(params)
      } catch {
        return await fetchMcpTools(params)
      }
    },
    enabled: hasMcp,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: false,
    placeholderData: (previousData) => previousData
  })

  const catalogs = React.useMemo(
    () => (catalogsQuery.data ?? []).filter(Boolean) as McpToolCatalog[],
    [catalogsQuery.data]
  )
  const tools = React.useMemo(
    () => filterExecutableTools(toolsQuery.data ?? []),
    [toolsQuery.data]
  )
  const moduleOptions = React.useMemo(() => {
    const fromDiscovery = normalizeModuleList(modulesQuery.data ?? [])
    if (fromDiscovery.length > 0) return fromDiscovery
    return deriveModulesFromTools(tools)
  }, [modulesQuery.data, tools])
  const toolOptions = React.useMemo(
    () =>
      [...tools]
        .sort((left, right) => getToolName(left).localeCompare(getToolName(right)))
        .filter((tool) => getToolName(tool).length > 0),
    [tools]
  )
  const isLoading =
    capabilitiesLoading ||
    (hasMcp &&
      ((catalogsQuery.isLoading && !catalogsQuery.data) ||
        (modulesQuery.isLoading && !modulesQuery.data) ||
        (toolsQuery.isLoading && !toolsQuery.data)))
  const currentValue = draftValue

  React.useEffect(() => {
    setDraftValue(value)
    setShowStaleToolWarning(false)
  }, [value])

  React.useEffect(() => {
    if (mcpUnavailable) {
      setManualMode(true)
    }
  }, [mcpUnavailable])

  // Loop safety: this effect only infers an initial module from a committed tool
  // when MCP is available, the current value is non-empty, no module is selected,
  // and tool options have loaded. When a match is found we setSelectedModule to
  // narrow the picker; otherwise we fall back to manual mode. The guards prevent
  // cascading re-renders once module state or tool options change.
  React.useEffect(() => {
    if (
      !hasMcp ||
      !currentValue.trim() ||
      selectedModule ||
      toolOptions.length === 0
    ) {
      return
    }
    const matchingTool = toolOptions.find(
      (tool) => getToolName(tool) === currentValue.trim()
    )
    const matchingModule = matchingTool ? getToolModule(matchingTool) : ""
    if (matchingModule) {
      setSelectedModule(matchingModule)
      return
    }
    setManualMode(true)
  }, [currentValue, hasMcp, selectedModule, toolOptions])

  React.useEffect(() => {
    if (!hasMcp || !selectedModule || !currentValue.trim() || toolsQuery.isLoading) {
      return
    }
    const matchesSelectedModule = toolOptions.some(
      (tool) => getToolName(tool) === currentValue.trim()
    )
    if (!matchesSelectedModule) {
      setDraftValue("")
      setShowStaleToolWarning(true)
      if (autoClearStaleTool) {
        onChange("")
      }
      return
    }
    setShowStaleToolWarning(false)
  }, [
    autoClearStaleTool,
    currentValue,
    hasMcp,
    onChange,
    selectedModule,
    toolOptions,
    toolsQuery.isLoading
  ])

  const handleCatalogChange = React.useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>) => {
      const nextValue = event.target.value
      if (!nextValue) {
        setCatalogId(null)
        return
      }
      const parsed = Number.parseInt(nextValue, 10)
      setCatalogId(Number.isFinite(parsed) ? parsed : null)
    },
    []
  )

  const handleModuleChange = React.useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>) => {
      setShowStaleToolWarning(false)
      setSelectedModule(event.target.value)
    },
    []
  )

  const handleToolChange = React.useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>) => {
      const nextValue = event.target.value
      setShowStaleToolWarning(false)
      setDraftValue(nextValue)
      onChange(nextValue)
    },
    [onChange]
  )

  if (mcpUnavailable) {
    return (
      <div className="space-y-2">
        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-800">
          {t("sidepanel:personaGarden.commands.mcpUnavailable", {
            defaultValue:
              "MCP discovery is unavailable for this server. Enter a tool name manually."
          })}
        </div>
        <label className="block text-xs text-text-muted">
          {t("sidepanel:personaGarden.commands.toolName", {
            defaultValue: "Tool name"
          })}
          <input
            data-testid="persona-mcp-tool-picker-manual-input"
            className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
            value={currentValue}
            onChange={(event) => {
              const nextValue = event.target.value
              setDraftValue(nextValue)
              onChange(nextValue)
            }}
            placeholder="notes.search"
            disabled={disabled}
          />
        </label>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="rounded-md border border-border bg-surface px-3 py-2 text-xs text-text-muted">
        {t("sidepanel:personaGarden.commands.mcpLoading", {
          defaultValue: "Loading MCP tools..."
        })}
      </div>
    )
  }

  if (manualMode) {
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div className="text-xs text-text-muted">
            {t("sidepanel:personaGarden.commands.manualToolEntry", {
              defaultValue:
                "Enter a tool name directly if it is not visible in the MCP catalog."
            })}
          </div>
          {hasMcp ? (
            <button
              type="button"
              className="rounded-md border border-border px-2 py-1 text-xs text-text transition hover:bg-surface2"
            onClick={() => setManualMode(false)}
            disabled={disabled}
          >
              {t("sidepanel:personaGarden.commands.backToPicker", {
                defaultValue: "Back to picker"
              })}
            </button>
          ) : null}
        </div>
        <label className="block text-xs text-text-muted">
          {t("sidepanel:personaGarden.commands.toolName", {
            defaultValue: "Tool name"
          })}
          <input
            data-testid="persona-mcp-tool-picker-manual-input"
            className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
            value={currentValue}
            onChange={(event) => {
              const nextValue = event.target.value
              setShowStaleToolWarning(false)
              setDraftValue(nextValue)
              onChange(nextValue)
            }}
            placeholder="notes.search"
            disabled={disabled}
          />
        </label>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {catalogs.length > 0 ? (
        <label className="block text-xs text-text-muted">
          {t("sidepanel:personaGarden.commands.catalog", {
            defaultValue: "Catalog"
          })}
          <select
            data-testid="persona-mcp-tool-picker-catalog-select"
            className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
            value={catalogId === null ? "" : String(catalogId)}
            onChange={handleCatalogChange}
            disabled={disabled}
          >
            <option value="">
              {t("sidepanel:personaGarden.commands.allCatalogs", {
                defaultValue: "All catalogs"
              })}
            </option>
            {catalogs.map((catalog) => (
              <option key={catalog.id} value={catalog.id}>
                {catalog.name}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <label className="block text-xs text-text-muted">
        {t("sidepanel:personaGarden.commands.module", {
          defaultValue: "Module"
        })}
        <select
          data-testid="persona-mcp-tool-picker-module-select"
          className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
          value={selectedModule}
          onChange={handleModuleChange}
          disabled={disabled}
        >
          <option value="">
            {t("sidepanel:personaGarden.commands.allModules", {
              defaultValue: "All modules"
            })}
          </option>
          {moduleOptions.map((moduleId) => (
            <option key={moduleId} value={moduleId}>
              {moduleId}
            </option>
          ))}
        </select>
      </label>

      <label className="block text-xs text-text-muted">
        {t("sidepanel:personaGarden.commands.toolName", {
          defaultValue: "Tool name"
        })}
        <select
          data-testid="persona-mcp-tool-picker-tool-select"
          className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
          value={currentValue}
          onChange={handleToolChange}
          disabled={disabled}
        >
          <option value="">
            {t("sidepanel:personaGarden.commands.selectTool", {
              defaultValue: "Select a tool"
            })}
          </option>
          {toolOptions.map((tool) => {
            const toolName = getToolName(tool)
            return (
              <option key={getToolOptionKey(tool, toolOptions.indexOf(tool))} value={toolName}>
                {toolName}
              </option>
            )
          })}
        </select>
      </label>

      {showStaleToolWarning ? (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-800">
          {t("sidepanel:personaGarden.commands.staleToolWarning", {
            defaultValue: "Selected tool is no longer available in this module."
          })}
        </div>
      ) : null}

      <div className="flex items-center justify-between gap-2 rounded-md border border-border bg-surface px-3 py-2 text-xs text-text-muted">
        <span>
          {t("sidepanel:personaGarden.commands.manualToolHint", {
            defaultValue: "Need a tool that is not listed yet?"
          })}
        </span>
        <button
          type="button"
          className="rounded-md border border-border px-2 py-1 text-xs text-text transition hover:bg-bg"
          onClick={() => {
            setShowStaleToolWarning(false)
            setManualMode(true)
          }}
          disabled={disabled}
        >
          {t("sidepanel:personaGarden.commands.enterManually", {
            defaultValue: "Enter manually"
          })}
        </button>
      </div>
    </div>
  )
}
