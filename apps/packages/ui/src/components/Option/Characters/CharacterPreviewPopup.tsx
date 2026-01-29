import { Modal, Button, Tooltip } from "antd"
import { MessageCircle, Pen, Copy, History, Trash2, Download } from "lucide-react"
import { useTranslation } from "react-i18next"
import { CharacterPreview } from "./CharacterPreview"

interface CharacterPreviewPopupProps {
  character: {
    id?: string
    slug?: string
    name?: string
    description?: string
    avatar_url?: string
    image_base64?: string
    system_prompt?: string
    greeting?: string
    first_message?: string
    tags?: string[]
  } | null
  open: boolean
  onClose: () => void
  onChat: () => void
  onEdit: () => void
  onDuplicate: () => void
  onExport: () => void
  onDelete: () => void
  onViewConversations: () => void
  deleting?: boolean
  exporting?: boolean
}

export function CharacterPreviewPopup({
  character,
  open,
  onClose,
  onChat,
  onEdit,
  onDuplicate,
  onExport,
  onDelete,
  onViewConversations,
  deleting = false,
  exporting = false
}: CharacterPreviewPopupProps) {
  const { t } = useTranslation(["settings", "common"])

  if (!character) return null

  const displayName =
    character.name ||
    t("settings:manageCharacters.preview.untitled", {
      defaultValue: "Untitled character"
    })

  const chatLabel = t("settings:manageCharacters.actions.chat", {
    defaultValue: "Chat"
  })
  const editLabel = t("settings:manageCharacters.actions.edit", {
    defaultValue: "Edit"
  })
  const duplicateLabel = t("settings:manageCharacters.actions.duplicate", {
    defaultValue: "Duplicate"
  })
  const exportLabel = t("settings:manageCharacters.actions.export", {
    defaultValue: "Export"
  })
  const deleteLabel = t("settings:manageCharacters.actions.delete", {
    defaultValue: "Delete"
  })
  const viewConversationsLabel = t(
    "settings:manageCharacters.actions.viewConversations",
    {
      defaultValue: "View conversations"
    }
  )

  return (
    <Modal
      title={t("settings:manageCharacters.gallery.previewTitle", {
        defaultValue: "Character Preview"
      })}
      open={open}
      onCancel={onClose}
      footer={null}
      destroyOnHidden
      width={480}
    >
      <div className="space-y-4">
        {/* Character Preview Content */}
        <CharacterPreview
          name={character.name}
          description={character.description}
          avatar_url={character.avatar_url}
          image_base64={character.image_base64}
          system_prompt={character.system_prompt}
          greeting={character.greeting || character.first_message}
          tags={character.tags}
        />

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center justify-center gap-2 border-t border-border pt-4">
          <Button
            type="primary"
            icon={<MessageCircle className="w-4 h-4" />}
            onClick={onChat}
          >
            {chatLabel}
          </Button>

          <Tooltip title={editLabel}>
            <Button
              icon={<Pen className="w-4 h-4" />}
              onClick={onEdit}
              aria-label={t("settings:manageCharacters.aria.edit", {
                defaultValue: "Edit character {{name}}",
                name: displayName
              })}
            >
              {editLabel}
            </Button>
          </Tooltip>

          <Tooltip title={duplicateLabel}>
            <Button
              icon={<Copy className="w-4 h-4" />}
              onClick={onDuplicate}
              aria-label={t("settings:manageCharacters.aria.duplicate", {
                defaultValue: "Duplicate character {{name}}",
                name: displayName
              })}
            >
              {duplicateLabel}
            </Button>
          </Tooltip>

          <Tooltip title={exportLabel}>
            <Button
              icon={<Download className="w-4 h-4" />}
              onClick={onExport}
              loading={exporting}
              aria-label={t("settings:manageCharacters.aria.export", {
                defaultValue: "Export character {{name}}",
                name: displayName
              })}
            >
              {exportLabel}
            </Button>
          </Tooltip>

          <Tooltip title={viewConversationsLabel}>
            <Button
              icon={<History className="w-4 h-4" />}
              onClick={onViewConversations}
              aria-label={t("settings:manageCharacters.aria.viewConversations", {
                defaultValue: "View conversations for {{name}}",
                name: displayName
              })}
            >
              {viewConversationsLabel}
            </Button>
          </Tooltip>

          <Tooltip title={deleteLabel}>
            <Button
              danger
              icon={<Trash2 className="w-4 h-4" />}
              onClick={onDelete}
              loading={deleting}
              aria-label={t("settings:manageCharacters.aria.delete", {
                defaultValue: "Delete character {{name}}",
                name: displayName
              })}
            >
              {deleteLabel}
            </Button>
          </Tooltip>
        </div>
      </div>
    </Modal>
  )
}
