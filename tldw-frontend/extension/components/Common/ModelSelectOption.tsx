import { useQuery } from "@tanstack/react-query"
import { Avatar, Dropdown, Tooltip } from "antd"
import type { MenuProps } from "antd"
import { LucideBrain } from "lucide-react"
import React from "react"
import { useTranslation } from "react-i18next"
import { useStorage } from "@plasmohq/storage/hook"
import { fetchChatModels } from "@/services/tldw-server"
import { useMessageOption } from "~/hooks/useMessageOption"
import { getProviderDisplayName } from "@/utils/provider-registry"
import { ProviderIcons } from "./ProviderIcon"
import { IconButton } from "./IconButton"

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

  const groupedItems = React.useMemo(() => {
    const groups = new Map<string, MenuItem[]>()
    const localProviders = new Set(["lmstudio", "llamafile", "ollama", "ollama2", "llamacpp", "vllm", "custom"]) // group as "custom"
    for (const d of data || []) {
      const providerRaw = (d.provider || "other").toLowerCase()
      const groupKey =
        providerRaw === "chrome"
          ? "default"
          : (localProviders.has(providerRaw) ? "custom" : providerRaw)
      const labelNode = (
        <div className="w-52 gap-2 text-sm truncate inline-flex items-center leading-5">
          <div>
            {d.avatar ? (
              <Avatar src={d.avatar} alt={d.name} size="small" />
            ) : (
              <ProviderIcons provider={d?.provider} className="h-4 w-4 text-text-subtle" />
            )}
          </div>
          {d?.nickname || d.model}
        </div>
      )
      const item: MenuItem = {
        key: d.name,
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
    const items: MenuItem[] = []
    for (const [groupKey, children] of groups) {
      const labelText =
        groupKey === "default"
          ? "Default"
          : groupKey === "custom"
            ? "Custom"
            : getProviderDisplayName(groupKey)
      const iconKey = groupKey === "default" ? "chrome" : groupKey
      items.push({
        type: "group",
        key: `group-${groupKey}`,
        label: (
          <div className="flex items-center gap-1.5 text-xs leading-4 font-medium uppercase tracking-wider text-text-subtle">
            <ProviderIcons provider={iconKey} className="h-3 w-3" />
            <span>{labelText}</span>
          </div>
        ),
        children
      })
    }
    return items
  }, [data, selectedModel, setSelectedModel])

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
