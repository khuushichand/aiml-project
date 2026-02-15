import React from "react"
import type { TFunction } from "i18next"
import { Popover, Tooltip } from "antd"
import {
  CheckIcon,
  ChevronLeft,
  ChevronRight,
  CopyIcon,
  GitBranchIcon,
  InfoIcon,
  Layers,
  MoreHorizontal,
  Pen,
  PlayCircle,
  Pin,
  PinOff,
  RotateCcw,
  Square,
  StickyNote,
  FileText,
  Volume2Icon,
  CornerUpLeft,
  Trash2
} from "lucide-react"
import { IconButton } from "../IconButton"
import { GenerationInfo } from "./GenerationInfo"
import { FeedbackButtons } from "@/components/Sidepanel/Chat/FeedbackButtons"
import type { FeedbackThumb } from "@/store/feedback"
import type { GenerationInfo as GenerationInfoType } from "./types"
import type { MessageSteeringMode } from "@/types/message-steering"

const ACTION_BUTTON_CLASS =
  "flex items-center justify-center rounded-full border border-border bg-surface2 text-text-muted hover:bg-surface hover:text-text transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-focus min-w-[44px] min-h-[44px] sm:h-8 sm:w-8 sm:min-w-0 sm:min-h-0"

const ActionButtonWithLabel: React.FC<{
  icon: React.ReactNode
  label: string
  showLabel?: boolean
  className?: string
}> = ({ icon, label, showLabel = false, className = "" }) => (
  <span className={`inline-flex items-center gap-1 ${className}`}>
    {icon}
    {showLabel && (
      <span className="text-label text-text-subtle">{label}</span>
    )}
  </span>
)

