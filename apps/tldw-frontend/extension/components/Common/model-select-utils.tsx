import React from "react"
import { getProviderDisplayName } from "@/utils/provider-registry"
import { ProviderIcons } from "./ProviderIcon"

export const LOCAL_PROVIDERS = new Set([
  "lmstudio",
  "llamafile",
  "ollama",
  "ollama2",
  "llamacpp",
  "vllm",
  "custom"
])

export const normalizeProvider = (provider?: string): string => {
  if (typeof provider === "string" && provider.trim()) {
    return provider.trim()
  }
  return "other"
}

export const getModelGroupKey = (provider?: string): string => {
  const providerRaw = normalizeProvider(provider).toLowerCase()
  if (providerRaw === "chrome") return "default"
  return LOCAL_PROVIDERS.has(providerRaw) ? "custom" : providerRaw
}

export const getGroupLabel = (groupKey: string): string => {
  if (groupKey === "default") return "Default"
  if (groupKey === "custom") return "Custom"
  return getProviderDisplayName(groupKey)
}

export const getGroupIconKey = (groupKey: string): string =>
  groupKey === "default" ? "chrome" : groupKey

export const buildGroupLabelNode = (groupKey: string): React.ReactNode => (
  <div className="flex items-center gap-1.5 text-xs leading-4 font-medium uppercase tracking-wider text-text-subtle">
    <ProviderIcons provider={getGroupIconKey(groupKey)} className="h-3 w-3" />
    <span>{getGroupLabel(groupKey)}</span>
  </div>
)
