import React, { useCallback, useState, useRef, useEffect } from "react"
import { useTranslation } from "react-i18next"
import { Button, Dropdown, message, Modal, Spin, Select } from "antd"
import type { MenuProps } from "antd"
import {
  Copy,
  Highlighter,
  Languages,
  MessageSquare,
  ChevronDown,
  Volume2
} from "lucide-react"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import { useTranslate } from "@/hooks/document-workspace/useTranslate"
import { useDocumentTTS } from "@/hooks/document-workspace/useDocumentTTS"
import type { AnnotationColor } from "../types"

interface TextSelectionPopoverProps {
  text: string
  position: { x: number; y: number }
  onClose: () => void
  /** Optional CFI location for EPUB annotations */
  epubCfi?: string
}

const HIGHLIGHT_COLORS: Array<{ key: AnnotationColor; label: string; color: string }> = [
  { key: "yellow", label: "Yellow", color: "#fef08a" },
  { key: "green", label: "Green", color: "#bbf7d0" },
  { key: "blue", label: "Blue", color: "#bfdbfe" },
  { key: "pink", label: "Pink", color: "#fbcfe8" }
]

const TARGET_LANGUAGES = [
  { value: "English", label: "English" },
  { value: "Spanish", label: "Spanish" },
  { value: "French", label: "French" },
  { value: "German", label: "German" },
  { value: "Chinese", label: "Chinese" },
  { value: "Japanese", label: "Japanese" },
  { value: "Korean", label: "Korean" },
  { value: "Portuguese", label: "Portuguese" },
  { value: "Russian", label: "Russian" },
  { value: "Arabic", label: "Arabic" }
]

/**
 * Floating popover that appears when text is selected in the PDF viewer.
 * Provides actions: Copy, Highlight, Translate, Ask AI
 */
