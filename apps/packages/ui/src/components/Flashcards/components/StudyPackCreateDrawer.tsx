import React from "react"
import { Button, Drawer, Input, Select, Space, Typography } from "antd"
import { Trash2 } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { useAntdMessage } from "@/hooks/useAntdMessage"
import type {
  StudyPackSourceSelection,
  StudyPackSourceType,
  StudyPackSummaryResponse
} from "@/services/flashcards"
import type { StudyPackIntent } from "@/services/tldw/study-pack-handoff"
import { useStudyPackCreateMutation, useStudyPackJobQuery } from "../hooks"

const { Text } = Typography

type StudyPackCreateDrawerProps = {
  open: boolean
  onClose: () => void
  initialIntent?: StudyPackIntent | null
  onCreated?: (pack: StudyPackSummaryResponse) => void
}

const DEFAULT_SOURCE_TYPE: StudyPackSourceType = "media"

const SOURCE_TYPE_OPTIONS: Array<{ label: string; value: StudyPackSourceType }> = [
  { label: "Media", value: "media" },
  { label: "Note", value: "note" },
  { label: "Message", value: "message" }
]

const normalizeIntentSources = (
  intent: StudyPackIntent | null | undefined
): StudyPackSourceSelection[] =>
  Array.isArray(intent?.sourceItems)
    ? intent.sourceItems.map((item) => ({
        source_type: item.sourceType,
        source_id: item.sourceId,
        source_title: item.sourceTitle
      }))
    : []

