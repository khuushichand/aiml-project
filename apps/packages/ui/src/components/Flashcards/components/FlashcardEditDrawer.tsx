import React from "react"
import {
  Badge,
  Button,
  Collapse,
  Drawer,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Tooltip,
  Typography
} from "antd"
import dayjs from "dayjs"
import relativeTime from "dayjs/plugin/relativeTime"
import { useTranslation } from "react-i18next"
import { useDebouncedFormField } from "../hooks"
import { FLASHCARDS_DRAWER_WIDTH_PX } from "../constants"
import { normalizeFlashcardTemplateFields } from "../utils/template-helpers"
import { MarkdownWithBoundary } from "./MarkdownWithBoundary"
import type { Flashcard, FlashcardUpdate, Deck } from "@/services/flashcards"

const { Text } = Typography
dayjs.extend(relativeTime)
const CLOZE_PATTERN = /\{\{c\d+::[\s\S]+?\}\}/

type FlashcardModelType = Flashcard["model_type"]

interface FlashcardEditDrawerProps {
  open: boolean
  onClose: () => void
  card: Flashcard | null
  onSave: (values: FlashcardUpdate) => Promise<void>
  onDelete: () => void
  onResetScheduling?: () => Promise<void>
  isLoading?: boolean
  decks: Deck[]
  decksLoading?: boolean
}

