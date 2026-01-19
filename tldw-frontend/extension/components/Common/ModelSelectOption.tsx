import { useQuery } from "@tanstack/react-query"
import { Avatar, Dropdown, Tooltip } from "antd"
import type { MenuProps } from "antd"
import { LucideBrain } from "lucide-react"
import React from "react"
import { useTranslation } from "react-i18next"
import { useStorage } from "@plasmohq/storage/hook"
import { fetchChatModels } from "@/services/tldw-server"
import { useMessageOption } from "~/hooks/useMessageOption"
import { ProviderIcons } from "./ProviderIcon"
import { IconButton } from "./IconButton"
import {
  buildGroupLabelNode,
  getModelGroupKey,
  normalizeProvider
} from "./model-select-utils"

type Props = {
  iconClassName?: string
}

type MenuItem = NonNullable<MenuProps["items"]>[number]

export const ModelSelectOption: React.FC<Props> = ({ iconClassName = "size-5" }) => {
  const { t } = useTranslation("common")
  const { setSelectedModel, selectedModel } = useMessageOption()
  const selectedModelValue = typeof selectedModel === "string" ? selectedModel : null
  const [menuDensity] = useStorage("menuDensity", "comfortable")
  const { data, isLoading, isError } = useQuery({
    queryKey: ["getAllModelsForSelectOption"],
    queryFn: () => fetchChatModels({ returnEmpty: false })
  })

  const handleModelClick = React.useCallback(
    (model: string) => {
      setSelectedModel((prev) => (prev === model ? null : model))
    },
    [setSelectedModel]
  )

  const groupedItems = React.useMemo(() => {
    const groups = new Map<string, MenuItem[]>()
    for (const d of data || []) {
      const normalizedProvider = normalizeProvider(d.provider)
      const groupKey = getModelGroupKey(normalizedProvider)
      const labelNode = (
        <div className="w-52 gap-2 text-sm truncate inline-flex items-center leading-5">
          <div>
            {d.avatar ? (
              <Avatar src={d.avatar} alt={d.name} size="small" />
            ) : (
              <ProviderIcons provider={normalizedProvider} className="h-4 w-4 text-text-subtle" />
            )}
          </div>
          {d?.nickname || d.model}
        </div>
      )
      const item: MenuItem = {
        key: d.model,
        label: labelNode,
        onClick: () => handleModelClick(d.model)
      }
      if (!groups.has(groupKey)) groups.set(groupKey, [])
      groups.get(groupKey)!.push(item)
    }
    const items: MenuItem[] = []
    for (const [groupKey, children] of groups) {
      items.push({
        type: "group",
        key: `group-${groupKey}`,
        label: buildGroupLabelNode(groupKey),
        children
      })
    }
    return items
  }, [data, handleModelClick])

  const hasModels = (data?.length ?? 0) > 0
  const showLoadingState = isLoading && !hasModels
  const showErrorState = isError && !hasModels
  const tooltipTitle = showLoadingState
    ? t("loadingModels", "Loading models...")
    : showErrorState
      ? t("failedToLoadModels", "Unable to load models")
      : t("selectAModel")

  if (!hasModels && !showLoadingState && !showErrorState) {
    return null
  }

  const button = (
    <Tooltip title={tooltipTitle}>
      <IconButton
        ariaLabel={tooltipTitle as string}
        hasPopup={hasModels ? "menu" : undefined}
        className="text-text-muted h-11 w-11 sm:h-7 sm:w-7 sm:min-w-0 sm:min-h-0"
        disabled={showLoadingState || showErrorState}
      >
        <LucideBrain className={iconClassName} />
      </IconButton>
    </Tooltip>
  )

  return (
    <>
      {hasModels ? (
        <Dropdown
          menu={{
            items: groupedItems,
            style: { maxHeight: 500, overflowY: "auto" },
            className: `no-scrollbar ${menuDensity === "compact" ? "menu-density-compact" : "menu-density-comfortable"}`,
            activeKey: selectedModelValue ?? undefined
          }}
          placement={"topLeft"}
          trigger={["click"]}
        >
          {button}
        </Dropdown>
      ) : (
        button
      )}
    </>
  )
}

export default ModelSelectOption
