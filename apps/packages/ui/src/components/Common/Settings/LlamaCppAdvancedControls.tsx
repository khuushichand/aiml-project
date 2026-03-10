import React from "react"
import { Alert, Button, Input, InputNumber, Select, Typography } from "antd"
import { useQuery } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { useStoreChatModelSettings } from "@/store/model"
import { resolveApiProviderForModel } from "@/utils/resolve-api-provider"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import {
  tldwLlamaGrammars,
  type LlamaGrammarRecord
} from "@/services/tldw/TldwLlamaGrammars"
import { LlamaGrammarLibraryModal } from "./LlamaGrammarLibraryModal"

const { TextArea } = Input
const { Text } = Typography

type LlamaCppControlsMetadata = {
  grammar?: {
    supported?: boolean
    effective_reason?: string | null
  }
  thinking_budget?: {
    supported?: boolean
    request_key?: string | null
    effective_reason?: string | null
  }
  reserved_extra_body_keys?: string[]
}

type Props = {
  selectedModel?: string | null
  resolvedProvider?: string | null
  className?: string
}

const normalizeResolvedProvider = (value: string | null | undefined) => {
  const normalized = String(value || "").trim().toLowerCase()
  if (normalized === "llamacpp") return "llama.cpp"
  return normalized || null
}

const extractLlamaCppControls = (payload: any): LlamaCppControlsMetadata | null => {
  const providers = payload?.providers
  if (!providers) return null
  if (!Array.isArray(providers)) {
    return (
      providers?.["llama.cpp"]?.llama_cpp_controls ??
      providers?.llamacpp?.llama_cpp_controls ??
      null
    )
  }
  const matched = providers.find((entry: any) => {
    const key = String(entry?.provider || entry?.id || entry?.name || "")
      .trim()
      .toLowerCase()
    return key === "llama.cpp" || key === "llamacpp"
  })
  return matched?.llama_cpp_controls ?? null
}

