import { useQuery } from "@tanstack/react-query"
import { Avatar, Dropdown, Tooltip } from "antd"
import type { MenuProps } from "antd"
import { Loader2, LucideBrain } from "lucide-react"
import React from "react"
import { useTranslation } from "react-i18next"
import { useStorage } from "@plasmohq/storage/hook"
import { fetchChatModels } from "@/services/tldw-server"
import { useMessage } from "@/hooks/useMessage"
import { getProviderDisplayName } from "@/utils/provider-registry"
import { ProviderIcons } from "./ProviderIcon"
import { IconButton } from "./IconButton"
import {
  buildGroupLabelNode,
  getModelGroupKey,
  normalizeProvider
} from "./model-select-utils"

type Props = {
  iconClassName?: string
  showSelectedName?: boolean
}

type MenuItem = NonNullable<MenuProps["items"]>[number]

type ChatModel = {
  model: string
  nickname?: string
  provider?: string
  details?: {
    capabilities?: string[]
  }
  avatar?: string
  name?: string
}

export const ModelSelect: React.FC<Props> = ({iconClassName = "size-5", showSelectedName = false}) => {
  const { t } = useTranslation("common")
  const { setSelectedModel, selectedModel } = useMessage()
  const [menuDensity] = useStorage("menuDensity", "comfortable")
  const { data, isLoading, isError } = useQuery<ChatModel[]>({
    queryKey: ["getAllModelsForSelect"],
    queryFn: () => fetchChatModels({ returnEmpty: false })
  })

  const hasModels = (data?.length ?? 0) > 0
  const showLoadingState = isLoading && !hasModels
  const showErrorState = isError && !hasModels
  const showEmptyState = !hasModels && !showLoadingState && !showErrorState

  const groupedItems = React.useMemo(() => {
    const groups = new Map<string, MenuItem[]>()
    for (const d of data || []) {
      const normalizedProvider = normalizeProvider(d.provider)
      const groupKey = getModelGroupKey(normalizedProvider)
      const providerLabel = getProviderDisplayName(normalizedProvider)
      const modelLabel = d.nickname || d.model
      const caps = Array.isArray(d.details?.capabilities)
        ? d.details.capabilities
        : []
      const hasVision = caps.includes("vision")
      const hasTools = caps.includes("tools")
      const hasFast = caps.includes("fast")

      const labelNode = (
        <div className="w-52 gap-2 text-sm truncate inline-flex items-center leading-5">
          <div>
            {d.avatar ? (
              <Avatar src={d.avatar} alt={d.name} size="small" />
            ) : (
              <ProviderIcons provider={normalizedProvider} className="h-4 w-4 text-text-subtle" />
            )}
          </div>
          <div className="flex flex-col min-w-0">
            <span className="truncate">
              {providerLabel} - {modelLabel}
            </span>
            {(hasVision || hasTools || hasFast) && (
              <div className="mt-0.5 flex flex-wrap gap-1 text-[10px]">
                {hasVision && (
                  <span className="rounded-full bg-primary/10 px-1.5 py-0.5 text-primary">
                    Vision
                  </span>
                )}
                {hasTools && (
                  <span className="rounded-full bg-accent/10 px-1.5 py-0.5 text-accent">
                    Tools
                  </span>
                )}
                {hasFast && (
                  <span className="rounded-full bg-success/10 px-1.5 py-0.5 text-success">
                    Fast
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      )
      const item: MenuItem = {
        key: d.model,
        label: labelNode,
        onClick: () => {
          if (selectedModel === d.model) {
            setSelectedModel(null)
          } else {
            setSelectedModel(d.model)
          }
        }
      }
      if (!groups.has(groupKey)) groups.set(groupKey, [])
      groups.get(groupKey)!.push(item)
    }
    // Build grouped menu items
    const items: MenuItem[] = []
    for (const [groupKey, children] of groups) {
      items.push({
        type: 'group',
        key: `group-${groupKey}`,
        label: buildGroupLabelNode(groupKey),
        children
      })
    }
    return items
  }, [data, selectedModel, setSelectedModel])

  // Get display name for selected model
  const selectedModelDisplay = React.useMemo(() => {
    if (!selectedModel || !data) return null
    const model = data.find(m => m.model === selectedModel)
    if (!model) return selectedModel.split('/').pop() || selectedModel
    // Use nickname if available, otherwise extract short name from model ID
    const shortName = model.nickname || model.model.split('/').pop() || model.model
    // Truncate if too long
    return shortName.length > 20 ? shortName.substring(0, 18) + '…' : shortName
  }, [selectedModel, data])

  const statusLabel = showLoadingState
    ? t("loadingModels", "Loading models...")
    : showErrorState
      ? t("failedToLoadModels", "Unable to load models")
      : showEmptyState
        ? t("noModelsAvailable", "No models available")
        : null

  const tooltipTitle = statusLabel
    ? statusLabel
    : selectedModel
      ? `${t("modelSelect.tooltip", "Changes model for next message")}: ${selectedModel}`
      : t("modelSelect.tooltip", "Changes model for next message")

  const buttonLabel = statusLabel ?? t("selectAModel", "Select a model")
  const button = (
    <Tooltip title={tooltipTitle}>
      <IconButton
        ariaLabel={buttonLabel as string}
        hasPopup={hasModels ? "menu" : undefined}
        dataTestId="chat-model-select"
        className="px-2 text-text-muted"
        disabled={showLoadingState || showErrorState || showEmptyState}>
        {showLoadingState ? (
          <Loader2 className={`${iconClassName} animate-spin`} />
        ) : (
          <LucideBrain className={iconClassName} />
        )}
        {statusLabel ? (
          <span className="ml-1.5 max-w-[160px] truncate text-xs font-medium text-text-muted">
            {statusLabel}
          </span>
        ) : showSelectedName && selectedModelDisplay ? (
          <span className="ml-1.5 max-w-[120px] truncate text-xs font-medium text-text">
            {selectedModelDisplay}
          </span>
        ) : (
          <span className="ml-1 hidden sm:inline text-xs">
            {t("modelSelect.label", "Model")}
          </span>
        )}
      </IconButton>
    </Tooltip>
  )

  return (
    <>
      {hasModels ? (
        <Dropdown
          menu={{
            items: groupedItems,
            style: {
              maxHeight: 500,
              overflowY: "auto"
            },
            className: `no-scrollbar ${menuDensity === 'compact' ? 'menu-density-compact' : 'menu-density-comfortable'}`,
            activeKey: selectedModel ?? undefined
          }}
          placement={"topLeft"}
          trigger={["click"]}>
          {button}
        </Dropdown>
      ) : (
        button
      )}
    </>
  )
}
