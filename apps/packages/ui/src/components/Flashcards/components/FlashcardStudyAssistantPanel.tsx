import React from "react"
import { Alert, Button, Card, Empty, Input, Space, Tag, Typography } from "antd"
import { Lightbulb, MessageSquareText, Sparkles, Volume2 } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition"
import { useTTS } from "@/hooks/useTTS"
import type {
  StudyAssistantAction,
  StudyAssistantMessage,
  StudyAssistantRespondRequest
} from "@/services/flashcards"
import { MarkdownWithBoundary } from "./MarkdownWithBoundary"
import { VoiceTranscriptComposer } from "./VoiceTranscriptComposer"

const { Text, Title } = Typography

const DEFAULT_ACTIONS: StudyAssistantAction[] = [
  "explain",
  "mnemonic",
  "follow_up",
  "fact_check",
  "freeform"
]

interface FlashcardStudyAssistantPanelProps {
  cardUuid: string
  messages: StudyAssistantMessage[]
  availableActions?: StudyAssistantAction[] | null
  isLoading?: boolean
  isError?: boolean
  isResponding?: boolean
  onRespond: (request: StudyAssistantRespondRequest) => Promise<unknown>
}

const ACTION_LABELS: Record<StudyAssistantAction, string> = {
  explain: "Explain",
  mnemonic: "Mnemonic",
  follow_up: "Follow-up",
  fact_check: "Fact-check me",
  freeform: "Ask assistant"
}

