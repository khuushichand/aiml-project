import React from "react"
import { useTranslation } from "react-i18next"
import { Modal } from "antd"
import { Mic, Headphones } from "lucide-react"

interface VoiceModeSelectorProps {
  open: boolean
  onClose: () => void
  onSelectDictation: () => void
  onSelectConversation: () => void
  dictationAvailable: boolean
  conversationAvailable: boolean
}

/**
 * Modal for selecting between voice typing (dictation) and voice conversation modes.
 * Provides clear descriptions of each mode to help users understand the difference.
 */
export const VoiceModeSelector: React.FC<VoiceModeSelectorProps> = ({
  open,
  onClose,
  onSelectDictation,
  onSelectConversation,
  dictationAvailable,
  conversationAvailable
}) => {
  const { t } = useTranslation(["playground"])

  const handleDictation = React.useCallback(() => {
    onSelectDictation()
    onClose()
  }, [onSelectDictation, onClose])

  const handleConversation = React.useCallback(() => {
    onSelectConversation()
    onClose()
  }, [onSelectConversation, onClose])

  return (
    <Modal
      open={open}
      onCancel={onClose}
      title={t("playground:voiceMode.title", "Choose voice mode")}
      footer={null}
      centered
      destroyOnClose
    >
      <div className="flex flex-col gap-4 pt-2">
        {/* Voice Typing Card */}
        <button
          type="button"
          onClick={handleDictation}
          disabled={!dictationAvailable}
          className="flex items-start gap-3 rounded-lg border border-border p-4 text-left transition hover:bg-surface2 hover:border-primary/50 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:border-border"
        >
          <div className="rounded-full bg-primary/10 p-2">
            <Mic className="h-5 w-5 text-primary" />
          </div>
          <div className="flex-1">
            <h3 className="font-medium text-text">
              {t("playground:voiceMode.dictationTitle", "Voice Typing")}
            </h3>
            <p className="mt-1 text-sm text-text-muted">
              {t("playground:voiceMode.dictationDesc", "Press to speak, text appears in message box. Review and edit before sending.")}
            </p>
            {!dictationAvailable && (
              <p className="mt-2 text-xs text-warn">
                {t("playground:voiceMode.dictationUnavailable", "Speech recognition not available")}
              </p>
            )}
          </div>
        </button>

        {/* Voice Conversation Card */}
        <button
          type="button"
          onClick={handleConversation}
          disabled={!conversationAvailable}
          className="flex items-start gap-3 rounded-lg border border-border p-4 text-left transition hover:bg-surface2 hover:border-primary/50 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:border-border"
        >
          <div className="rounded-full bg-primary/10 p-2">
            <Headphones className="h-5 w-5 text-primary" />
          </div>
          <div className="flex-1">
            <h3 className="font-medium text-text">
              {t("playground:voiceMode.conversationTitle", "Voice Conversation")}
            </h3>
            <p className="mt-1 text-sm text-text-muted">
              {t("playground:voiceMode.conversationDesc", "Hands-free spoken dialogue with AI responses read aloud. Messages sent automatically.")}
            </p>
            {!conversationAvailable && (
              <p className="mt-2 text-xs text-warn">
                {t("playground:voiceMode.conversationUnavailable", "Connect to a tldw server with audio support")}
              </p>
            )}
          </div>
        </button>
      </div>
    </Modal>
  )
}
