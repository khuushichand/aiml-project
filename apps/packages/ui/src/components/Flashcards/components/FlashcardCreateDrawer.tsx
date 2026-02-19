import React from "react"
import {
  Badge,
  Button,
  Collapse,
  Divider,
  Drawer,
  Form,
  Input,
  Select,
  Space,
  Typography
} from "antd"
import { Plus } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useAntdMessage } from "@/hooks/useAntdMessage"
import {
  useDecksQuery,
  useCreateFlashcardMutation,
  useCreateDeckMutation,
  useDebouncedFormField
} from "../hooks"
import { FLASHCARDS_DRAWER_WIDTH_PX } from "../constants"
import { MarkdownWithBoundary } from "./MarkdownWithBoundary"
import { normalizeFlashcardTemplateFields } from "../utils/template-helpers"
import {
  FLASHCARD_FIELD_MAX_BYTES,
  getFlashcardFieldLimitState,
  getUtf8ByteLength
} from "../utils/field-byte-limit"
import type { FlashcardCreate, Deck } from "@/services/flashcards"

const { Text } = Typography
const CLOZE_PATTERN = /\{\{c\d+::[\s\S]+?\}\}/
type FlashcardModelType = NonNullable<FlashcardCreate["model_type"]>

interface PreviewProps {
  content?: string
  showPreview: boolean
}

const Preview: React.FC<PreviewProps> = ({ content, showPreview }) => {
  const { t } = useTranslation(["option"])
  if (!showPreview || !content) return null
  return (
    <div className="mt-2 rounded border border-border bg-surface p-2 text-xs">
      <Text type="secondary" className="block text-[11px] mb-1">
        {t("flashcards.preview", { defaultValue: "Preview" })}
      </Text>
      <MarkdownWithBoundary content={content} size="xs" />
    </div>
  )
}

interface FlashcardCreateDrawerProps {
  open: boolean
  onClose: () => void
  decks?: Deck[]
  decksLoading?: boolean
  onSuccess?: () => void
}

