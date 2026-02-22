import React from "react"
import { Button, Input } from "antd"
import { useStorage } from "@plasmohq/storage/hook"
import { useTranslation } from "react-i18next"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import {
  QUICK_CHAT_WORKFLOW_GUIDES,
  QUICK_CHAT_WORKFLOW_GUIDES_STORAGE_KEY,
  parseQuickChatWorkflowGuidesJson,
  resolveQuickChatWorkflowGuides,
  stringifyQuickChatWorkflowGuides
} from "@/components/Common/QuickChatHelper/workflow-guides"

const WORKFLOW_GUIDES_JSON_LABEL = "Quick Chat workflow cards JSON"

export const QuickChatWorkflowGuidesSettings: React.FC = () => {
  const { t } = useTranslation("settings")
  const notification = useAntdNotification()
  const [storedGuidesRaw, setStoredGuidesRaw] = useStorage<unknown>(
    QUICK_CHAT_WORKFLOW_GUIDES_STORAGE_KEY,
    QUICK_CHAT_WORKFLOW_GUIDES
  )
  const storedGuides = React.useMemo(
    () => resolveQuickChatWorkflowGuides(storedGuidesRaw),
    [storedGuidesRaw]
  )
  const [draft, setDraft] = React.useState(() =>
    stringifyQuickChatWorkflowGuides(storedGuides)
  )
  const [draftDirty, setDraftDirty] = React.useState(false)
  const [draftError, setDraftError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (draftDirty) return
    setDraft(stringifyQuickChatWorkflowGuides(storedGuides))
    setDraftError(null)
  }, [draftDirty, storedGuides])

  const handleDraftChange = React.useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      setDraft(event.target.value)
      setDraftDirty(true)
      setDraftError(null)
    },
    []
  )

  const handleDiscard = React.useCallback(() => {
    setDraft(stringifyQuickChatWorkflowGuides(storedGuides))
    setDraftDirty(false)
    setDraftError(null)
  }, [storedGuides])

  const handleSave = React.useCallback(() => {
    const parsed = parseQuickChatWorkflowGuidesJson(draft)
    if (!parsed.guides) {
      const errorText =
        parsed.error ||
        t(
          "generalSettings.settings.quickChatWorkflowGuides.invalidJson",
          "Workflow cards JSON is invalid."
        )
      setDraftError(errorText)
      notification.error({
        message: t(
          "generalSettings.settings.quickChatWorkflowGuides.saveFailed",
          "Could not save workflow cards"
        ),
        description: errorText
      })
      return
    }

    setStoredGuidesRaw(parsed.guides)
    setDraft(stringifyQuickChatWorkflowGuides(parsed.guides))
    setDraftDirty(false)
    setDraftError(null)
    notification.success({
      message: t(
        "generalSettings.settings.quickChatWorkflowGuides.saved",
        "Workflow cards saved"
      )
    })
  }, [draft, notification, setStoredGuidesRaw, t])

  const handleReset = React.useCallback(() => {
    setStoredGuidesRaw(QUICK_CHAT_WORKFLOW_GUIDES)
    setDraft(stringifyQuickChatWorkflowGuides(QUICK_CHAT_WORKFLOW_GUIDES))
    setDraftDirty(false)
    setDraftError(null)
    notification.info({
      message: t(
        "generalSettings.settings.quickChatWorkflowGuides.reset",
        "Workflow cards reset to defaults"
      )
    })
  }, [notification, setStoredGuidesRaw, t])

  return (
    <div className="rounded-md border border-border bg-surface2/40 p-3 space-y-3">
      <div>
        <p className="text-xs font-semibold text-text-muted">
          {t(
            "generalSettings.settings.quickChatWorkflowGuides.title",
            "Quick Chat workflow cards"
          )}
        </p>
        <p className="mt-1 text-xs text-text-muted">
          {t(
            "generalSettings.settings.quickChatWorkflowGuides.description",
            "Edit the pre-written Q/A cards used by Browse Guides and docs-mode route suggestions."
          )}
        </p>
      </div>

      <Input.TextArea
        rows={12}
        value={draft}
        onChange={handleDraftChange}
        aria-label={WORKFLOW_GUIDES_JSON_LABEL}
      />

      {draftError ? (
        <p className="text-xs text-danger">{draftError}</p>
      ) : (
        <p className="text-xs text-text-muted">
          {t(
            "generalSettings.settings.quickChatWorkflowGuides.hint",
            "JSON must be an array of cards with id, title, question, answer, route, routeLabel, and tags."
          )}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <Button
          type="primary"
          size="small"
          onClick={handleSave}
          disabled={!draftDirty}
        >
          {t(
            "generalSettings.settings.quickChatWorkflowGuides.saveButton",
            "Save workflow cards"
          )}
        </Button>
        <Button size="small" onClick={handleDiscard} disabled={!draftDirty}>
          {t(
            "generalSettings.settings.quickChatWorkflowGuides.discardButton",
            "Discard edits"
          )}
        </Button>
        <Button danger size="small" onClick={handleReset}>
          {t(
            "generalSettings.settings.quickChatWorkflowGuides.resetButton",
            "Reset to built-in defaults"
          )}
        </Button>
      </div>
    </div>
  )
}

export default QuickChatWorkflowGuidesSettings