export const FlashcardStudyAssistantPanel: React.FC<FlashcardStudyAssistantPanelProps> = ({
  cardUuid,
  messages,
  availableActions,
  isLoading = false,
  isError = false,
  isResponding = false,
  onRespond
}) => {
  const { t } = useTranslation(["option", "common"])
  const { speak, isSpeaking } = useTTS()
  const {
    supported,
    isListening,
    transcript,
    start,
    stop,
    resetTranscript
  } = useSpeechRecognition()
  const [assistantError, setAssistantError] = React.useState<string | null>(null)
  const [followUpText, setFollowUpText] = React.useState("")
  const [factCheckTranscript, setFactCheckTranscript] = React.useState("")
  const [factCheckOpen, setFactCheckOpen] = React.useState(false)

  const resolvedActions = React.useMemo(
    () =>
      Array.from(
        new Set((availableActions && availableActions.length ? availableActions : DEFAULT_ACTIONS))
      ),
    [availableActions]
  )

  React.useEffect(() => {
    setAssistantError(null)
    setFollowUpText("")
    setFactCheckTranscript("")
    setFactCheckOpen(false)
    resetTranscript()
  }, [cardUuid, resetTranscript])

  React.useEffect(() => {
    if (!factCheckOpen || !isListening) return
    setFactCheckTranscript(transcript)
  }, [factCheckOpen, isListening, transcript])

  const submitRequest = React.useCallback(
    async (request: StudyAssistantRespondRequest) => {
      try {
        setAssistantError(null)
        await onRespond(request)
        return true
      } catch {
        setAssistantError(
          t("option:flashcards.studyAssistantUnavailable", {
            defaultValue: "Study assistant unavailable"
          })
        )
        return false
      }
    },
    [onRespond, t]
  )

  const handleQuickAction = React.useCallback(
    async (action: StudyAssistantAction) => {
      if (action === "fact_check") {
        setFactCheckOpen(true)
        setFactCheckTranscript(transcript)
        if (supported && !isListening) {
          resetTranscript()
          start()
        }
        return
      }
      await submitRequest({ action })
    },
    [isListening, resetTranscript, start, submitRequest, supported, transcript]
  )

  const handleSubmitFollowUp = React.useCallback(async () => {
    const trimmed = followUpText.trim()
    if (!trimmed) return
    const action: StudyAssistantAction = resolvedActions.includes("follow_up")
      ? "follow_up"
      : "freeform"
    const succeeded = await submitRequest({
      action,
      message: trimmed,
      input_modality: "text"
    })
    if (succeeded) {
      setFollowUpText("")
    }
  }, [followUpText, resolvedActions, submitRequest])

  const handleSubmitFactCheck = React.useCallback(async () => {
    const trimmed = factCheckTranscript.trim()
    if (!trimmed) return
    const succeeded = await submitRequest({
      action: "fact_check",
      message: trimmed,
      input_modality: "voice_transcript"
    })
    if (!succeeded) return
    if (isListening) {
      stop()
    }
    setFactCheckOpen(false)
    setFactCheckTranscript("")
    resetTranscript()
  }, [factCheckTranscript, isListening, resetTranscript, stop, submitRequest])

  const handleCancelFactCheck = React.useCallback(() => {
    if (isListening) {
      stop()
    }
    setFactCheckOpen(false)
    setFactCheckTranscript("")
    resetTranscript()
  }, [isListening, resetTranscript, stop])

  const handlePlayReply = React.useCallback(
    (content: string) => {
      if (!content.trim()) return
      void speak({ utterance: content })
    },
    [speak]
  )

  return (
    <Card
      size="small"
      data-testid="flashcards-review-study-assistant"
      title={
        <div className="flex items-center gap-2">
          <Sparkles className="size-4 text-primary" aria-hidden="true" />
          <span>
            {t("option:flashcards.studyAssistantTitle", {
              defaultValue: "Study assistant"
            })}
          </span>
        </div>
      }
    >
      <Space orientation="vertical" size={12} className="w-full">
        {(assistantError || isError) && (
          <Alert
            showIcon
            type="warning"
            title={
              assistantError ??
              t("option:flashcards.studyAssistantUnavailable", {
                defaultValue: "Study assistant unavailable"
              })
            }
          />
        )}
        <div className="flex flex-wrap gap-2">
          {resolvedActions.includes("explain") && (
            <Button
              onClick={() => void handleQuickAction("explain")}
              loading={isResponding}
              icon={<Lightbulb className="size-4" />}
            >
              {t("option:flashcards.studyAssistantExplain", {
                defaultValue: ACTION_LABELS.explain
              })}
            </Button>
          )}
          {resolvedActions.includes("mnemonic") && (
            <Button
              onClick={() => void handleQuickAction("mnemonic")}
              loading={isResponding}
            >
              {t("option:flashcards.studyAssistantMnemonic", {
                defaultValue: ACTION_LABELS.mnemonic
              })}
            </Button>
          )}
          {supported && resolvedActions.includes("fact_check") && (
            <Button
              onClick={() => void handleQuickAction("fact_check")}
              loading={isResponding}
            >
              {t("option:flashcards.studyAssistantFactCheck", {
                defaultValue: ACTION_LABELS.fact_check
              })}
            </Button>
          )}
        </div>
        {factCheckOpen && (
          <VoiceTranscriptComposer
            transcript={factCheckTranscript}
            isListening={isListening}
            supported={supported}
            isSubmitting={isResponding}
            onTranscriptChange={setFactCheckTranscript}
            onStartListening={() => start()}
            onStopListening={stop}
            onCancel={handleCancelFactCheck}
            onSubmit={() => void handleSubmitFactCheck()}
          />
        )}
        {resolvedActions.includes("follow_up") || resolvedActions.includes("freeform") ? (
          <div className="rounded border border-border bg-surface p-3">
            <Space orientation="vertical" size={8} className="w-full">
              <Text strong>
                {t("option:flashcards.studyAssistantChatPrompt", {
                  defaultValue: "Ask a follow-up"
                })}
              </Text>
              <Input.TextArea
                aria-label={t("option:flashcards.studyAssistantChatInput", {
                  defaultValue: "Ask the study assistant"
                })}
                value={followUpText}
                onChange={(event) => setFollowUpText(event.target.value)}
                rows={3}
                placeholder={t("option:flashcards.studyAssistantChatPlaceholder", {
                  defaultValue: "Ask for clarification, examples, or a simpler explanation."
                })}
              />
              <div className="flex justify-end">
                <Button
                  type="primary"
                  icon={<MessageSquareText className="size-4" />}
                  loading={isResponding}
                  disabled={!followUpText.trim()}
                  onClick={() => void handleSubmitFollowUp()}
                >
                  {t("option:flashcards.studyAssistantChatSend", {
                    defaultValue: ACTION_LABELS.freeform
                  })}
                </Button>
              </div>
            </Space>
          </div>
        ) : null}
        <div>
          <Title level={5} className="!mb-2">
            {t("option:flashcards.studyAssistantHistory", {
              defaultValue: "Session"
            })}
          </Title>
          {isLoading ? (
            <Text type="secondary">
              {t("option:flashcards.studyAssistantLoading", {
                defaultValue: "Loading assistant history..."
              })}
            </Text>
          ) : messages.length ? (
            <div className="flex flex-col gap-3">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className="rounded border border-border bg-surface p-3"
                >
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <Space size={8}>
                      <Tag color={message.role === "assistant" ? "blue" : "default"}>
                        {message.role === "assistant"
                          ? t("option:flashcards.studyAssistantRoleAssistant", {
                              defaultValue: "Assistant"
                            })
                          : t("option:flashcards.studyAssistantRoleUser", {
                              defaultValue: "You"
                            })}
                      </Tag>
                      <Text type="secondary" className="text-xs">
                        {t(`option:flashcards.studyAssistantAction.${message.action_type}`, {
                          defaultValue: ACTION_LABELS[message.action_type]
                        })}
                      </Text>
                    </Space>
                    {message.role === "assistant" && (
                      <Button
                        size="small"
                        icon={<Volume2 className="size-4" />}
                        loading={isSpeaking}
                        onClick={() => handlePlayReply(message.content)}
                      >
                        {t("option:flashcards.studyAssistantPlayReply", {
                          defaultValue: "Play reply"
                        })}
                      </Button>
                    )}
                  </div>
                  <MarkdownWithBoundary
                    content={message.content}
                    size="sm"
                    className="prose-headings:!text-text prose-p:!text-text prose-li:!text-text prose-strong:!text-text"
                  />
                </div>
              ))}
            </div>
          ) : (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={t("option:flashcards.studyAssistantEmpty", {
                defaultValue: "Use the assistant to explain or check this card without leaving review mode."
              })}
            />
          )}
        </div>
      </Space>
    </Card>
  )
}

export default FlashcardStudyAssistantPanel
