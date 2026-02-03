import type { ToolCall } from "@/types/tool-calls"
import { useMcpToolsStore } from "@/store/mcp-tools"
import {
  MCP_TOOL_CATALOG_ID_SETTING,
  MCP_TOOL_CATALOG_SETTING,
  MCP_TOOL_CATALOG_STRICT_SETTING,
  MCP_TOOL_MODULE_SETTING
} from "@/services/settings/ui-settings"
import { setSetting } from "@/services/settings/registry"
import { notification as staticNotification } from "antd"

const normalizeModuleList = (values: string[]): string[] => {
  const seen = new Set<string>()
  const result: string[] = []
  for (const value of values) {
    if (typeof value !== "string") continue
    const trimmed = value.trim()
    if (!trimmed || seen.has(trimmed)) continue
    seen.add(trimmed)
    result.push(trimmed)
  }
  return result
}

const extractModules = (args: Record<string, unknown>): string[] => {
  const modules: string[] = []
  const pushValue = (value: unknown) => {
    if (typeof value === "string") {
      const trimmed = value.trim()
      if (!trimmed) return
      if (trimmed.includes(",")) {
        modules.push(...trimmed.split(","))
      } else {
        modules.push(trimmed)
      }
    } else if (Array.isArray(value)) {
      for (const item of value) {
        if (typeof item === "string") modules.push(item)
      }
    }
  }
  pushValue(args.module)
  pushValue(args.modules)
  return normalizeModuleList(modules)
}

const parseToolArguments = (toolCall: ToolCall): Record<string, unknown> | null => {
  const raw = toolCall?.function?.arguments
  if (raw && typeof raw === "object") {
    return raw as Record<string, unknown>
  }
  if (typeof raw === "string") {
    const trimmed = raw.trim()
    if (!trimmed) return null
    try {
      const parsed = JSON.parse(trimmed)
      if (parsed && typeof parsed === "object") {
        return parsed as Record<string, unknown>
      }
    } catch {
      return null
    }
  }
  const params = toolCall?.function?.parameters
  if (params && typeof params === "object") {
    return params as Record<string, unknown>
  }
  return null
}

const extractCatalog = (args: Record<string, unknown>): {
  catalogName?: string
  catalogId?: number
  hasCatalogName: boolean
  hasCatalogId: boolean
} => {
  let catalogName: string | undefined
  let catalogId: number | undefined
  let hasCatalogName = false
  let hasCatalogId = false

  const rawName = args.catalog
  if (typeof rawName === "string") {
    const trimmed = rawName.trim()
    if (trimmed) {
      catalogName = trimmed
      hasCatalogName = true
    }
  }

  const rawId = args.catalog_id ?? args.catalogId
  if (rawId !== undefined && rawId !== null && rawId !== "") {
    const parsed = Number(rawId)
    if (Number.isFinite(parsed)) {
      catalogId = parsed
      hasCatalogId = true
    }
  }

  return { catalogName, catalogId, hasCatalogName, hasCatalogId }
}

const parseBooleanValue = (value: unknown): boolean | null => {
  if (typeof value === "boolean") return value
  if (typeof value === "number") return value !== 0
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase()
    if (["1", "true", "yes", "on"].includes(normalized)) return true
    if (["0", "false", "no", "off"].includes(normalized)) return false
  }
  return null
}

const extractCatalogStrict = (args: Record<string, unknown>) => {
  const hasCatalogStrict =
    Object.prototype.hasOwnProperty.call(args, "catalog_strict") ||
    Object.prototype.hasOwnProperty.call(args, "catalogStrict")
  if (!hasCatalogStrict) return { hasCatalogStrict: false, value: null }
  const raw = args.catalog_strict ?? args.catalogStrict
  return { hasCatalogStrict: true, value: parseBooleanValue(raw) }
}

const notifyChanges = (summary: string, details: string[]) => {
  if (typeof window === "undefined") return
  const message = summary
  const description = details.join(" · ")
  if (!description) return
  staticNotification.info({
    message,
    description,
    duration: 2
  })
}

export const applyMcpModuleDisclosureFromToolCalls = (toolCalls?: ToolCall[]) => {
  if (!Array.isArray(toolCalls) || toolCalls.length === 0) return

  let candidateModules: string[] | null = null
  let candidateCatalogName: string | undefined
  let candidateCatalogId: number | undefined
  let hasCatalogName = false
  let hasCatalogId = false
  let candidateCatalogStrict: boolean | null = null
  let hasCatalogStrict = false

  for (const toolCall of toolCalls) {
    if (toolCall?.function?.name !== "mcp.tools.list") continue
    const args = parseToolArguments(toolCall)
    if (!args) continue
    const modules = extractModules(args)
    if (modules.length > 0) {
      candidateModules = modules
    }
    const catalog = extractCatalog(args)
    if (catalog.hasCatalogName) {
      candidateCatalogName = catalog.catalogName
      hasCatalogName = true
    }
    if (catalog.hasCatalogId) {
      candidateCatalogId = catalog.catalogId
      hasCatalogId = true
    }
    const strict = extractCatalogStrict(args)
    if (strict.hasCatalogStrict && strict.value !== null) {
      candidateCatalogStrict = strict.value
      hasCatalogStrict = true
    }
  }

  if (
    (!candidateModules || candidateModules.length === 0) &&
    !hasCatalogName &&
    !hasCatalogId &&
    !hasCatalogStrict
  ) {
    return
  }

  const store = useMcpToolsStore.getState()
  const normalizedCurrent = normalizeModuleList(store.toolModules)
  const changeDetails: string[] = []
  let didUpdate = false

  if (candidateModules && candidateModules.length > 0) {
    if (
      candidateModules.length !== normalizedCurrent.length ||
      !candidateModules.every((value, index) => value === normalizedCurrent[index])
    ) {
      store.setToolModules(candidateModules)
      void setSetting(MCP_TOOL_MODULE_SETTING, candidateModules)
      changeDetails.push(`Modules: ${candidateModules.join(", ")}`)
      didUpdate = true
    }
  }

  if (hasCatalogId) {
    if (store.toolCatalogId !== candidateCatalogId) {
      store.setToolCatalogId(candidateCatalogId ?? null)
      void setSetting(MCP_TOOL_CATALOG_ID_SETTING, candidateCatalogId ?? null)
      changeDetails.push(`Catalog ID: ${candidateCatalogId ?? "none"}`)
      didUpdate = true
    }
  }

  if (hasCatalogName) {
    const nextName = candidateCatalogName ?? ""
    if (store.toolCatalog !== nextName) {
      store.setToolCatalog(nextName)
      void setSetting(MCP_TOOL_CATALOG_SETTING, nextName)
      changeDetails.push(`Catalog: ${nextName || "none"}`)
      didUpdate = true
    }
    if (!hasCatalogId && store.toolCatalogId !== null) {
      store.setToolCatalogId(null)
      void setSetting(MCP_TOOL_CATALOG_ID_SETTING, null)
      changeDetails.push("Catalog ID: none")
      didUpdate = true
    }
  }

  if (hasCatalogStrict && candidateCatalogStrict !== null) {
    if (store.toolCatalogStrict !== candidateCatalogStrict) {
      store.setToolCatalogStrict(candidateCatalogStrict)
      void setSetting(MCP_TOOL_CATALOG_STRICT_SETTING, candidateCatalogStrict)
      changeDetails.push(`Strict: ${candidateCatalogStrict ? "on" : "off"}`)
      didUpdate = true
    }
  }

  if (didUpdate) {
    notifyChanges("MCP filters updated", changeDetails)
  }
}
