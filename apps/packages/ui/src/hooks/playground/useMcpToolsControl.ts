import React from "react"
import { useTranslation } from "react-i18next"

export type UseMcpToolsControlParams = {
  hasMcp: boolean
  mcpHealthState: string
  mcpTools: any[]
  mcpToolsLoading: boolean
  mcpCatalogs: any[]
  toolCatalog: string
  toolCatalogId: number | null
  setToolCatalog: (value: string) => void
  setToolCatalogId: (value: number | null) => void
  toolChoice: string
}

export function useMcpToolsControl({
  hasMcp,
  mcpHealthState,
  mcpTools,
  mcpToolsLoading,
  mcpCatalogs,
  toolCatalog,
  toolCatalogId,
  setToolCatalog,
  setToolCatalogId,
  toolChoice
}: UseMcpToolsControlParams) {
  const { t } = useTranslation(["playground"])

  const [mcpPopoverOpen, setMcpPopoverOpen] = React.useState(false)
  const [mcpSettingsOpen, setMcpSettingsOpen] = React.useState(false)
  const [catalogDraft, setCatalogDraft] = React.useState(toolCatalog)

  React.useEffect(() => {
    setCatalogDraft(toolCatalog)
  }, [toolCatalog])

  const commitCatalog = React.useCallback(() => {
    const next = catalogDraft.trim()
    if (next !== toolCatalog) {
      setToolCatalog(next)
    }
    if (toolCatalogId !== null && next !== toolCatalog) {
      setToolCatalogId(null)
    }
  }, [catalogDraft, setToolCatalog, toolCatalog, toolCatalogId, setToolCatalogId])

  const catalogGroups = React.useMemo(() => {
    const global: typeof mcpCatalogs = []
    const org: typeof mcpCatalogs = []
    const team: typeof mcpCatalogs = []
    for (const catalog of mcpCatalogs) {
      if (!catalog) continue
      if (catalog.team_id != null) {
        team.push(catalog)
      } else if (catalog.org_id != null) {
        org.push(catalog)
      } else {
        global.push(catalog)
      }
    }
    return { global, org, team }
  }, [mcpCatalogs])

  const catalogById = React.useMemo(() => {
    const map = new Map<number, (typeof mcpCatalogs)[number]>()
    for (const catalog of mcpCatalogs) {
      if (catalog?.id == null) continue
      map.set(catalog.id, catalog)
    }
    return map
  }, [mcpCatalogs])

  const handleCatalogSelect = React.useCallback(
    (value?: number) => {
      if (value === null || value === undefined) {
        setToolCatalogId(null)
        setToolCatalog("")
        return
      }
      const catalog = catalogById.get(value)
      setToolCatalogId(value)
      if (catalog?.name) {
        setToolCatalog(catalog.name)
      }
    },
    [catalogById, setToolCatalog, setToolCatalogId]
  )

  const handleModuleSelect = React.useCallback(
    (value?: string[], setToolModules?: (modules: string[]) => void) => {
      setToolModules?.(Array.isArray(value) ? value : [])
    },
    []
  )

  React.useEffect(() => {
    if (!hasMcp || mcpHealthState === "unhealthy") {
      setMcpPopoverOpen(false)
    }
  }, [hasMcp, mcpHealthState])

  const mcpNotCheckedYet = React.useMemo(
    () =>
      hasMcp &&
      mcpHealthState === "unknown" &&
      !mcpToolsLoading &&
      mcpTools.length === 0,
    [hasMcp, mcpHealthState, mcpTools.length, mcpToolsLoading]
  )

  const mcpDisabledReason = React.useMemo(() => {
    if (!hasMcp) {
      return t("playground:composer.mcpToolsUnavailable", "MCP tools unavailable")
    }
    if (mcpHealthState === "unhealthy") {
      return t("playground:composer.mcpToolsUnhealthy", "MCP tools are offline")
    }
    if (mcpToolsLoading) {
      return t("playground:composer.mcpToolsLoading", "Loading tools...")
    }
    if (mcpTools.length === 0) {
      return t("playground:composer.mcpToolsEmpty", "No MCP tools available")
    }
    return ""
  }, [hasMcp, mcpHealthState, mcpToolsLoading, mcpTools.length, t])

  const mcpChoiceLabel = React.useMemo(() => {
    switch (toolChoice) {
      case "required":
        return t("playground:composer.toolChoiceRequired", "Required")
      case "none":
        return t("playground:composer.toolChoiceNone", "None")
      case "auto":
      default:
        return t("playground:composer.toolChoiceAuto", "Auto")
    }
  }, [toolChoice, t])

  const mcpAriaLabel = React.useMemo(() => {
    if (!hasMcp) {
      return t("playground:composer.mcpAriaUnavailable", "MCP tools unavailable")
    }
    const countLabel = mcpToolsLoading
      ? t("playground:composer.mcpToolsLoading", "Loading tools...")
      : mcpNotCheckedYet
        ? t("playground:composer.mcpToolsNotChecked", "Not checked yet")
        : t("playground:tools.mcpSummary", "{{count}} tools", {
            count: mcpTools.length
          })
    return t(
      "playground:composer.mcpAriaLabel",
      "MCP tools: {{choice}}, {{summary}}",
      { choice: mcpChoiceLabel, summary: countLabel }
    )
  }, [hasMcp, mcpChoiceLabel, mcpNotCheckedYet, mcpTools.length, mcpToolsLoading, t])

  const mcpSummaryLabel = React.useMemo(() => {
    if (!hasMcp) return t("playground:composer.mcpToolsUnavailable", "MCP unavailable")
    if (mcpToolsLoading) return t("playground:composer.mcpToolsLoading", "Loading tools...")
    if (mcpNotCheckedYet) {
      return t("playground:composer.mcpToolsNotChecked", "Not checked yet")
    }
    return t("playground:tools.mcpSummary", "{{count}} tools", { count: mcpTools.length })
  }, [hasMcp, mcpNotCheckedYet, mcpToolsLoading, mcpTools.length, t])

  const mcpStatusLabel = React.useMemo(() => {
    if (!hasMcp) {
      return t("playground:composer.mcpToolsUnavailable", "MCP tools unavailable")
    }
    if (mcpHealthState === "unhealthy") {
      return t("playground:composer.mcpToolsUnhealthy", "MCP tools are offline")
    }
    if (mcpNotCheckedYet) {
      return t(
        "playground:composer.mcpToolsCheckAvailability",
        "Open this panel to check availability"
      )
    }
    return mcpSummaryLabel
  }, [hasMcp, mcpHealthState, mcpNotCheckedYet, mcpSummaryLabel, t])

  return {
    mcpPopoverOpen,
    setMcpPopoverOpen,
    mcpSettingsOpen,
    setMcpSettingsOpen,
    catalogDraft,
    setCatalogDraft,
    commitCatalog,
    catalogGroups,
    catalogById,
    handleCatalogSelect,
    handleModuleSelect,
    mcpDisabledReason,
    mcpChoiceLabel,
    mcpAriaLabel,
    mcpSummaryLabel,
    mcpStatusLabel
  }
}