export const FlashcardCreateDrawer: React.FC<FlashcardCreateDrawerProps> = ({
  open,
  onClose,
  decks: propDecks,
  decksLoading: propDecksLoading,
  onSuccess
}) => {
  const { t } = useTranslation(["option", "common"])
  const message = useAntdMessage()

  // Form and state
  const [form] = Form.useForm<FlashcardCreate>()
  const selectedModelType = Form.useWatch("model_type", form) as
    | FlashcardModelType
    | undefined
  const [showPreview, setShowPreview] = React.useState(false)
  const frontPreview = useDebouncedFormField(form, "front")
  const backPreview = useDebouncedFormField(form, "back")
  const extraPreview = useDebouncedFormField(form, "extra")
  const notesPreview = useDebouncedFormField(form, "notes")
  const tagsValue = useDebouncedFormField(form, "tags")
  const frontValue = Form.useWatch("front", form) as string | undefined
  const backValue = Form.useWatch("back", form) as string | undefined

  // Count how many advanced fields have values for the badge indicator
  const advancedFieldCount = React.useMemo(() => {
    let count = 0
    if (Array.isArray(tagsValue) && tagsValue.length > 0) count++
    if (extraPreview && extraPreview.trim()) count++
    if (notesPreview && notesPreview.trim()) count++
    return count
  }, [tagsValue, extraPreview, notesPreview])

  // Inline deck creation state
  const [showInlineCreate, setShowInlineCreate] = React.useState(false)
  const [inlineDeckName, setInlineDeckName] = React.useState("")

  // Queries and mutations - use props if provided, otherwise fetch
  const decksQuery = useDecksQuery({ enabled: !propDecks })
  const decks = propDecks ?? decksQuery.data ?? []
  const decksLoading = propDecksLoading ?? decksQuery.isLoading

  const createMutation = useCreateFlashcardMutation()
  const createDeckMutation = useCreateDeckMutation()
  const isClozeTemplate = selectedModelType === "cloze"
  const frontByteLength = getUtf8ByteLength(frontValue)
  const backByteLength = getUtf8ByteLength(backValue)
  const frontLimitState = getFlashcardFieldLimitState(frontByteLength)
  const backLimitState = getFlashcardFieldLimitState(backByteLength)

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

  const renderByteUsageHint = React.useCallback(
    (field: "front" | "back", byteLength: number, state: "normal" | "warning" | "over") => {
      const fieldLabel = t(`option:flashcards.${field}`, {
        defaultValue: field === "front" ? "Front" : "Back"
      })
      const usageText = t("option:flashcards.fieldByteUsage", {
        defaultValue: "{{field}}: {{used}} / {{max}} bytes",
        field: fieldLabel,
        used: byteLength,
        max: FLASHCARD_FIELD_MAX_BYTES
      })
      if (state === "over") {
        return t("option:flashcards.fieldByteOverLimit", {
          defaultValue: "{{usage}}. Exceeds limit by {{over}} bytes.",
          usage: usageText,
          over: byteLength - FLASHCARD_FIELD_MAX_BYTES
        })
      }
      if (state === "warning") {
        return t("option:flashcards.fieldByteNearLimit", {
          defaultValue: "{{usage}}. Approaching the {{max}}-byte limit.",
          usage: usageText,
          max: FLASHCARD_FIELD_MAX_BYTES
        })
      }
      return usageText
    },
    [t]
  )

  // Reset form when drawer opens
  React.useEffect(() => {
    if (open) {
      form.resetFields()
      setShowPreview(false)
      setShowInlineCreate(false)
      setInlineDeckName("")
    }
  }, [open, form])

  // Create new deck (inline)
  const handleInlineCreateDeck = async () => {
    try {
      if (!inlineDeckName.trim()) {
        message.error(
          t("option:flashcards.newDeckNameRequired", {
            defaultValue: "Enter a deck name."
          })
        )
        return
      }
      const deck = await createDeckMutation.mutateAsync({
        name: inlineDeckName.trim()
      })
      message.success(t("common:created", { defaultValue: "Created" }))
      setShowInlineCreate(false)
      setInlineDeckName("")
      form.setFieldsValue({ deck_id: deck.id })
    } catch (e: unknown) {
      const errorMessage =
        e instanceof Error ? e.message : "Failed to create deck"
      message.error(errorMessage)
    }
  }

  // Create flashcard
  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      await createMutation.mutateAsync(normalizeFlashcardTemplateFields(values))
      message.success(t("common:created", { defaultValue: "Created" }))
      form.resetFields()
      onSuccess?.()
      onClose()
    } catch (e: unknown) {
      if (e && typeof e === "object" && "errorFields" in e) return // form validation
      const errorMessage = e instanceof Error ? e.message : "Create failed"
      message.error(errorMessage)
    }
  }

  // Create and add another
  const handleCreateAndAddAnother = async () => {
    try {
      const values = await form.validateFields()
      await createMutation.mutateAsync(normalizeFlashcardTemplateFields(values))
      message.success(t("common:created", { defaultValue: "Created" }))
      // Keep deck selection but clear content
      const deckId = form.getFieldValue("deck_id")
      const modelType = form.getFieldValue("model_type")
      form.resetFields()
      form.setFieldsValue({ deck_id: deckId, model_type: modelType })
      onSuccess?.()
    } catch (e: unknown) {
      if (e && typeof e === "object" && "errorFields" in e) return
      const errorMessage = e instanceof Error ? e.message : "Create failed"
      message.error(errorMessage)
    }
  }

  return (
    <Drawer
      placement="right"
      styles={{ wrapper: { width: FLASHCARDS_DRAWER_WIDTH_PX } }}
      open={open}
      onClose={onClose}
      title={t("option:flashcards.createCard", { defaultValue: "Create Flashcard" })}
      footer={
        <div className="flex justify-end">
          <Space>
            <Button onClick={onClose}>
              {t("common:cancel", { defaultValue: "Cancel" })}
            </Button>
            <Button
              onClick={handleCreateAndAddAnother}
              loading={createMutation.isPending}
            >
              {t("option:flashcards.createAndAddAnother", {
                defaultValue: "Create & Add Another"
              })}
            </Button>
            <Button
              type="primary"
              onClick={handleCreate}
              loading={createMutation.isPending}
            >
              {t("common:create", { defaultValue: "Create" })}
            </Button>
          </Space>
        </div>
      }
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          is_cloze: false,
          model_type: "basic",
          reverse: false
        }}
      >
        {/* Section: Organization */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-text-muted mb-3">
            {t("option:flashcards.organization", { defaultValue: "Organization" })}
          </h3>
          {!showInlineCreate ? (
            <Form.Item
              name="deck_id"
              label={t("option:flashcards.deck", { defaultValue: "Deck" })}
              className="!mb-0"
            >
              <Select
                placeholder={t("option:flashcards.selectDeck", {
                  defaultValue: "Select deck"
                })}
                allowClear
                loading={decksLoading}
                className="w-full"
                options={decks.map((d) => ({
                  label: d.name,
                  value: d.id
                }))}
                popupRender={(menu) => (
                  <>
                    {menu}
                    <Divider className="!my-2" />
                    <button
                      type="button"
                      className="w-full text-left px-3 py-2 text-primary hover:bg-primary/5 flex items-center gap-2"
                      onClick={(e) => {
                        e.preventDefault()
                        setShowInlineCreate(true)
                      }}
                    >
                      <Plus className="size-4" />
                      {t("option:flashcards.createNewDeck", {
                        defaultValue: "Create new deck"
                      })}
                    </button>
                  </>
                )}
              />
            </Form.Item>
          ) : (
            <div className="flex items-center gap-2">
              <Input
                placeholder={t("option:flashcards.newDeckNamePlaceholder", {
                  defaultValue: "New deck name"
                })}
                value={inlineDeckName}
                onChange={(e) => setInlineDeckName(e.target.value)}
                className="flex-1"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleInlineCreateDeck()
                  if (e.key === "Escape") {
                    setShowInlineCreate(false)
                    setInlineDeckName("")
                  }
                }}
              />
              <Button
                type="primary"
                size="small"
                onClick={handleInlineCreateDeck}
                loading={createDeckMutation.isPending}
              >
                {t("common:create", { defaultValue: "Create" })}
              </Button>
              <Button
                size="small"
                onClick={() => {
                  setShowInlineCreate(false)
                  setInlineDeckName("")
                }}
              >
                {t("common:cancel", { defaultValue: "Cancel" })}
              </Button>
            </div>
          )}

          {/* Card template */}
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
            />
          </Form.Item>
          <Text type="secondary" className="block text-xs -mt-4 mb-3">
            {templateHelperText}
          </Text>
          {isClozeTemplate && (
            <Text type="secondary" className="block text-xs -mt-2 mb-3">
              {t("option:flashcards.clozeSyntaxHelp", {
                defaultValue:
                  "Cloze syntax: add at least one deletion like {{syntax}} in Front text.",
                syntax: "{{c1::answer}}"
              })}
            </Text>
          )}
        </div>

        {/* Hidden fields for API compatibility */}
        <Form.Item name="reverse" hidden>
          <Input />
        </Form.Item>
        <Form.Item name="is_cloze" hidden>
          <Input />
        </Form.Item>

        {/* Section: Content */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-text-muted mb-3">
            {t("option:flashcards.content", { defaultValue: "Content" })}
          </h3>

          {/* Front - required */}
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
              }),
              {
                validator(_, value) {
                  const byteLength = getUtf8ByteLength(String(value ?? ""))
                  if (byteLength <= FLASHCARD_FIELD_MAX_BYTES) {
                    return Promise.resolve()
                  }
                  return Promise.reject(
                    new Error(
                      t("option:flashcards.fieldByteValidation", {
                        defaultValue: "{{field}} must be {{max}} bytes or fewer.",
                        field: t("option:flashcards.front", { defaultValue: "Front" }),
                        max: FLASHCARD_FIELD_MAX_BYTES
                      })
                    )
                  )
                }
              }
            ]}
          >
            <Input.TextArea
              rows={3}
              placeholder={t("option:flashcards.frontPlaceholder", {
                defaultValue: "Question or prompt..."
              })}
            />
          </Form.Item>
          <Text
            type={frontLimitState === "over" ? "danger" : frontLimitState === "warning" ? "warning" : "secondary"}
            className="block text-[11px] -mt-4 mb-3"
          >
            {renderByteUsageHint("front", frontByteLength, frontLimitState)}
          </Text>
          <Preview content={frontPreview} showPreview={showPreview} />

          {/* Back - required */}
          <Form.Item
            name="back"
            label={t("option:flashcards.back", { defaultValue: "Back" })}
            rules={[
              {
                required: true,
                message: t("option:flashcards.backRequired", {
                  defaultValue: "Back is required."
                })
              },
              {
                validator(_, value) {
                  const byteLength = getUtf8ByteLength(String(value ?? ""))
                  if (byteLength <= FLASHCARD_FIELD_MAX_BYTES) {
                    return Promise.resolve()
                  }
                  return Promise.reject(
                    new Error(
                      t("option:flashcards.fieldByteValidation", {
                        defaultValue: "{{field}} must be {{max}} bytes or fewer.",
                        field: t("option:flashcards.back", { defaultValue: "Back" }),
                        max: FLASHCARD_FIELD_MAX_BYTES
                      })
                    )
                  )
                }
              }
            ]}
          >
            <Input.TextArea
              rows={5}
              placeholder={t("option:flashcards.backPlaceholder", {
                defaultValue: "Answer..."
              })}
            />
          </Form.Item>
          <Text
            type={backLimitState === "over" ? "danger" : backLimitState === "warning" ? "warning" : "secondary"}
            className="block text-[11px] -mt-4 mb-3"
          >
            {renderByteUsageHint("back", backByteLength, backLimitState)}
          </Text>
          <Preview content={backPreview} showPreview={showPreview} />

          {/* Preview toggle and help text */}
          <div className="flex items-center gap-4">
            <button
              type="button"
              className="text-xs text-primary hover:text-primaryStrong"
              onClick={() => setShowPreview((v) => !v)}
            >
              {showPreview
                ? t("option:flashcards.hidePreview", { defaultValue: "Hide preview" })
                : t("option:flashcards.showPreview", { defaultValue: "Show preview" })}
            </button>
            <Text type="secondary" className="text-xs">
              {t("option:flashcards.markdownHint", {
                defaultValue: "Supports Markdown and LaTeX"
              })}
            </Text>
          </div>
        </div>

        {/* Advanced options - collapsed by default */}
        <Collapse
          ghost
          className="-mx-4"
          items={[
            {
              key: "advanced",
              label: (
                <span className="inline-flex items-center gap-2">
                  <Text type="secondary">
                    {t("option:flashcards.advancedOptions", {
                      defaultValue: "Advanced options (tags, extra, notes)"
                    })}
                  </Text>
                  {advancedFieldCount > 0 && (
                    <Badge
                      count={advancedFieldCount}
                      size="small"
                      title={t("option:flashcards.advancedFieldsSet", {
                        defaultValue: "{{count}} field(s) set",
                        count: advancedFieldCount
                      })}
                    />
                  )}
                </span>
              ),
              children: (
                <div className="space-y-4">
                  <Form.Item
                    name="tags"
                    label={t("option:flashcards.tags", { defaultValue: "Tags" })}
                    className="!mb-0"
                  >
                    <Select
                      mode="tags"
                      placeholder={t("option:flashcards.tagsPlaceholder", {
                        defaultValue: "tag1, tag2"
                      })}
                      open={false}
                      allowClear
                    />
                  </Form.Item>

                  <Form.Item
                    name="extra"
                    label={t("option:flashcards.extra", { defaultValue: "Extra" })}
                    className="!mb-0"
                  >
                    <Input.TextArea
                      rows={2}
                      placeholder={t("option:flashcards.extraPlaceholder", {
                        defaultValue: "Optional hints or explanations..."
                      })}
                    />
                  </Form.Item>
                  <Preview content={extraPreview} showPreview={showPreview} />

                  <Form.Item
                    name="notes"
                    label={t("option:flashcards.notes", { defaultValue: "Notes" })}
                    className="!mb-0"
                  >
                    <Input.TextArea
                      rows={2}
                      placeholder={t("option:flashcards.notesPlaceholder", {
                        defaultValue: "Internal notes (not shown during review)..."
                      })}
                    />
                  </Form.Item>
                  <Preview content={notesPreview} showPreview={showPreview} />
                </div>
              )
            }
          ]}
        />
      </Form>
    </Drawer>
  )
}

export default FlashcardCreateDrawer