export const TextSelectionPopover: React.FC<TextSelectionPopoverProps> = ({
  text,
  position,
  onClose,
  epubCfi
}) => {
  const { t } = useTranslation(["option", "common"])
  const popoverRef = useRef<HTMLDivElement>(null)
  const [translateModalOpen, setTranslateModalOpen] = useState(false)
  const [translatedText, setTranslatedText] = useState<string | null>(null)
  const [targetLanguage, setTargetLanguage] = useState("English")
  const [adjustedPosition, setAdjustedPosition] = useState(position)

  const { mutateAsync: translate, isPending: translating } = useTranslate()
  const { speak, state: ttsState, stop: stopTTS } = useDocumentTTS()

  const activeDocumentId = useDocumentWorkspaceStore((s) => s.activeDocumentId)
  const currentPage = useDocumentWorkspaceStore((s) => s.currentPage)
  const currentPercentage = useDocumentWorkspaceStore((s) => s.currentPercentage)
  const currentChapterTitle = useDocumentWorkspaceStore((s) => s.currentChapterTitle)
  const addAnnotation = useDocumentWorkspaceStore((s) => s.addAnnotation)
  const setActiveRightTab = useDocumentWorkspaceStore((s) => s.setActiveRightTab)

  // Adjust position to keep popover in viewport
  useEffect(() => {
    if (!popoverRef.current) return

    const rect = popoverRef.current.getBoundingClientRect()
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    let x = position.x
    let y = position.y

    // Adjust horizontal position if going off-screen
    if (x + rect.width > viewportWidth - 16) {
      x = viewportWidth - rect.width - 16
    }
    if (x < 16) {
      x = 16
    }

    // Adjust vertical position if going off-screen
    if (y + rect.height > viewportHeight - 16) {
      y = position.y - rect.height - 8 // Show above selection
    }
    if (y < 16) {
      y = 16
    }

    setAdjustedPosition({ x, y })
  }, [position])

  // Copy to clipboard
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text)
      message.success(t("option:documentWorkspace.copiedToClipboard", "Copied to clipboard"))
      onClose()
    } catch (err) {
      message.error(t("option:documentWorkspace.copyFailed", "Failed to copy"))
    }
  }, [text, onClose, t])

  // Highlight with color
  const handleHighlight = useCallback(
    (color: AnnotationColor) => {
      if (!activeDocumentId) return

      // Use CFI for EPUB, page number for PDF
      const location = epubCfi || currentPage
      const isEpub = !!epubCfi

      addAnnotation({
        documentId: activeDocumentId,
        location,
        text,
        color,
        annotationType: "highlight",
        // Include chapter context for EPUB annotations
        ...(isEpub && currentChapterTitle ? { chapterTitle: currentChapterTitle } : {}),
        ...(isEpub ? { percentage: currentPercentage } : {})
      })
      message.success(t("option:documentWorkspace.highlightAdded", "Highlight added"))
      onClose()
    },
    [activeDocumentId, currentPage, currentPercentage, currentChapterTitle, epubCfi, text, addAnnotation, onClose, t]
  )

  // Ask AI - prefill chat with question about selected text
  const handleAskAI = useCallback(() => {
    // Set the chat tab as active and we'll handle the prefill via URL or state
    setActiveRightTab("chat")
    // Store selected text for the chat component to pick up
    // This could be done via a dedicated store action, but for simplicity we'll use
    // a custom event that the DocumentChat component can listen to
    window.dispatchEvent(
      new CustomEvent("document-workspace-ask-ai", {
        detail: { text, prompt: `Explain this passage: "${text}"` }
      })
    )
    onClose()
  }, [text, setActiveRightTab, onClose])

  // Listen - text-to-speech
  const handleListen = useCallback(async () => {
    if (ttsState.isPlaying && ttsState.currentText === text) {
      // Stop if already playing this text
      stopTTS()
    } else {
      await speak(text)
    }
    // Don't close popover - let user control playback
  }, [text, speak, stopTTS, ttsState.isPlaying, ttsState.currentText])

  // Translate - opens modal with translation
  const handleTranslate = useCallback(async () => {
    setTranslateModalOpen(true)
    setTranslatedText(null)

    try {
      const result = await translate({ text, targetLanguage })
      setTranslatedText(result.translated_text)
    } catch (err) {
      console.error("Translation error:", err)
      setTranslatedText(t("option:documentWorkspace.translationFailed", "Translation failed. Please try again."))
    }
  }, [text, targetLanguage, translate, t])

  // Re-translate when language changes
  const handleLanguageChange = useCallback(
    async (newLanguage: string) => {
      setTargetLanguage(newLanguage)
      if (translateModalOpen) {
        setTranslatedText(null)
        try {
          const result = await translate({ text, targetLanguage: newLanguage })
          setTranslatedText(result.translated_text)
        } catch (err) {
          setTranslatedText(t("option:documentWorkspace.translationFailed", "Translation failed. Please try again."))
        }
      }
    },
    [text, translateModalOpen, translate, t]
  )

  // Highlight color menu items
  const highlightMenuItems: MenuProps["items"] = HIGHLIGHT_COLORS.map((c) => ({
    key: c.key,
    label: (
      <div className="flex items-center gap-2">
        <div
          className="h-4 w-4 rounded border border-border"
          style={{ backgroundColor: c.color }}
        />
        <span>{c.label}</span>
      </div>
    ),
    onClick: () => handleHighlight(c.key)
  }))

  return (
    <>
      <div
        ref={popoverRef}
        data-selection-popover
        className="fixed z-[100] flex items-center gap-1 rounded-lg border border-border bg-surface p-1.5 shadow-lg"
        style={{
          left: adjustedPosition.x,
          top: adjustedPosition.y
        }}
      >
        {/* Copy */}
        <Button
          type="text"
          size="small"
          icon={<Copy className="h-4 w-4" />}
          onClick={handleCopy}
          title={t("common:copy", "Copy")}
        />

        {/* Highlight */}
        <Dropdown menu={{ items: highlightMenuItems }} trigger={["click"]}>
          <Button
            type="text"
            size="small"
            icon={<Highlighter className="h-4 w-4" />}
            title={t("option:documentWorkspace.highlight", "Highlight")}
          >
            <ChevronDown className="h-3 w-3 ml-0.5" />
          </Button>
        </Dropdown>

        {/* Translate */}
        <Button
          type="text"
          size="small"
          icon={<Languages className="h-4 w-4" />}
          onClick={handleTranslate}
          title={t("option:documentWorkspace.translate", "Translate")}
        />

        {/* Ask AI */}
        <Button
          type="text"
          size="small"
          icon={<MessageSquare className="h-4 w-4" />}
          onClick={handleAskAI}
          title={t("option:documentWorkspace.askAI", "Ask AI")}
        />

        {/* Listen (TTS) */}
        <Button
          type="text"
          size="small"
          icon={<Volume2 className="h-4 w-4" />}
          onClick={handleListen}
          loading={ttsState.isLoading}
          title={t("option:documentWorkspace.listen", "Listen")}
          className={ttsState.isPlaying && ttsState.currentText === text ? "text-primary" : ""}
        />
      </div>

      {/* Translation Modal */}
      <Modal
        title={t("option:documentWorkspace.translation", "Translation")}
        open={translateModalOpen}
        onCancel={() => setTranslateModalOpen(false)}
        footer={[
          <Button key="close" onClick={() => setTranslateModalOpen(false)}>
            {t("common:close", "Close")}
          </Button>,
          <Button
            key="copy"
            type="primary"
            disabled={!translatedText || translating}
            onClick={async () => {
              if (translatedText) {
                await navigator.clipboard.writeText(translatedText)
                message.success(t("option:documentWorkspace.copiedToClipboard", "Copied to clipboard"))
              }
            }}
          >
            {t("common:copy", "Copy")}
          </Button>
        ]}
        width={500}
      >
        <div className="space-y-4">
          {/* Original text */}
          <div>
            <div className="text-xs font-medium text-muted mb-1">
              {t("option:documentWorkspace.originalText", "Original")}
            </div>
            <div className="rounded border border-border bg-surface2 p-3 text-sm max-h-32 overflow-auto">
              {text}
            </div>
          </div>

          {/* Target language selector */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted">
              {t("option:documentWorkspace.translateTo", "Translate to:")}
            </span>
            <Select
              value={targetLanguage}
              onChange={handleLanguageChange}
              options={TARGET_LANGUAGES}
              size="small"
              className="w-32"
            />
          </div>

          {/* Translated text */}
          <div>
            <div className="text-xs font-medium text-muted mb-1">
              {t("option:documentWorkspace.translatedText", "Translation")}
            </div>
            <div className="rounded border border-border bg-surface2 p-3 text-sm min-h-[80px] max-h-48 overflow-auto">
              {translating ? (
                <div className="flex items-center justify-center py-4">
                  <Spin size="small" />
                  <span className="ml-2 text-muted">
                    {t("option:documentWorkspace.translating", "Translating...")}
                  </span>
                </div>
              ) : (
                translatedText || (
                  <span className="text-muted">
                    {t("option:documentWorkspace.clickTranslate", "Click translate to see result")}
                  </span>
                )
              )}
            </div>
          </div>
        </div>
      </Modal>
    </>
  )
}

export default TextSelectionPopover
