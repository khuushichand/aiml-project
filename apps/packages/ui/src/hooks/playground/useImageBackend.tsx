import React from "react"
import { useTranslation } from "react-i18next"
import { useStorage } from "@plasmohq/storage/hook"
import { getProviderDisplayName } from "@/utils/provider-registry"

export type ImageBackendOption = {
  value: string
  label: string
  provider?: string
}

export type UseImageBackendParams = {
  imageModels: any[]
}

export function useImageBackend({ imageModels }: UseImageBackendParams) {
  const { t } = useTranslation(["playground"])
  const [imageBackendDefault, setImageBackendDefault] = useStorage(
    "imageBackendDefault",
    ""
  )

  const imageBackendOptions = React.useMemo<ImageBackendOption[]>(() => {
    const dynamicOptions = (imageModels || [])
      .filter((model: any) => model && model.id)
      .map((model: any) => ({
        value: String(model.id),
        label: String(model.name || model.id),
        provider: model.provider ? String(model.provider) : undefined
      }))

    const fallbackOptions: ImageBackendOption[] = [
      {
        value: "tldw_server-Flux-Klein",
        label: t("playground:imageBackend.fluxKlein", "Flux-Klein"),
        provider: undefined
      },
      {
        value: "tldw_server-ZTurbo",
        label: t("playground:imageBackend.zTurbo", "ZTurbo"),
        provider: undefined
      }
    ]

    const baseOptions = dynamicOptions.length > 0 ? dynamicOptions : fallbackOptions
    return [
      {
        value: "",
        label: t("playground:imageBackend.none", "None")
      },
      ...baseOptions
    ]
  }, [imageModels, t])

  const imageBackendDefaultTrimmed = React.useMemo(
    () => (imageBackendDefault || "").trim(),
    [imageBackendDefault]
  )

  const imageBackendLabel = React.useMemo(() => {
    if (!imageBackendDefaultTrimmed) {
      return t("playground:imageBackend.none", "None")
    }
    const match = imageBackendOptions.find(
      (option) => option.value === imageBackendDefaultTrimmed
    )
    if (match?.provider) {
      return `${getProviderDisplayName(match.provider)} · ${match.label}`
    }
    return match?.label || imageBackendDefaultTrimmed
  }, [imageBackendDefaultTrimmed, imageBackendOptions, t])

  const imageBackendActiveKey =
    imageBackendDefaultTrimmed.length > 0 ? imageBackendDefaultTrimmed : "none"

  const imageBackendMenuItems = React.useMemo(
    () =>
      imageBackendOptions.map((option: any) => {
        const providerLabel = option.provider
          ? getProviderDisplayName(option.provider)
          : null
        const labelText = providerLabel
          ? `${providerLabel} · ${option.label}`
          : option.label
        return {
          key: option.value || "none",
          label: (
            <div className="flex items-center gap-2 text-sm">
              <span className="truncate">{labelText}</span>
            </div>
          ),
          onClick: () => setImageBackendDefault(option.value)
        }
      }),
    [imageBackendOptions, setImageBackendDefault]
  )

  const imageBackendBadgeLabel = imageBackendDefaultTrimmed
    ? t("playground:imageBackend.badge", "Image: {{backend}}", {
        backend: imageBackendLabel
      })
    : t("playground:imageBackend.noneBadge", "Image: none")

  return {
    imageBackendDefault: imageBackendDefaultTrimmed,
    setImageBackendDefault,
    imageBackendOptions,
    imageBackendLabel,
    imageBackendActiveKey,
    imageBackendMenuItems,
    imageBackendBadgeLabel
  }
}