/** Overflow menu item for secondary actions */
const OverflowMenuItem: React.FC<{
  icon: React.ReactNode
  label: string
  onClick?: () => void
  disabled?: boolean
  danger?: boolean
  active?: boolean
}> = ({ icon, label, onClick, disabled, danger, active }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    aria-disabled={disabled}
    className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-xs transition hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-50 ${
      danger
        ? "text-danger hover:text-danger"
        : active
          ? "bg-primary/10 text-primaryStrong hover:bg-primary/10 hover:text-primaryStrong"
          : "text-text hover:text-text"
    }`}
  >
    <span className="flex h-4 w-4 items-center justify-center text-text-subtle">{icon}</span>
    <span>{label}</span>
  </button>
)

type MessageActionsBarProps = {
  t: TFunction
  isProMode: boolean
  isBot: boolean
  showVariantPager: boolean
  resolvedVariantIndex: number
  variantCount: number
  canSwipePrev: boolean
  canSwipeNext: boolean
  onSwipePrev?: () => void
  onSwipeNext?: () => void
  overflowChipVisibility: string
  actionRowVisibility: string
  isTtsEnabled?: boolean
  ttsDisabledReason?: string | null
  ttsActionDisabled?: boolean
  isSpeaking: boolean
  onToggleTts: () => void
  hideCopy?: boolean
  copyPressed: boolean
  onCopy: () => void | Promise<void>
  canReply: boolean
  onReply: () => void
  canSaveToNotes: boolean
  canSaveToFlashcards: boolean
  canGenerateDocument: boolean
  onGenerateDocument: () => void
  onSaveKnowledge: (makeFlashcard: boolean) => void
  savingKnowledge: "note" | "flashcard" | null
  generationInfo?: GenerationInfoType
  isLastMessage: boolean
  hideEditAndRegenerate?: boolean
  onRegenerate: () => void
  onNewBranch?: () => void
  temporaryChat?: boolean
  hideContinue?: boolean
  onContinue?: () => void
  messageSteeringMode?: MessageSteeringMode
  onMessageSteeringModeChange?: (mode: MessageSteeringMode) => void
  messageSteeringForceNarrate?: boolean
  onMessageSteeringForceNarrateChange?: (enabled: boolean) => void
  onClearMessageSteering?: () => void
  onEdit: () => void
  editMode: boolean
  showFeedbackControls: boolean
  feedbackSelected?: FeedbackThumb
  feedbackDisabled: boolean
  feedbackDisabledReason: string
  isFeedbackSubmitting: boolean
  showThanks: boolean
  onThumbUp: () => void
  onThumbDown: () => void
  onOpenDetails: () => void
  onDelete?: () => void
  canPin?: boolean
  isPinned?: boolean
  onTogglePinned?: () => void
}

export function MessageActionsBar({
  t,
  isProMode,
  isBot,
  showVariantPager,
  resolvedVariantIndex,
  variantCount,
  canSwipePrev,
  canSwipeNext,
  onSwipePrev,
  onSwipeNext,
  overflowChipVisibility,
  actionRowVisibility,
  isTtsEnabled,
  ttsDisabledReason,
  ttsActionDisabled = false,
  isSpeaking,
  onToggleTts,
  hideCopy,
  copyPressed,
  onCopy,
  canReply,
  onReply,
  canSaveToNotes,
  canSaveToFlashcards,
  canGenerateDocument,
  onGenerateDocument,
  onSaveKnowledge,
  savingKnowledge,
  generationInfo,
  isLastMessage,
  hideEditAndRegenerate,
  onRegenerate,
  onNewBranch,
  temporaryChat,
  hideContinue,
  onContinue,
  messageSteeringMode = "none",
  onMessageSteeringModeChange,
  messageSteeringForceNarrate = false,
  onMessageSteeringForceNarrateChange,
  onClearMessageSteering,
  onEdit,
  editMode,
  showFeedbackControls,
  feedbackSelected,
  feedbackDisabled,
  feedbackDisabledReason,
  isFeedbackSubmitting,
  showThanks,
  onThumbUp,
  onThumbDown,
  onOpenDetails,
  onDelete,
  canPin,
  isPinned,
  onTogglePinned
}: MessageActionsBarProps) {
  const actionButtonClass = `${ACTION_BUTTON_CLASS} ${
    isProMode ? "h-11 px-3 sm:h-8 sm:px-2" : "h-11 w-11 sm:h-8 sm:w-8"
  }`

  const [overflowOpen, setOverflowOpen] = React.useState(false)
  const showLeftFeedback = !editMode && showFeedbackControls

  // Build overflow menu items
  const overflowItems = React.useMemo(() => {
    const items: React.ReactNode[] = []
    if (canReply) {
      items.push(
        <OverflowMenuItem
          key="reply"
          icon={<CornerUpLeft className="w-3.5 h-3.5" />}
          label={t("common:reply", "Reply")}
          onClick={onReply}
        />
      )
    }
    if (isBot && onNewBranch && !temporaryChat) {
      items.push(
        <OverflowMenuItem
          key="branch"
          icon={<GitBranchIcon className="w-3.5 h-3.5" />}
          label={t("newBranch", "New Branch")}
          onClick={onNewBranch}
        />
      )
    }
    if (isBot && !hideContinue && isLastMessage && onContinue) {
      items.push(
        <OverflowMenuItem
          key="continue"
          icon={<PlayCircle className="w-3.5 h-3.5" />}
          label={t("continue", "Continue")}
          onClick={onContinue}
        />
      )
    }
    const canControlMessageSteering =
      isBot &&
      isLastMessage &&
      onMessageSteeringModeChange &&
      onMessageSteeringForceNarrateChange
    if (canControlMessageSteering) {
      items.push(
        <OverflowMenuItem
          key="steer-continue"
          icon={<span className="text-[10px] leading-none font-semibold">C</span>}
          label={
            t("playground:composer.steering.continue", "Continue as user") as string
          }
          onClick={() =>
            onMessageSteeringModeChange(
              messageSteeringMode === "continue_as_user"
                ? "none"
                : "continue_as_user"
            )
          }
          active={messageSteeringMode === "continue_as_user"}
        />
      )
      items.push(
        <OverflowMenuItem
          key="steer-impersonate"
          icon={<span className="text-[10px] leading-none font-semibold">I</span>}
          label={
            t("playground:composer.steering.impersonate", "Impersonate user") as string
          }
          onClick={() =>
            onMessageSteeringModeChange(
              messageSteeringMode === "impersonate_user"
                ? "none"
                : "impersonate_user"
            )
          }
          active={messageSteeringMode === "impersonate_user"}
        />
      )
      items.push(
        <OverflowMenuItem
          key="steer-narrate"
          icon={<span className="text-[10px] leading-none font-semibold">N</span>}
          label={t("playground:composer.steering.narrate", "Force narrate") as string}
          onClick={() =>
            onMessageSteeringForceNarrateChange(!messageSteeringForceNarrate)
          }
          active={messageSteeringForceNarrate}
        />
      )
      const steeringActive =
        messageSteeringMode !== "none" || messageSteeringForceNarrate
      if (steeringActive && onClearMessageSteering) {
        items.push(
          <OverflowMenuItem
            key="steer-clear"
            icon={<span className="text-[10px] leading-none font-semibold">x</span>}
            label={t("common:clear", "Clear") as string}
            onClick={onClearMessageSteering}
          />
        )
      }
    }
    if (isBot && canSaveToNotes) {
      items.push(
        <OverflowMenuItem
          key="save-note"
          icon={<StickyNote className="w-3.5 h-3.5" />}
          label={t("saveToNotes", "Save to Notes")}
          onClick={() => onSaveKnowledge(false)}
          disabled={savingKnowledge !== null}
        />
      )
    }
    if (isBot && canSaveToFlashcards) {
      items.push(
        <OverflowMenuItem
          key="save-flashcard"
          icon={<Layers className="w-3.5 h-3.5" />}
          label={t("saveToFlashcards", "Save to Flashcards")}
          onClick={() => onSaveKnowledge(true)}
          disabled={savingKnowledge !== null}
        />
      )
    }
    if (isBot && canGenerateDocument) {
      items.push(
        <OverflowMenuItem
          key="generate-doc"
          icon={<FileText className="w-3.5 h-3.5" />}
          label={t("generateDocument", "Generate document")}
          onClick={onGenerateDocument}
        />
      )
    }
    if (isBot && isTtsEnabled) {
      items.push(
        <OverflowMenuItem
          key="tts"
          icon={
            !isSpeaking ? (
              <Volume2Icon className="w-3.5 h-3.5" />
            ) : (
              <Square className="w-3.5 h-3.5 text-danger" />
            )
          }
          label={isSpeaking ? t("ttsStop", "Stop TTS") : t("tts", "Read Aloud")}
          onClick={onToggleTts}
          disabled={ttsActionDisabled}
        />
      )
    }
    if (onDelete) {
      items.push(
        <OverflowMenuItem
          key="delete"
          icon={<Trash2 className="w-3.5 h-3.5" />}
          label={t("common:delete", "Delete")}
          onClick={onDelete}
          danger
        />
      )
    }
    if (canPin && onTogglePinned) {
      items.push(
        <OverflowMenuItem
          key="pin-toggle"
          icon={
            isPinned ? (
              <PinOff className="w-3.5 h-3.5" />
            ) : (
              <Pin className="w-3.5 h-3.5" />
            )
          }
          label={
            isPinned
              ? t("common:unpin", "Unpin")
              : t("common:pin", "Pin")
          }
          onClick={onTogglePinned}
        />
      )
    }
    return items
  }, [
    canReply, onReply, isBot, onNewBranch, temporaryChat,
    hideContinue, isLastMessage, onContinue, canSaveToNotes,
    messageSteeringMode, onMessageSteeringModeChange,
    messageSteeringForceNarrate, onMessageSteeringForceNarrateChange,
    onClearMessageSteering,
    canSaveToFlashcards, canGenerateDocument, onGenerateDocument,
    onSaveKnowledge, savingKnowledge, isTtsEnabled, ttsActionDisabled,
    isSpeaking, onToggleTts, onDelete, canPin, isPinned, onTogglePinned, t
  ])

  return (
    <div
      className={`flex w-full items-start gap-2 ${
        showLeftFeedback ? "justify-between" : "justify-end"
      }`}>
      {showLeftFeedback && (
        <FeedbackButtons
          compact
          selected={feedbackSelected}
          disabled={feedbackDisabled}
          disabledReason={feedbackDisabledReason}
          isSubmitting={isFeedbackSubmitting}
          onThumbUp={onThumbUp}
          onThumbDown={onThumbDown}
          onOpenDetails={onOpenDetails}
          showThanks={showThanks}
          className="mr-auto"
        />
      )}

      <div className="ml-auto flex items-center gap-1">
        {/* Variant pager */}
        {showVariantPager && (
          <div className="inline-flex items-center gap-1 rounded-full border border-border bg-surface2 px-1.5 py-0.5 text-xs text-text-muted">
            <button
              type="button"
              aria-label={t("playground:actions.previousVariant", "Previous response") as string}
              title={t("playground:actions.previousVariant", "Previous response") as string}
              onClick={() => canSwipePrev && onSwipePrev?.()}
              disabled={!canSwipePrev}
              className={`flex h-4 w-4 items-center justify-center rounded-full transition-colors ${
                canSwipePrev ? "text-text-subtle hover:text-text" : "text-text-muted/50"
              }`}
            >
              <ChevronLeft className="h-3 w-3" />
            </button>
            <span className="tabular-nums text-[11px]">
              {resolvedVariantIndex + 1}/{variantCount}
            </span>
            <button
              type="button"
              aria-label={t("playground:actions.nextVariant", "Next response") as string}
              title={t("playground:actions.nextVariant", "Next response") as string}
              onClick={() => canSwipeNext && onSwipeNext?.()}
              disabled={!canSwipeNext}
              className={`flex h-4 w-4 items-center justify-center rounded-full transition-colors ${
                canSwipeNext ? "text-text-subtle hover:text-text" : "text-text-muted/50"
              }`}
            >
              <ChevronRight className="h-3 w-3" />
            </button>
          </div>
        )}

        {/* Collapsed "..." trigger (shows when action row is hidden) */}
        <button
          type="button"
          aria-label={t("common:moreActions", "More actions") as string}
          title={t("common:moreActions", "More actions") as string}
          className={`${overflowChipVisibility} rounded-full border border-border bg-surface2 px-2 py-0.5 text-xs text-text-muted transition-colors hover:text-text`}
        >
          •••
        </button>

        {/* Action row (visible on hover/tap) */}
        <div className={`${actionRowVisibility} flex-wrap items-center gap-2`}>
          <div className="flex flex-wrap items-center gap-1">
            {/* Primary actions: Copy, Edit, Regenerate */}
            {!hideCopy && (
              <Tooltip title={t("copyToClipboard")}>
                <IconButton
                  ariaLabel={t("copyToClipboard") as string}
                  onClick={() => { void onCopy() }}
                  className={actionButtonClass}
                >
                  <ActionButtonWithLabel
                    icon={
                      !copyPressed ? (
                        <CopyIcon className="w-3 h-3 text-text-subtle group-hover:text-text" />
                      ) : (
                        <CheckIcon className="w-3 h-3 text-success group-hover:text-success" />
                      )
                    }
                    label={t("copyShort", "Copy")}
                    showLabel={isProMode}
                  />
                </IconButton>
              </Tooltip>
            )}
            {!hideEditAndRegenerate && (
              <Tooltip title={t("edit")}>
                <IconButton
                  onClick={onEdit}
                  ariaLabel={t("edit") as string}
                  className={actionButtonClass}
                >
                  <ActionButtonWithLabel
                    icon={<Pen className="w-3 h-3 text-text-subtle group-hover:text-text" />}
                    label={t("edit", "Edit")}
                    showLabel={isProMode}
                  />
                </IconButton>
              </Tooltip>
            )}
            {isBot && !hideEditAndRegenerate && isLastMessage && (
              <Tooltip title={t("regenerate")}>
                <IconButton
                  ariaLabel={t("regenerate") as string}
                  onClick={onRegenerate}
                  className={actionButtonClass}
                >
                  <ActionButtonWithLabel
                    icon={<RotateCcw className="w-3 h-3 text-text-subtle group-hover:text-text" />}
                    label={t("regenShort", "Redo")}
                    showLabel={isProMode}
                  />
                </IconButton>
              </Tooltip>
            )}

            {/* Generation info (stays inline) */}
            {isBot && generationInfo && (
              <Popover
                content={<GenerationInfo generationInfo={generationInfo} />}
                title={t("generationInfo")}
              >
                <IconButton
                  ariaLabel={t("generationInfo") as string}
                  className={actionButtonClass}
                >
                  <ActionButtonWithLabel
                    icon={<InfoIcon className="w-3 h-3 text-text-subtle group-hover:text-text" />}
                    label={t("infoShort", "Info")}
                    showLabel={isProMode}
                  />
                </IconButton>
              </Popover>
            )}

            {/* Overflow menu for secondary actions */}
            {overflowItems.length > 0 && (
              <Popover
                open={overflowOpen}
                onOpenChange={setOverflowOpen}
                trigger="click"
                placement="bottomRight"
                content={
                  <div className="flex min-w-[180px] flex-col py-1" onClick={() => setOverflowOpen(false)}>
                    {overflowItems}
                  </div>
                }
              >
                <IconButton
                  ariaLabel={t("common:moreActions", "More actions") as string}
                  className={actionButtonClass}
                >
                  <MoreHorizontal className="w-3 h-3 text-text-subtle group-hover:text-text" />
                </IconButton>
              </Popover>
            )}
          </div>

        </div>
      </div>
    </div>
  )
}
