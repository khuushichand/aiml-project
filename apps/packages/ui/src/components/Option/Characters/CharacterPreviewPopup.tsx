import React from "react"
import { Modal, Button, Tooltip, Dropdown } from "antd"
import { MessageCircle, Pen, Copy, History, Trash2, Download, ExternalLink, Clock3, Info, MoreHorizontal, UserCircle2 } from "lucide-react"
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
  onQuickChat: () => void
  onChat: () => void
  onChatInNewTab: () => void
  onEdit: () => void
  onDuplicate: () => void
  onExport: (format?: 'json' | 'png') => void
  onDelete: () => void
  onViewConversations: () => void
  onCreatePersonaFromCharacter: () => void
  onOpenPersonaGarden: () => void
  onViewVersionHistory: () => void
  creatingPersonaFromCharacter?: boolean
  attachedWorldBooks?: Array<{ id: number; name: string }>
  attachedWorldBooksLoading?: boolean
  launchedFromWorldBooks?: boolean
  launchedFromWorldBookId?: number | null
  deleting?: boolean
  exporting?: boolean
}

export function CharacterPreviewPopup({
  character,
  open,
  onClose,
  onQuickChat,
  onChat,
  onChatInNewTab,
  onEdit,
  onDuplicate,
  onExport,
  onDelete,
  onViewConversations,
  onCreatePersonaFromCharacter,
  onOpenPersonaGarden,
  onViewVersionHistory,
  creatingPersonaFromCharacter = false,
  attachedWorldBooks = [],
  attachedWorldBooksLoading = false,
  launchedFromWorldBooks = false,
  launchedFromWorldBookId = null,
  deleting = false,
  exporting = false
}: CharacterPreviewPopupProps) {
  const { t } = useTranslation(["settings", "common"])
  const [fullImageOpen, setFullImageOpen] = React.useState(false)
  const [fullImageSrc, setFullImageSrc] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!open) {
      setFullImageOpen(false)
      setFullImageSrc(null)
    }
  }, [open])

  if (!character) return null

  const displayName =
    character.name ||
    t("settings:manageCharacters.preview.untitled", {
      defaultValue: "Untitled character"
    })

  const chatLabel = t("settings:manageCharacters.actions.chat", {
    defaultValue: "Chat"
  })
  const quickChatLabel = t("settings:manageCharacters.actions.quickChat", {
    defaultValue: "Test in popup"
  })
  const chatInNewTabLabel = t("settings:manageCharacters.actions.chatInNewTab", {
    defaultValue: "Chat in new tab"
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
  const versionHistoryLabel = t(
    "settings:manageCharacters.actions.versionHistory",
    {
      defaultValue: "Version history"
    }
  )
  const createPersonaLabel = t(
    creatingPersonaFromCharacter
      ? "settings:manageCharacters.actions.creatingPersonaFromCharacter"
      : "settings:manageCharacters.actions.createPersonaFromCharacter",
    {
      defaultValue: creatingPersonaFromCharacter
        ? "Creating Persona..."
        : "Create Persona from Character"
    }
  )
  const openPersonaGardenLabel = t(
    "settings:manageCharacters.actions.openInPersonaGarden",
    {
      defaultValue: "Open in Persona Garden"
    }
  )
  const characterIdParam = encodeURIComponent(String(character.id || ""))
  const worldBooksWorkspaceHref = `/world-books?from=characters&focusCharacterId=${characterIdParam}`
  const backToWorldBooksHref =
    launchedFromWorldBooks && launchedFromWorldBookId != null
      ? `/world-books?focusWorldBookId=${encodeURIComponent(String(launchedFromWorldBookId))}`
      : "/world-books"

  const exportMenuItems = [
    {
      key: 'json',
      label: t("settings:manageCharacters.export.json", { defaultValue: "Export as JSON" }),
      onClick: () => onExport('json')
    },
    {
      key: 'png',
      label: t("settings:manageCharacters.export.png", { defaultValue: "Export as PNG (with metadata)" }),
      onClick: () => onExport('png')
    }
  ]

  const handleOpenFullImage = (src: string) => {
    setFullImageSrc(src)
    setFullImageOpen(true)
  }

  return (
    <>
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
            expandedMetadata
            onAvatarClick={handleOpenFullImage}
            avatarTriggerTestId="character-preview-avatar-button"
            avatarClickAriaLabel={t("settings:manageCharacters.preview.openFullImage", {
              defaultValue: "Open full size image for {{name}}",
              name: displayName
            })}
          />

        <div className="rounded-md border border-border bg-surface p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-1 text-sm font-medium">
              {t("settings:manageCharacters.worldBooks.title", {
                defaultValue: "World Books"
              })}
              <Tooltip title={t("settings:manageCharacters.worldBooks.hint", {
                defaultValue: "Shared lore documents that provide context during conversations with this character."
              })}>
                <Info className="h-3.5 w-3.5 text-text-muted cursor-help" />
              </Tooltip>
            </div>
            <a
              href={worldBooksWorkspaceHref}
              className="text-xs text-primary hover:underline"
              aria-label={t("settings:manageCharacters.worldBooks.openWorkspaceAria", {
                defaultValue: "Open World Books workspace"
              })}
            >
              {t("settings:manageCharacters.worldBooks.openWorkspace", {
                defaultValue: "Open workspace"
              })}
            </a>
          </div>

          {launchedFromWorldBooks && (
            <div className="mt-2">
              <a
                href={backToWorldBooksHref}
                className="text-xs text-primary hover:underline"
                aria-label={t("settings:manageCharacters.worldBooks.backAria", {
                  defaultValue: "Back to World Books"
                })}
              >
                {t("settings:manageCharacters.worldBooks.back", {
                  defaultValue: "Back to World Books"
                })}
              </a>
            </div>
          )}

          <div className="mt-2">
            {attachedWorldBooksLoading ? (
              <div className="text-xs text-text-muted">
                {t("settings:manageCharacters.worldBooks.loading", {
                  defaultValue: "Loading attached world books..."
                })}
              </div>
            ) : attachedWorldBooks.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {attachedWorldBooks.map((worldBook) => (
                  <a
                    key={worldBook.id}
                    href={`${worldBooksWorkspaceHref}&focusWorldBookId=${encodeURIComponent(
                      String(worldBook.id)
                    )}`}
                    className="inline-flex items-center rounded border border-border px-2 py-1 text-xs text-primary hover:bg-surface2"
                    aria-label={t("settings:manageCharacters.worldBooks.openBookAria", {
                      defaultValue: "Open world book {{name}}",
                      name: worldBook.name
                    })}
                  >
                    {worldBook.name}
                  </a>
                ))}
              </div>
            ) : (
              <div className="text-xs text-text-muted">
                {t("settings:manageCharacters.worldBooks.empty", {
                  defaultValue: "No world books attached to this character."
                })}
              </div>
            )}
          </div>
        </div>

          {/* Action Buttons — primary / secondary / overflow */}
          <div className="flex flex-wrap items-center justify-center gap-2 border-t border-border pt-4">
            {/* Primary action */}
            <Button
              type="primary"
              icon={<MessageCircle className="w-4 h-4" />}
              onClick={onChat}
            >
              {chatLabel}
            </Button>

            {/* Secondary actions */}
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

            {/* Overflow menu */}
            <Dropdown
              menu={{
                items: [
                  {
                    key: "chat-new-tab",
                    icon: <ExternalLink className="w-4 h-4" />,
                    label: chatInNewTabLabel,
                    onClick: onChatInNewTab
                  },
                  {
                    key: "test-in-popup",
                    icon: <MessageCircle className="w-4 h-4" />,
                    label: quickChatLabel,
                    onClick: onQuickChat
                  },
                  {
                    key: "export",
                    icon: <Download className="w-4 h-4" />,
                    label: exportLabel,
                    disabled: exporting,
                    children: exportMenuItems
                  },
                  {
                    key: "conversations",
                    icon: <History className="w-4 h-4" />,
                    label: viewConversationsLabel,
                    onClick: onViewConversations
                  },
                  {
                    key: "create-persona",
                    icon: <UserCircle2 className="w-4 h-4" />,
                    label: createPersonaLabel,
                    disabled: creatingPersonaFromCharacter,
                    onClick: onCreatePersonaFromCharacter
                  },
                  {
                    key: "open-persona-garden",
                    icon: <ExternalLink className="w-4 h-4" />,
                    label: openPersonaGardenLabel,
                    onClick: onOpenPersonaGarden
                  },
                  {
                    key: "version-history",
                    icon: <Clock3 className="w-4 h-4" />,
                    label: versionHistoryLabel,
                    onClick: onViewVersionHistory
                  },
                  { type: "divider" as const },
                  {
                    key: "delete",
                    icon: <Trash2 className="w-4 h-4" />,
                    label: deleteLabel,
                    danger: true,
                    disabled: deleting,
                    onClick: onDelete
                  }
                ]
              }}
              trigger={["click"]}
            >
              <Button
                icon={<MoreHorizontal className="w-4 h-4" />}
                aria-label={t("settings:manageCharacters.aria.moreActions", {
                  defaultValue: "More actions for {{name}}",
                  name: displayName
                })}
              />
            </Dropdown>
          </div>
        </div>
      </Modal>
      <Modal
        title={t("settings:manageCharacters.preview.fullImageTitle", {
          defaultValue: "Character image"
        })}
        open={fullImageOpen}
        onCancel={() => setFullImageOpen(false)}
        footer={null}
        destroyOnHidden
        width="auto"
      >
        <div className="flex items-center justify-center">
          {fullImageSrc && (
            <img
              src={fullImageSrc}
              alt={displayName}
              className="max-h-[80vh] max-w-[90vw] h-auto w-auto object-contain"
              data-testid="character-preview-full-image"
            />
          )}
        </div>
      </Modal>
    </>
  )
}