export function LlamaCppAdvancedControls({
  selectedModel,
  resolvedProvider,
  className
}: Props) {
  const { t } = useTranslation(["common", "sidepanel"])
  const apiProviderOverride = useStoreChatModelSettings((state) => state.apiProvider)
  const updateSetting = useStoreChatModelSettings((state) => state.updateSetting)
  const thinkingBudget = useStoreChatModelSettings(
    (state) => state.llamaThinkingBudgetTokens
  )
  const grammarMode = useStoreChatModelSettings((state) => state.llamaGrammarMode)
  const grammarId = useStoreChatModelSettings((state) => state.llamaGrammarId)
  const grammarInline = useStoreChatModelSettings((state) => state.llamaGrammarInline)
  const grammarOverride = useStoreChatModelSettings(
    (state) => state.llamaGrammarOverride
  )
  const [libraryOpen, setLibraryOpen] = React.useState(false)
  const [derivedProvider, setDerivedProvider] = React.useState<string | null>(
    normalizeResolvedProvider(resolvedProvider)
  )

  React.useEffect(() => {
    const direct = normalizeResolvedProvider(resolvedProvider)
    if (direct) {
      setDerivedProvider(direct)
      return
    }

    let cancelled = false
    void resolveApiProviderForModel({
      modelId: selectedModel,
      explicitProvider: apiProviderOverride
    }).then((nextProvider) => {
      if (!cancelled) {
        setDerivedProvider(normalizeResolvedProvider(nextProvider))
      }
    })

    return () => {
      cancelled = true
    }
  }, [apiProviderOverride, resolvedProvider, selectedModel])

  const isLlamaCpp = derivedProvider === "llama.cpp"

  const providersQuery = useQuery({
    queryKey: ["tldw:llm-providers"],
    queryFn: () => tldwClient.getLlmProviders(),
    enabled: isLlamaCpp
  })

  const grammarsQuery = useQuery({
    queryKey: ["tldw:llama-grammars"],
    queryFn: () => tldwLlamaGrammars.list(),
    enabled: isLlamaCpp
  })

  if (!isLlamaCpp) {
    return null
  }

  const controls = extractLlamaCppControls(providersQuery.data)
  const grammarSupported = controls?.grammar?.supported !== false
  const thinkingSupported = controls?.thinking_budget?.supported === true
  const grammarOptions =
    grammarsQuery.data?.items?.map((item: LlamaGrammarRecord) => ({
      label: item.name,
      value: item.id
    })) ?? []

  return (
    <div className={className}>
      <div className="rounded-xl border border-border/70 bg-surface2/60 p-3 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="space-y-0.5">
            <Text strong>
              {t("sidepanel:llamaControls.title", "llama.cpp advanced controls")}
            </Text>
            <div className="text-xs text-text-muted">
              {t(
                "sidepanel:llamaControls.subtitle",
                "Grammar-constrained output and optional reasoning budget."
              )}
            </div>
          </div>
          <Button size="small" onClick={() => setLibraryOpen(true)}>
            {t("sidepanel:llamaControls.manageGrammars", "Manage grammars")}
          </Button>
        </div>

        {!grammarSupported && controls?.grammar?.effective_reason ? (
          <Alert
            type="info"
            showIcon
            message={controls.grammar.effective_reason}
          />
        ) : null}

        <div className="space-y-1">
          <label className="text-xs text-text-muted">
            {t("sidepanel:llamaControls.thinkingBudget", "Thinking budget")}
          </label>
          <InputNumber
            min={0}
            disabled={!thinkingSupported}
            value={thinkingBudget}
            onChange={(value) =>
              updateSetting(
                "llamaThinkingBudgetTokens",
                typeof value === "number" ? value : undefined
              )
            }
            className="w-full"
            placeholder={t(
              "sidepanel:llamaControls.thinkingBudgetPlaceholder",
              "Disabled for this deployment"
            )}
          />
          {!thinkingSupported && controls?.thinking_budget?.effective_reason ? (
            <div className="text-xs text-text-muted">
              {controls.thinking_budget.effective_reason}
            </div>
          ) : null}
        </div>

        <div className="space-y-1">
          <label className="text-xs text-text-muted">
            {t("sidepanel:llamaControls.grammarSource", "Grammar source")}
          </label>
          <Select
            value={grammarMode || "none"}
            onChange={(value: "none" | "library" | "inline") => {
              updateSetting("llamaGrammarMode", value === "none" ? undefined : value)
              if (value === "none") {
                updateSetting("llamaGrammarId", undefined)
                updateSetting("llamaGrammarInline", undefined)
                updateSetting("llamaGrammarOverride", undefined)
              }
              if (value === "inline") {
                updateSetting("llamaGrammarId", undefined)
              }
              if (value === "library") {
                updateSetting("llamaGrammarInline", undefined)
              }
            }}
            options={[
              { label: t("common:none", "None"), value: "none" },
              { label: t("sidepanel:llamaControls.savedGrammar", "Saved grammar"), value: "library" },
              { label: t("sidepanel:llamaControls.inlineGrammar", "Inline grammar"), value: "inline" }
            ]}
          />
        </div>

        {grammarMode === "library" ? (
          <div className="space-y-2">
            <Select
              value={grammarId}
              options={grammarOptions}
              onChange={(value) => updateSetting("llamaGrammarId", value)}
              placeholder={t(
                "sidepanel:llamaControls.selectSavedGrammar",
                "Select a saved grammar"
              )}
              loading={grammarsQuery.isLoading}
              allowClear
            />
            <TextArea
              value={grammarOverride || ""}
              onChange={(event) =>
                updateSetting(
                  "llamaGrammarOverride",
                  event.target.value || undefined
                )
              }
              rows={5}
              className="font-mono text-xs"
              placeholder={t(
                "sidepanel:llamaControls.overridePlaceholder",
                "Optional per-chat override"
              )}
            />
          </div>
        ) : null}

        {grammarMode === "inline" ? (
          <TextArea
            value={grammarInline || ""}
            onChange={(event) =>
              updateSetting(
                "llamaGrammarInline",
                event.target.value || undefined
              )
            }
            rows={8}
            className="font-mono text-xs"
            placeholder={'root ::= "ok"'}
          />
        ) : null}
      </div>

      <LlamaGrammarLibraryModal
        open={libraryOpen}
        onClose={() => setLibraryOpen(false)}
        selectedGrammarId={grammarId}
        onSelectGrammar={(grammar) => {
          updateSetting("llamaGrammarMode", "library")
          updateSetting("llamaGrammarId", grammar.id)
          setLibraryOpen(false)
        }}
      />
    </div>
  )
}