export const StudyPackCreateDrawer: React.FC<StudyPackCreateDrawerProps> = ({
  open,
  onClose,
  initialIntent,
  onCreated
}) => {
  const { t } = useTranslation(["option", "common"])
  const navigate = useNavigate()
  const message = useAntdMessage()
  const createMutation = useStudyPackCreateMutation()
  const handledTerminalJobIdRef = React.useRef<number | null>(null)

  const [title, setTitle] = React.useState("")
  const [sourceItems, setSourceItems] = React.useState<StudyPackSourceSelection[]>([])
  const [sourceType, setSourceType] = React.useState<StudyPackSourceType>(DEFAULT_SOURCE_TYPE)
  const [sourceId, setSourceId] = React.useState("")
  const [sourceTitle, setSourceTitle] = React.useState("")
  const [jobId, setJobId] = React.useState<number | null>(null)

  const jobQuery = useStudyPackJobQuery(jobId, {
    enabled: open && jobId != null
  })

  React.useEffect(() => {
    if (!open) return
    setTitle(initialIntent?.title ?? "")
    setSourceItems(normalizeIntentSources(initialIntent))
    setSourceType(DEFAULT_SOURCE_TYPE)
    setSourceId("")
    setSourceTitle("")
    setJobId(null)
    handledTerminalJobIdRef.current = null
  }, [initialIntent, open])

  React.useEffect(() => {
    const response = jobQuery.data
    if (!response) return
    if (handledTerminalJobIdRef.current === response.job.id) return

    if (response.job.status === "completed" && response.study_pack?.deck_id) {
      handledTerminalJobIdRef.current = response.job.id
      const pack = response.study_pack
      onCreated?.(pack)
      onClose()
      navigate(`/flashcards?tab=review&deck_id=${pack.deck_id}`, {
        replace: true
      })
      return
    }

    if (response.job.status === "failed" || response.job.status === "cancelled") {
      handledTerminalJobIdRef.current = response.job.id
      message.error(
        response.error ||
          t("option:flashcards.studyPackCreateFailed", {
            defaultValue: "Study pack generation failed."
          })
      )
      setJobId(null)
    }
  }, [jobQuery.data, message, navigate, onClose, onCreated, t])

  const trimmedTitle = title.trim()
  const trimmedSourceId = sourceId.trim()
  const trimmedSourceTitle = sourceTitle.trim()
  const canSubmit = trimmedTitle.length > 0 && sourceItems.length > 0 && !createMutation.isPending

  const handleAddSource = React.useCallback(() => {
    if (!trimmedSourceId) return

    setSourceItems((current) => [
      ...current,
      {
        source_type: sourceType,
        source_id: trimmedSourceId,
        source_title: trimmedSourceTitle || undefined
      }
    ])
    setSourceId("")
    setSourceTitle("")
  }, [sourceType, trimmedSourceId, trimmedSourceTitle])

  const handleRemoveSource = React.useCallback((index: number) => {
    setSourceItems((current) => current.filter((_, currentIndex) => currentIndex !== index))
  }, [])

  const handleSubmit = React.useCallback(async () => {
    if (!canSubmit) return

    const accepted = await createMutation.mutateAsync({
      title: trimmedTitle,
      source_items: sourceItems,
      deck_mode: "new"
    })
    setJobId(accepted.job.id)
  }, [canSubmit, createMutation, sourceItems, trimmedTitle])

  const drawerTitle = t("option:flashcards.studyPackDrawerTitle", {
    defaultValue: "Create study pack"
  })

  return (
    <Drawer
      open={open}
      title={drawerTitle}
      onClose={onClose}
      destroyOnClose
      size="large"
      footer={
        <Space>
          <Button onClick={onClose}>
            {t("common:cancel", { defaultValue: "Cancel" })}
          </Button>
          <Button
            type="primary"
            onClick={() => {
              void handleSubmit()
            }}
            disabled={!canSubmit}
            loading={createMutation.isPending || (jobId != null && jobQuery.isFetching)}
          >
            {t("option:flashcards.studyPackCreateButton", {
              defaultValue: "Create study pack"
            })}
          </Button>
        </Space>
      }
    >
      <div className="space-y-4">
        <div className="space-y-1">
          <Text strong>Title</Text>
          <Input
            aria-label="Title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder={t("option:flashcards.studyPackTitlePlaceholder", {
              defaultValue: "Study pack title"
            })}
          />
        </div>

        <div className="rounded border border-border bg-surface p-3">
          <div className="mb-3 flex items-center justify-between gap-2">
            <Text strong>
              {t("option:flashcards.studyPackSourcesLabel", {
                defaultValue: "Sources"
              })}
            </Text>
            <Text type="secondary">
              {t("option:flashcards.studyPackSourcesCount", {
                defaultValue: "{{count}} selected",
                count: sourceItems.length
              })}
            </Text>
          </div>

          <Space.Compact className="w-full">
            <Select
              aria-label="Source Type"
              value={sourceType}
              onChange={(value) => setSourceType(value)}
              options={SOURCE_TYPE_OPTIONS}
              className="min-w-[120px]"
            />
            <Input
              aria-label="Source ID"
              value={sourceId}
              onChange={(event) => setSourceId(event.target.value)}
              placeholder="Source ID"
            />
            <Input
              aria-label="Source Title"
              value={sourceTitle}
              onChange={(event) => setSourceTitle(event.target.value)}
              placeholder={t("option:flashcards.studyPackSourceTitlePlaceholder", {
                defaultValue: "Optional title"
              })}
            />
            <Button onClick={handleAddSource}>
              {t("common:add", { defaultValue: "Add source" })}
            </Button>
          </Space.Compact>

          <div className="mt-3 space-y-2">
            {sourceItems.length === 0 ? (
              <Text type="secondary">
                {t("option:flashcards.studyPackSourcesEmpty", {
                  defaultValue: "Add at least one supported source to create a study pack."
                })}
              </Text>
            ) : (
              sourceItems.map((item, index) => (
                <div
                  key={`${item.source_type}-${item.source_id}-${index}`}
                  className="flex items-start justify-between gap-3 rounded border border-border bg-background p-2"
                >
                  <div className="min-w-0">
                    <Text className="block">
                      {item.source_type} · {item.source_id}
                    </Text>
                    {item.source_title ? (
                      <Text type="secondary" className="block truncate">
                        {item.source_title}
                      </Text>
                    ) : null}
                  </div>
                  <Button
                    type="text"
                    aria-label={t("common:remove", { defaultValue: "Remove" })}
                    icon={<Trash2 className="size-4" />}
                    onClick={() => handleRemoveSource(index)}
                  />
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </Drawer>
  )
}

export default StudyPackCreateDrawer