export const FlashcardEditDrawer: React.FC<FlashcardEditDrawerProps> = ({
  open,
  onClose,
  card,
  onSave,
  onDelete,
  onResetScheduling,
  isLoading = false,
  decks,
  decksLoading = false
}) => {
  const { t } = useTranslation(["option", "common"])
  const [form] = Form.useForm<FlashcardUpdate & { tags_text?: string[] }>()
  const selectedModelType = Form.useWatch("model_type", form) as
    | FlashcardModelType
    | undefined
  const [showPreview, setShowPreview] = React.useState(false)
  const [isDirty, setIsDirty] = React.useState(false)
  const [confirmCloseOpen, setConfirmCloseOpen] = React.useState(false)
  const [confirmResetOpen, setConfirmResetOpen] = React.useState(false)

  const frontPreview = useDebouncedFormField(form, "front")
  const backPreview = useDebouncedFormField(form, "back")
  const extraPreview = useDebouncedFormField(form, "extra")
  const notesPreview = useDebouncedFormField(form, "notes")

  const previewLabel = t("option:flashcards.preview", { defaultValue: "Preview" })
  const markdownSupportHint = t("option:flashcards.markdownSupportHint", {
    defaultValue: "Supports Markdown and LaTeX."
  })
  const isClozeTemplate = selectedModelType === "cloze"

  const templateHelperText = React.useMemo(() => {
    if (selectedModelType === "basic_reverse") {
      return t("option:flashcards.templateReverseHelp", {
        defaultValue:
          "Choose Basic + Reverse when you want both directions (term -> meaning and meaning -> term)."
      })
    }
    if (selectedModelType === "cloze") {
      return t("option:flashcards.templateClozeHelp", {
        defaultValue:
          "Choose Cloze when you want to hide key words inside a sentence or paragraph."
      })
    }
    return t("option:flashcards.templateBasicHelp", {
      defaultValue:
        "Choose Basic for direct question and answer cards (facts, definitions, short prompts)."
    })
  }, [selectedModelType, t])

  // Count how many additional fields have values for the badge indicator
  const additionalFieldCount = React.useMemo(() => {
    let count = 0
    if (extraPreview && extraPreview.trim()) count++
    if (notesPreview && notesPreview.trim()) count++
    return count
  }, [extraPreview, notesPreview])

  // Sync form with card data when card changes
  React.useEffect(() => {
    if (card && open) {
      form.setFieldsValue({
        deck_id: card.deck_id ?? undefined,
        front: card.front,
        back: card.back,
        notes: card.notes || undefined,
        extra: card.extra || undefined,
        tags: card.tags || undefined,
        model_type: card.model_type,
        expected_version: card.version
      })
      setIsDirty(false)
    }
  }, [card, open, form])

  // Track form changes
  const handleFormChange = React.useCallback(() => {
    setIsDirty(true)
  }, [])

  const syncTemplateFields = React.useCallback(
    (partial: Partial<Pick<FlashcardUpdate, "model_type" | "reverse" | "is_cloze">>) => {
      const normalized = normalizeFlashcardTemplateFields(partial)
      form.setFieldsValue({
        model_type: normalized.model_type,
        reverse: normalized.reverse,
        is_cloze: normalized.is_cloze
      })
    },
    [form]
  )

  const handleSave = async () => {
    try {
      const values = normalizeFlashcardTemplateFields(
        (await form.validateFields()) as FlashcardUpdate
      )
      await onSave(values)
    } catch (e: any) {
      // Validation errors handled by form
      if (!e?.errorFields) {
        console.error("Save error:", e)
      }
    }
  }

  const handleClose = React.useCallback(() => {
    form.resetFields()
    setIsDirty(false)
    setConfirmCloseOpen(false)
    setConfirmResetOpen(false)
    onClose()
  }, [form, onClose])

  const handleAttemptClose = React.useCallback(() => {
    if (isDirty) {
      setConfirmCloseOpen(true)
    } else {
      handleClose()
    }
  }, [handleClose, isDirty])

  const handleConfirmResetScheduling = React.useCallback(async () => {
    if (!onResetScheduling) return
    try {
      await onResetScheduling()
      setConfirmResetOpen(false)
      setIsDirty(false)
    } catch (e: unknown) {
      console.error("Reset scheduling error:", e)
    }
  }, [onResetScheduling])

  return (
    <>
    <Drawer
      placement="right"
      styles={{ wrapper: { width: FLASHCARDS_DRAWER_WIDTH_PX } }}
      open={open}
      onClose={handleAttemptClose}
      title={t("option:flashcards.editCard", { defaultValue: "Edit Flashcard" })}
      footer={
        <div className="flex justify-end">
          <Space>
            <Button onClick={handleAttemptClose}>
              {t("common:cancel", { defaultValue: "Cancel" })}
            </Button>
            <Button danger onClick={onDelete}>
              {t("common:delete", { defaultValue: "Delete" })}
            </Button>
            <Button type="primary" loading={isLoading} onClick={handleSave}>
              {t("common:save", { defaultValue: "Save" })}
            </Button>
          </Space>
        </div>
      }
    >
      <Form form={form} layout="vertical" onValuesChange={handleFormChange}>
        {/* Section: Organization */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-text-muted mb-3">
            {t("option:flashcards.organization", { defaultValue: "Organization" })}
          </h3>
          <Form.Item
            name="deck_id"
            label={t("option:flashcards.deck", { defaultValue: "Deck" })}
          >
            <Select
              allowClear
              loading={decksLoading}
              placeholder={t("option:flashcards.selectDeck", {
                defaultValue: "Select deck"
              })}
              options={decks.map((d) => ({
                label: d.name,
                value: d.id
              }))}
            />
          </Form.Item>
          <Form.Item
            name="model_type"
            label={t("option:flashcards.modelType", {
              defaultValue: "Card template"
            })}
          >
            <Select
              options={[
                {
                  label: t("option:flashcards.templateBasic", {
                    defaultValue: "Basic (Question - Answer)"
                  }),
                  value: "basic"
                },
                {
                  label: t("option:flashcards.templateReverse", {
                    defaultValue: "Basic + Reverse (Both directions)"
                  }),
                  value: "basic_reverse"
                },
                {
                  label: t("option:flashcards.templateCloze", {
                    defaultValue: "Cloze (Fill in the blank)"
                  }),
                  value: "cloze"
                }
              ]}
              onChange={(value: FlashcardModelType) => {
                syncTemplateFields({ model_type: value })
              }}
            />
          </Form.Item>
          <Text type="secondary" className="block text-[11px] -mt-4 mb-3">
            {templateHelperText}
          </Text>
          {isClozeTemplate && (
            <Text type="secondary" className="block text-[11px] -mt-2 mb-3">
              {t("option:flashcards.clozeSyntaxHelp", {
                defaultValue:
                  "Cloze syntax: add at least one deletion like {{syntax}} in Front text.",
                syntax: "{{c1::answer}}"
              })}
            </Text>
          )}
          <Form.Item
            name="tags"
            label={t("option:flashcards.tags", { defaultValue: "Tags" })}
          >
            <Select
              mode="tags"
              open={false}
              allowClear
              placeholder={t("option:flashcards.tagsPlaceholder", {
                defaultValue: "Add tags..."
              })}
            />
          </Form.Item>
        </div>

        {/* Section: Scheduling (read-only metadata) */}
        {card && (
          <div className="mb-6 rounded border border-border bg-surface p-3">
            <h3 className="text-sm font-medium text-text-muted mb-3">
              {t("option:flashcards.scheduling", { defaultValue: "Scheduling" })}
            </h3>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <Text type="secondary" className="block text-[11px]">
                  <Tooltip
                    title={t("option:flashcards.schedulingMemoryStrengthHelp", {
                      defaultValue: "SM-2 ease factor (how fast review gaps grow)."
                    })}
                  >
                    <span>
                      {t("option:flashcards.memoryStrength", {
                        defaultValue: "Memory strength"
                      })}
                    </span>
                  </Tooltip>
                </Text>
                <Text>{card.ef.toFixed(2)}</Text>
              </div>
              <div>
                <Text type="secondary" className="block text-[11px]">
                  <Tooltip
                    title={t("option:flashcards.schedulingNextGapHelp", {
                      defaultValue: "SM-2 interval (days until next review)."
                    })}
                  >
                    <span>
                      {t("option:flashcards.nextReviewGap", {
                        defaultValue: "Next review gap"
                      })}
                    </span>
                  </Tooltip>
                </Text>
                <Text>
                  {t("option:flashcards.intervalDaysShort", {
                    defaultValue: "{{count}}d",
                    count: Math.max(0, card.interval_days)
                  })}
                </Text>
              </div>
              <div>
                <Text type="secondary" className="block text-[11px]">
                  <Tooltip
                    title={t("option:flashcards.schedulingRecallRunsHelp", {
                      defaultValue: "SM-2 repetitions (successful recalls)."
                    })}
                  >
                    <span>
                      {t("option:flashcards.recallRuns", {
                        defaultValue: "Recall runs"
                      })}
                    </span>
                  </Tooltip>
                </Text>
                <Text>{Math.max(0, card.repetitions)}</Text>
              </div>
              <div>
                <Text type="secondary" className="block text-[11px]">
                  <Tooltip
                    title={t("option:flashcards.schedulingRelearnsHelp", {
                      defaultValue: "SM-2 lapses (times forgotten)."
                    })}
                  >
                    <span>
                      {t("option:flashcards.relearns", {
                        defaultValue: "Relearns"
                      })}
                    </span>
                  </Tooltip>
                </Text>
                <Text>{Math.max(0, card.lapses)}</Text>
              </div>
            </div>

            <div className="mt-3 space-y-2 text-xs">
              <div>
                <Text type="secondary" className="block text-[11px]">
                  {t("option:flashcards.dueAt", { defaultValue: "Due at" })}
                </Text>
                <Text>
                  {card.due_at
                    ? t("option:flashcards.timestampWithRelative", {
                        defaultValue: "{{absolute}} ({{relative}})",
                        absolute: dayjs(card.due_at).format("YYYY-MM-DD HH:mm"),
                        relative: dayjs(card.due_at).fromNow()
                      })
                    : t("option:flashcards.notScheduled", {
                        defaultValue: "Not scheduled"
                      })}
                </Text>
              </div>
              <div>
                <Text type="secondary" className="block text-[11px]">
                  {t("option:flashcards.lastReviewed", { defaultValue: "Last reviewed" })}
                </Text>
                <Text>
                  {card.last_reviewed_at
                    ? t("option:flashcards.timestampWithRelative", {
                        defaultValue: "{{absolute}} ({{relative}})",
                        absolute: dayjs(card.last_reviewed_at).format("YYYY-MM-DD HH:mm"),
                        relative: dayjs(card.last_reviewed_at).fromNow()
                      })
                    : t("option:flashcards.neverReviewed", {
                        defaultValue: "Never"
                      })}
                </Text>
              </div>
            </div>

            {onResetScheduling && (
              <div className="mt-3 border-t border-border pt-3">
                <Text type="secondary" className="block text-[11px] mb-2">
                  {t("option:flashcards.resetSchedulingHelp", {
                    defaultValue:
                      "Reset scheduling when this card's timing feels wrong. This keeps card content but starts scheduling from new-card defaults."
                  })}
                </Text>
                <Button
                  danger
                  size="small"
                  onClick={() => setConfirmResetOpen(true)}
                  disabled={isLoading}
                >
                  {t("option:flashcards.resetScheduling", {
                    defaultValue: "Reset scheduling"
                  })}
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Section: Content */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-text-muted">
              {t("option:flashcards.content", { defaultValue: "Content" })}
            </h3>
            <button
              type="button"
              className="text-xs text-primary hover:underline"
              onClick={() => setShowPreview(!showPreview)}
            >
              {showPreview
                ? t("option:flashcards.hidePreview", { defaultValue: "Hide preview" })
                : t("option:flashcards.showPreview", { defaultValue: "Show preview" })}
            </button>
          </div>
          <Form.Item
            name="front"
            label={t("option:flashcards.front", { defaultValue: "Front" })}
            rules={[
              {
                required: true,
                message: t("option:flashcards.frontRequired", {
                  defaultValue: "Front is required."
                })
              },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (getFieldValue("model_type") !== "cloze") {
                    return Promise.resolve()
                  }
                  const frontText = String(value ?? "")
                  if (CLOZE_PATTERN.test(frontText)) {
                    return Promise.resolve()
                  }
                  return Promise.reject(
                    new Error(
                      t("option:flashcards.clozeValidationMessage", {
                        defaultValue:
                          "For Cloze cards, include at least one deletion like {{syntax}}.",
                        syntax: "{{c1::answer}}"
                      })
                    )
                  )
                }
              })
            ]}
          >
            <Input.TextArea rows={3} />
          </Form.Item>
          <Text type="secondary" className="block text-[11px] -mt-4 mb-3">
            {markdownSupportHint}
          </Text>
          {showPreview && frontPreview && (
            <div className="mb-4 border rounded p-2 text-xs bg-surface">
              <Text type="secondary" className="block text-[11px] mb-1">
                {previewLabel}
              </Text>
              <MarkdownWithBoundary content={frontPreview || ""} size="xs" />
            </div>
          )}

          <Form.Item
            name="back"
            label={t("option:flashcards.back", { defaultValue: "Back" })}
            rules={[{ required: true }]}
          >
            <Input.TextArea rows={5} />
          </Form.Item>
          <Text type="secondary" className="block text-[11px] -mt-4 mb-3">
            {markdownSupportHint}
          </Text>
          {showPreview && backPreview && (
            <div className="mb-4 border rounded p-2 text-xs bg-surface">
              <Text type="secondary" className="block text-[11px] mb-1">
                {previewLabel}
              </Text>
              <MarkdownWithBoundary content={backPreview || ""} size="xs" />
            </div>
          )}
        </div>

        {/* Section: Additional (collapsed) */}
        <Collapse ghost>
          <Collapse.Panel
            header={
              <span className="inline-flex items-center gap-2">
                {t("option:flashcards.additionalFields", {
                  defaultValue: "Additional fields"
                })}
                {additionalFieldCount > 0 && (
                  <Badge
                    count={additionalFieldCount}
                    size="small"
                    title={t("option:flashcards.additionalFieldsSet", {
                      defaultValue: "{{count}} field(s) set",
                      count: additionalFieldCount
                    })}
                  />
                )}
              </span>
            }
            key="additional"
          >
            <Form.Item
              name="extra"
              label={t("option:flashcards.extra", { defaultValue: "Extra" })}
            >
              <Input.TextArea rows={2} />
            </Form.Item>
            {showPreview && extraPreview && (
              <div className="mb-4 border rounded p-2 text-xs bg-surface">
                <MarkdownWithBoundary content={extraPreview || ""} size="xs" />
              </div>
            )}
            <Form.Item
              name="notes"
              label={t("option:flashcards.notes", { defaultValue: "Notes" })}
            >
              <Input.TextArea rows={2} />
            </Form.Item>
            {showPreview && notesPreview && (
              <div className="mb-4 border rounded p-2 text-xs bg-surface">
                <MarkdownWithBoundary content={notesPreview || ""} size="xs" />
              </div>
            )}
          </Collapse.Panel>
        </Collapse>

        {/* Hidden fields */}
        <Form.Item name="expected_version" hidden>
          <Input type="number" />
        </Form.Item>
        <Form.Item name="reverse" hidden>
          <Input />
        </Form.Item>
        <Form.Item name="is_cloze" hidden>
          <Input />
        </Form.Item>
      </Form>
    </Drawer>

    {/* Confirmation modal for unsaved changes */}
    <Modal
      open={confirmCloseOpen}
      title={t("option:flashcards.unsavedChangesTitle", {
        defaultValue: "Unsaved changes"
      })}
      onCancel={() => setConfirmCloseOpen(false)}
      footer={[
        <Button key="cancel" onClick={() => setConfirmCloseOpen(false)}>
          {t("common:cancel", { defaultValue: "Cancel" })}
        </Button>,
        <Button key="discard" danger onClick={handleClose}>
          {t("common:discard", { defaultValue: "Discard" })}
        </Button>
      ]}
    >
      <p>
        {t("option:flashcards.unsavedChangesDescription", {
          defaultValue: "You have unsaved changes. Are you sure you want to close?"
        })}
      </p>
    </Modal>

    <Modal
      open={confirmResetOpen}
      title={t("option:flashcards.resetSchedulingConfirmTitle", {
        defaultValue: "Reset scheduling for this card?"
      })}
      onCancel={() => setConfirmResetOpen(false)}
      footer={[
        <Button key="cancel" onClick={() => setConfirmResetOpen(false)}>
          {t("common:cancel", { defaultValue: "Cancel" })}
        </Button>,
        <Button
          key="reset"
          danger
          loading={isLoading}
          onClick={handleConfirmResetScheduling}
        >
          {t("option:flashcards.resetScheduling", {
            defaultValue: "Reset scheduling"
          })}
        </Button>
      ]}
    >
      <p>
        {t("option:flashcards.resetSchedulingConfirmDescription", {
          defaultValue:
            "This will reset memory strength, next review gap, recall runs, and relearns to new-card defaults. Card content and tags will not change."
        })}
      </p>
    </Modal>
    </>
  )
}

export default FlashcardEditDrawer
