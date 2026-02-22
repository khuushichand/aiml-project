import React from "react"
import { useStorage } from "@plasmohq/storage/hook"
import { Button, InputNumber, Switch, Tag } from "antd"
import { useTranslation } from "react-i18next"
import { useKnowledgeSettings } from "@/components/Knowledge/hooks"
import { SettingsTab } from "@/components/Knowledge/SettingsTab"

const DEFAULT_MAX_WEBSITE_CONTEXT = 7028
const MIN_MAX_WEBSITE_CONTEXT = 256
const MAX_MAX_WEBSITE_CONTEXT = 32768

export const RagSettings = () => {
  const { t } = useTranslation(["settings", "sidepanel", "common"])
  const settings = useKnowledgeSettings()
  const [chatWithWebsiteEmbedding, setChatWithWebsiteEmbedding] = useStorage(
    "chatWithWebsiteEmbedding",
    false
  )
  const [maxWebsiteContext, setMaxWebsiteContext] = useStorage(
    "maxWebsiteContext",
    DEFAULT_MAX_WEBSITE_CONTEXT
  )
  const resolvedMaxWebsiteContext =
    typeof maxWebsiteContext === "number" &&
    Number.isFinite(maxWebsiteContext)
      ? maxWebsiteContext
      : DEFAULT_MAX_WEBSITE_CONTEXT

  const handleSaveDefaults = React.useCallback(() => {
    settings.applySettings()
  }, [settings])

  const handleMaxWebsiteContextChange = React.useCallback(
    (value: number | null) => {
      if (typeof value !== "number" || !Number.isFinite(value)) return
      const normalized = Math.max(
        MIN_MAX_WEBSITE_CONTEXT,
        Math.min(MAX_MAX_WEBSITE_CONTEXT, Math.round(value))
      )
      setMaxWebsiteContext(normalized)
    },
    [setMaxWebsiteContext]
  )

  return (
    <div className="flex flex-col space-y-6 text-sm">
      <div>
        <h2 className="text-base font-semibold leading-7 text-text">
          {t("rag.title", "RAG settings")}
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          {t(
            "rag.defaultsDescription",
            "Set default retrieval and generation behavior used by Knowledge QA and chat RAG."
          )}
        </p>
        <div className="border-b border-border mt-3" />
      </div>

      <div className="rounded-lg border border-border bg-surface overflow-hidden">
        <div className="px-4 py-3 space-y-3">
          <h3 className="text-sm font-semibold text-text">
            {t("rag.defaultProfileTitle", "Default RAG profile")}
          </h3>
          <p className="text-xs text-text-muted">
            {t(
              "rag.defaultProfileDescription",
              "These defaults are shared across Knowledge QA and chat RAG requests."
            )}
          </p>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <span className="text-text">
              {t("sidepanel:rag.useCurrentMessage", "Use current message")}
            </span>
            <Switch
              checked={settings.useCurrentMessage}
              onChange={settings.setUseCurrentMessage}
              aria-label={t(
                "sidepanel:rag.useCurrentMessage",
                "Use current message"
              )}
            />
          </div>
        </div>

        <div
          className="border-t border-border"
          style={{ height: "min(70vh, 42rem)" }}
        >
          <SettingsTab
            settings={settings.draftSettings}
            preset={settings.preset}
            searchFilter={settings.advancedSearch}
            onSearchFilterChange={settings.setAdvancedSearch}
            onUpdate={settings.updateSetting}
            onPresetChange={settings.applyPreset}
            onResetToBalanced={settings.resetToBalanced}
          />
        </div>

        <div className="flex justify-end gap-2 border-t border-border px-4 py-3 bg-surface">
          <Button onClick={settings.discardChanges} disabled={!settings.isDirty}>
            {t("common:cancel", "Discard")}
          </Button>
          <Button
            type="primary"
            onClick={handleSaveDefaults}
            disabled={!settings.isDirty}
          >
            {t("rag.saveDefaults", "Save defaults")}
          </Button>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-surface p-4 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-text">
            {t("rag.chatContextTitle", "Chat RAG context")}
          </h3>
          <p className="text-xs text-text-muted">
            {t(
              "rag.chatContextDescription",
              "These toggles control page-context retrieval behavior for chat."
            )}
          </p>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <span className="text-text">
            {t(
              "generalSettings.sidepanelRag.ragEnabled.label",
              "Enable Embedding and Retrieval"
            )}
          </span>
          <Switch
            checked={chatWithWebsiteEmbedding}
            onChange={(checked) => setChatWithWebsiteEmbedding(checked)}
            aria-label={t(
              "generalSettings.sidepanelRag.ragEnabled.label",
              "Enable Embedding and Retrieval"
            )}
          />
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="inline-flex items-center gap-2">
            <span className="text-text">
              {t(
                "generalSettings.sidepanelRag.maxWebsiteContext.label",
                "Maximum Content Size for Full Context Mode"
              )}
            </span>
            {resolvedMaxWebsiteContext === DEFAULT_MAX_WEBSITE_CONTEXT ? (
              <Tag className="text-[10px] py-0 px-1.5 leading-4">
                {t("generalSettings.settings.defaultBadge", "default")}
              </Tag>
            ) : null}
          </div>

          <div className="flex items-center gap-2">
            <InputNumber
              value={resolvedMaxWebsiteContext}
              min={MIN_MAX_WEBSITE_CONTEXT}
              max={MAX_MAX_WEBSITE_CONTEXT}
              disabled={!chatWithWebsiteEmbedding}
              onChange={handleMaxWebsiteContextChange}
              placeholder={t(
                "generalSettings.sidepanelRag.maxWebsiteContext.placeholder",
                "Content size"
              )}
              aria-label={t(
                "generalSettings.sidepanelRag.maxWebsiteContext.label",
                "Maximum Content Size for Full Context Mode"
              )}
            />
            <Button
              onClick={() => setMaxWebsiteContext(DEFAULT_MAX_WEBSITE_CONTEXT)}
              disabled={resolvedMaxWebsiteContext === DEFAULT_MAX_WEBSITE_CONTEXT}
            >
              {t("sidepanel:rag.reset", "Reset")}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
