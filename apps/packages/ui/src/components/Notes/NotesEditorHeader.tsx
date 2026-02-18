import React from 'react'
import { Button, Tag, Tooltip, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import {
  Link2 as LinkIcon,
  Plus as PlusIcon,
  Copy as CopyIcon,
  FileDown as FileDownIcon,
  Save as SaveIcon,
  Trash2 as TrashIcon,
  Eye as EyeIcon,
  Edit3 as EditIcon,
  Columns2 as SplitIcon
} from 'lucide-react'

interface NotesEditorHeaderProps {
  title: string
  selectedId: string | number | null
  backlinkConversationId: string | null
  backlinkMessageId: string | null
  editorDisabled: boolean
  openingLinkedChat: boolean
  editorMode: 'edit' | 'split' | 'preview'
  hasContent: boolean
  canSave: boolean
  canExport: boolean
  isSaving: boolean
  canDelete: boolean
  isDirty?: boolean
  onOpenLinkedConversation: () => void
  onNewNote: () => void
  onChangeEditorMode: (mode: 'edit' | 'split' | 'preview') => void
  onCopy: () => void
  onExport: () => void
  onSave: () => void
  onDelete: () => void
}

const NotesEditorHeader: React.FC<NotesEditorHeaderProps> = ({
  title,
  selectedId,
  backlinkConversationId,
  backlinkMessageId,
  editorDisabled,
  openingLinkedChat,
  editorMode,
  hasContent,
  canSave,
  canExport,
  isSaving,
  canDelete,
  isDirty,
  onOpenLinkedConversation,
  onNewNote,
  onChangeEditorMode,
  onCopy,
  onExport,
  onSave,
  onDelete
}) => {
  const { t } = useTranslation(['option', 'common'])

  const displayTitle =
    selectedId == null
      ? t('option:notesSearch.newNoteTitle', { defaultValue: 'New note' })
      : title ||
        t('option:notesSearch.untitledNote', {
          defaultValue: `Note ${selectedId}`
        })

  return (
    <div className="flex items-center justify-between gap-4 px-4 py-3 border-b border-border bg-surface">
      <div className="flex flex-col gap-0.5 min-w-0">
        <div className="flex items-center gap-2">
          <Typography.Title level={5} className="!mb-0 truncate !text-text">
            {displayTitle}
          </Typography.Title>
          {isDirty && (
            <Tag color="orange" className="!text-[10px] !px-1.5 !py-0 !leading-4 !m-0">
              {t('option:notesSearch.unsaved', { defaultValue: 'Unsaved' })}
            </Tag>
          )}
        </div>
        {backlinkConversationId && (
          <div className="text-xs text-primary">
            {t('option:notesSearch.linkedConversation', {
              defaultValue: 'Linked to conversation'
            })}{' '}
            {backlinkConversationId}
            {backlinkMessageId ? ` · msg ${backlinkMessageId}` : ''}
          </div>
        )}
      </div>
      <div className="flex items-center gap-2" data-testid="notes-header-actions">
        <Tooltip
          title={
            !canSave
              ? t('option:notesSearch.toolbarSaveDisabledTooltip', {
                  defaultValue: 'Add a title or content to save'
                })
              : t('option:notesSearch.toolbarSaveTooltip', {
                  defaultValue: 'Save note'
                })
          }
        >
          <Button
            type="primary"
            size="small"
            onClick={onSave}
            loading={isSaving}
            disabled={!canSave}
            icon={(<SaveIcon className="w-4 h-4" />) as any}
            aria-label={t('option:notesSearch.toolbarSaveTooltip', {
              defaultValue: 'Save note'
            })}
            data-testid="notes-save-button"
          >
            {t('common:save', { defaultValue: 'Save' })}
          </Button>
        </Tooltip>
        <div className="flex items-center gap-2">
          {!editorDisabled && (
            <>
              {backlinkConversationId && (
                <Tooltip
                  title={t('option:notesSearch.openConversationTooltip', {
                    defaultValue: 'Open linked conversation'
                  })}
                >
                  <Button
                    size="small"
                    loading={openingLinkedChat}
                    onClick={onOpenLinkedConversation}
                    icon={(<LinkIcon className="w-4 h-4" />) as any}
                  >
                    {t('option:notesSearch.openConversation', {
                      defaultValue: 'Open conversation'
                    })}
                  </Button>
                </Tooltip>
              )}
              <Tooltip
                title={t('option:notesSearch.newTooltip', {
                  defaultValue: 'Create a new note'
                })}
              >
                <Button
                  data-testid="notes-new-button"
                  size="small"
                  onClick={onNewNote}
                  icon={(<PlusIcon className="w-4 h-4" />) as any}
                >
                  {t('option:notesSearch.new', {
                    defaultValue: 'New note'
                  })}
                </Button>
              </Tooltip>
            </>
          )}
          <div
            className="inline-flex items-center gap-1 rounded-md border border-border p-0.5"
            role="group"
            aria-label={t('option:notesSearch.editorModeGroup', {
              defaultValue: 'Editor mode'
            })}
          >
            <Tooltip
              title={t('option:notesSearch.toolbarEditModeTooltip', {
                defaultValue: 'Write markdown content'
              })}
            >
              <Button
                size="small"
                type={editorMode === 'edit' ? 'primary' : 'text'}
                onClick={() => onChangeEditorMode('edit')}
                icon={(<EditIcon className="w-4 h-4" />) as any}
                aria-pressed={editorMode === 'edit'}
                aria-label={t('option:notesSearch.editModeLabel', {
                  defaultValue: 'Edit'
                })}
              >
                {t('option:notesSearch.editModeLabel', {
                  defaultValue: 'Edit'
                })}
              </Button>
            </Tooltip>
            <Tooltip
              title={t('option:notesSearch.toolbarSplitModeTooltip', {
                defaultValue: 'Show editor and preview together'
              })}
            >
              <Button
                size="small"
                type={editorMode === 'split' ? 'primary' : 'text'}
                onClick={() => onChangeEditorMode('split')}
                icon={(<SplitIcon className="w-4 h-4" />) as any}
                aria-pressed={editorMode === 'split'}
                aria-label={t('option:notesSearch.splitModeLabel', {
                  defaultValue: 'Split'
                })}
              >
                {t('option:notesSearch.splitModeLabel', {
                  defaultValue: 'Split'
                })}
              </Button>
            </Tooltip>
            <Tooltip
              title={t('option:notesSearch.toolbarPreviewTooltip', {
                defaultValue: 'Preview rendered Markdown'
              })}
            >
              <Button
                size="small"
                type={editorMode === 'preview' ? 'primary' : 'text'}
                onClick={() => onChangeEditorMode('preview')}
                icon={(<EyeIcon className="w-4 h-4" />) as any}
                aria-pressed={editorMode === 'preview'}
                aria-label={t('option:notesSearch.previewModeLabel', {
                  defaultValue: 'Preview'
                })}
              >
                {t('option:notesSearch.previewModeLabel', {
                  defaultValue: 'Preview'
                })}
              </Button>
            </Tooltip>
          </div>
          <Tooltip
            title={t('option:notesSearch.toolbarCopyTooltip', {
              defaultValue: 'Copy note content'
            })}
          >
            <Button
              size="small"
              onClick={onCopy}
              icon={(<CopyIcon className="w-4 h-4" />) as any}
              disabled={!hasContent}
              aria-label={t('option:notesSearch.toolbarCopyTooltip', {
                defaultValue: 'Copy note content'
              })}
            />
          </Tooltip>
          <Tooltip
            title={t('option:notesSearch.toolbarExportMdTooltip', {
              defaultValue: 'Export note as Markdown (.md)'
            })}
          >
            <Button
              size="small"
              onClick={onExport}
              icon={(<FileDownIcon className="w-4 h-4" />) as any}
              disabled={!canExport}
              aria-label={t('option:notesSearch.toolbarExportMdTooltip', {
                defaultValue: 'Export note as Markdown (.md)'
              })}
            >
              MD
            </Button>
          </Tooltip>
        </div>
        <span
          className="h-5 w-px bg-border"
          data-testid="notes-destructive-divider"
          aria-hidden="true"
        />
        <Tooltip
          title={t('option:notesSearch.toolbarDeleteTooltip', {
            defaultValue: 'Delete note'
          })}
        >
          <Button
            danger
            size="small"
            onClick={onDelete}
            icon={(<TrashIcon className="w-4 h-4" />) as any}
            disabled={!canDelete}
            aria-label={t('option:notesSearch.toolbarDeleteTooltip', {
              defaultValue: 'Delete note'
            })}
            data-testid="notes-delete-button"
          >
            {t('common:delete', { defaultValue: 'Delete' })}
          </Button>
        </Tooltip>
      </div>
    </div>
  )
}

export default NotesEditorHeader
