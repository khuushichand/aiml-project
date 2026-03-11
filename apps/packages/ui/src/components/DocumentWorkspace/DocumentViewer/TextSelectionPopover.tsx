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
import { useMobile } from "@/hooks/useMediaQuery"
import type { AnnotationColor } from "../types"
import { HIGHLIGHT_COLORS, TARGET_LANGUAGES } from "../config"

interface TextSelectionPopoverProps {
  text: string
  position: { x: number; y: number }
  onClose: () => void
  /** Optional CFI location for EPUB annotations */
  epubCfi?: string
}

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
  const [positionReady, setPositionReady] = useState(false)

  const { mutateAsync: translate, isPending: translating } = useTranslate()
  const { speak, state: ttsState, stop: stopTTS } = useDocumentTTS()

  const activeDocumentId = useDocumentWorkspaceStore((s) => s.activeDocumentId)
  const currentPage = useDocumentWorkspaceStore((s) => s.currentPage)
  const currentPercentage = useDocumentWorkspaceStore((s) => s.currentPercentage)
  const currentChapterTitle = useDocumentWorkspaceStore((s) => s.currentChapterTitle)
  const addAnnotation = useDocumentWorkspaceStore((s) => s.addAnnotation)
  const setActiveRightTab = useDocumentWorkspaceStore((s) => s.setActiveRightTab)

  const isMobileView = useMobile()

  // Dismiss on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose()
      }
    }
    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [onClose])

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
    setPositionReady(true)
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

  // Ask AI - prefill chat with a prompt template about selected text
  const handleAskAI = useCallback((promptTemplate: string) => {
    setActiveRightTab("chat")
    window.dispatchEvent(
      new CustomEvent("document-workspace-ask-ai", {
        detail: { text, prompt: promptTemplate }
      })
    )
    onClose()
  }, [text, setActiveRightTab, onClose])

  // Ask AI prompt templates
  const askAIMenuItems: MenuProps["items"] = [
    {
      key: "explain",
      label: t("option:documentWorkspace.aiExplain", "Explain"),
      onClick: () => handleAskAI(`Explain this passage: "${text}"`)
    },
    {
      key: "summarize",
      label: t("option:documentWorkspace.aiSummarize", "Summarize"),
      onClick: () => handleAskAI(`Summarize this passage: "${text}"`)
    },
    {
      key: "define",
      label: t("option:documentWorkspace.aiDefine", "Define terms"),
      onClick: () => handleAskAI(`Define the key terms in this passage: "${text}"`)
    },
    {
      key: "simplify",
      label: t("option:documentWorkspace.aiSimplify", "Simplify"),
      onClick: () => handleAskAI(`Simplify this passage in plain language: "${text}"`)
    }
  ]

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

  // Shared action buttons used in both desktop popover and mobile bottom sheet
  const actionButtons = (
    <>
      <Button
        type="text"
        size={isMobileView ? "middle" : "small"}
        icon={<Copy className="h-4 w-4" />}
        onClick={handleCopy}
        aria-label={t("common:copy", "Copy")}
      >
        {isMobileView && <span className="text-xs">{t("common:copy", "Copy")}</span>}
      </Button>

      <Dropdown menu={{ items: highlightMenuItems }} trigger={["click"]}>
        <Button
          type="text"
          size={isMobileView ? "middle" : "small"}
          icon={<Highlighter className="h-4 w-4" />}
          aria-label={t("option:documentWorkspace.highlight", "Highlight")}
        >
          {isMobileView && <span className="text-xs">{t("option:documentWorkspace.highlight", "Highlight")}</span>}
          <ChevronDown className="h-3 w-3 ml-0.5" />
        </Button>
      </Dropdown>

      <Button
        type="text"
        size={isMobileView ? "middle" : "small"}
        icon={<Languages className="h-4 w-4" />}
        onClick={handleTranslate}
        aria-label={t("option:documentWorkspace.translate", "Translate")}
      >
        {isMobileView && <span className="text-xs">{t("option:documentWorkspace.translate", "Translate")}</span>}
      </Button>

      <Dropdown menu={{ items: askAIMenuItems }} trigger={["click"]}>
        <Button
          type="text"
          size={isMobileView ? "middle" : "small"}
          icon={<MessageSquare className="h-4 w-4" />}
          aria-label={t("option:documentWorkspace.askAI", "Ask AI")}
        >
          {isMobileView && <span className="text-xs">{t("option:documentWorkspace.askAI", "Ask AI")}</span>}
          <ChevronDown className="h-3 w-3 ml-0.5" />
        </Button>
      </Dropdown>

      <Button
        type="text"
        size={isMobileView ? "middle" : "small"}
        icon={<Volume2 className="h-4 w-4" />}
        onClick={handleListen}
        loading={ttsState.isLoading}
        aria-label={t("option:documentWorkspace.listen", "Listen")}
        className={ttsState.isPlaying && ttsState.currentText === text ? "text-primary" : ""}
      >
        {isMobileView && <span className="text-xs">{t("option:documentWorkspace.listen", "Listen")}</span>}
      </Button>
    </>
  )

  return (
    <>
      {isMobileView ? (
        // Mobile: bottom sheet
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-[99] bg-black/20"
            onClick={onClose}
          />
          <div
            ref={popoverRef}
            data-selection-popover
            className="fixed bottom-0 left-0 right-0 z-[100] rounded-t-xl border-t border-border bg-surface px-4 pb-[env(safe-area-inset-bottom,8px)] pt-3 shadow-2xl animate-in slide-in-from-bottom duration-200"
          >
            {/* Drag handle */}
            <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-border" />
            {/* Selected text preview */}
            <p className="mb-3 line-clamp-2 text-xs text-text-muted italic">"{text}"</p>
            {/* Actions */}
            <div className="flex flex-wrap items-center gap-2">
              {actionButtons}
            </div>
          </div>
        </>
      ) : (
        // Desktop: floating popover
        <div
          ref={popoverRef}
          data-selection-popover
          className="fixed z-[100] flex items-center gap-1 rounded-lg border border-border bg-surface p-1.5 shadow-lg"
          style={{
            left: adjustedPosition.x,
            top: adjustedPosition.y,
            opacity: positionReady ? 1 : 0,
            pointerEvents: positionReady ? "auto" : "none",
            transition: "opacity 100ms"
          }}
        >
          {actionButtons}
        </div>
      )}

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
