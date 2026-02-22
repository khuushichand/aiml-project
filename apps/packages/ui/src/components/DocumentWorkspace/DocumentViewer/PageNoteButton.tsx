import React, { useState, useCallback } from "react"
import { useTranslation } from "react-i18next"
import { Button, Modal, Input, Dropdown, message } from "antd"
import type { MenuProps } from "antd"
import { StickyNote } from "lucide-react"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import type { AnnotationColor } from "../types"

const { TextArea } = Input

// theme-exempt: user annotation colors
const NOTE_COLORS: Array<{ key: AnnotationColor; label: string; color: string }> = [
  { key: "yellow", label: "Yellow", color: "#fef08a" },
  { key: "green", label: "Green", color: "#bbf7d0" },
  { key: "blue", label: "Blue", color: "#bfdbfe" },
  { key: "pink", label: "Pink", color: "#fbcfe8" }
]

interface PageNoteButtonProps {
  pageNumber: number
}

/**
 * Floating button that appears on each PDF page to add a page note.
 * Unlike highlights which require text selection, page notes can be added
 * at any point on a page without selecting text.
 */
export const PageNoteButton: React.FC<PageNoteButtonProps> = ({ pageNumber }) => {
  const { t } = useTranslation(["option", "common"])
  const [modalOpen, setModalOpen] = useState(false)
  const [noteText, setNoteText] = useState("")
  const [selectedColor, setSelectedColor] = useState<AnnotationColor>("yellow")

  const activeDocumentId = useDocumentWorkspaceStore((s) => s.activeDocumentId)
  const addAnnotation = useDocumentWorkspaceStore((s) => s.addAnnotation)

  const handleOpenModal = useCallback((color: AnnotationColor) => {
    setSelectedColor(color)
    setModalOpen(true)
  }, [])

  const handleClose = useCallback(() => {
    setModalOpen(false)
    setNoteText("")
  }, [])

  const handleSave = useCallback(() => {
    if (!activeDocumentId || !noteText.trim()) return

    addAnnotation({
      documentId: activeDocumentId,
      location: pageNumber,
      text: "", // Page notes have empty text (no selection)
      color: selectedColor,
      note: noteText.trim(),
      annotationType: "page_note"
    })

    message.success(t("option:documentWorkspace.noteAdded", "Note added"))
    handleClose()
  }, [activeDocumentId, pageNumber, noteText, selectedColor, addAnnotation, handleClose, t])

  // Color menu items for dropdown
  const colorMenuItems: MenuProps["items"] = NOTE_COLORS.map((c) => ({
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
    onClick: () => handleOpenModal(c.key)
  }))

  return (
    <>
      <Dropdown
        menu={{ items: colorMenuItems }}
        trigger={["click"]}
        placement="bottomRight"
      >
        <Button
          type="text"
          size="small"
          icon={<StickyNote className="h-4 w-4" />}
          className="absolute right-2 top-2 z-10 opacity-0 transition-opacity group-hover:opacity-100 bg-surface/80 hover:bg-surface shadow-sm"
          title={t("option:documentWorkspace.addPageNote", "Add page note")}
        />
      </Dropdown>

      <Modal
        title={t("option:documentWorkspace.addPageNote", "Add Page Note")}
        open={modalOpen}
        onCancel={handleClose}
        onOk={handleSave}
        okText={t("common:save", "Save")}
        cancelText={t("common:cancel", "Cancel")}
        okButtonProps={{ disabled: !noteText.trim() }}
      >
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm text-text-secondary">
            <span>{t("option:documentWorkspace.page", "Page")} {pageNumber}</span>
            <span className="text-border">|</span>
            <div className="flex items-center gap-1">
              <div
                className="h-3 w-3 rounded border border-border"
                style={{ backgroundColor: NOTE_COLORS.find(c => c.key === selectedColor)?.color }}
              />
              <span>{NOTE_COLORS.find(c => c.key === selectedColor)?.label}</span>
            </div>
          </div>
          <TextArea
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            placeholder={t(
              "option:documentWorkspace.pageNotePlaceholder",
              "Write your note about this page..."
            )}
            autoSize={{ minRows: 4, maxRows: 10 }}
            autoFocus
          />
        </div>
      </Modal>
    </>
  )
}

export default PageNoteButton
