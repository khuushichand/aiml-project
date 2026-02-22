import React from 'react'
import { Button, Dropdown, Tag, Tooltip, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import { useMobile } from '@/hooks/useMediaQuery'
import {
  Link2 as LinkIcon,
  Plus as PlusIcon,
  Sparkles as SparklesIcon,
  Copy as CopyIcon,
  FileDown as FileDownIcon,
  FilePlus2 as FileTemplateIcon,
  Save as SaveIcon,
  Star as StarIcon,
  Trash2 as TrashIcon,
  Eye as EyeIcon,
  Edit3 as EditIcon,
  Columns2 as SplitIcon
} from 'lucide-react'

interface NotesEditorHeaderProps {
  title: string
  selectedId: string | number | null
  backlinkConversationId: string | null
  backlinkConversationLabel: string | null
  backlinkMessageId: string | null
  sourceLinks: Array<{ id: string; label: string }>
  editorDisabled: boolean
  openingLinkedChat: boolean
  editorMode: 'edit' | 'split' | 'preview'
  hasContent: boolean
  canSave: boolean
  canGenerateFlashcards: boolean
  canExport: boolean
  canDuplicate?: boolean
  canPin?: boolean
  isPinned?: boolean
  templateOptions?: Array<{ id: string; label: string }>
  isSaving: boolean
  canDelete: boolean
  isDirty?: boolean
  onOpenLinkedConversation: () => void
  onOpenSourceLink: (sourceId: string, sourceLabel: string) => void
  onNewNote: () => void
  onApplyTemplate?: (templateId: string) => void
  onDuplicate?: () => void
  onTogglePin?: () => void
  onChangeEditorMode: (mode: 'edit' | 'split' | 'preview') => void
  onCopy: (mode: 'content' | 'markdown') => void
  onGenerateFlashcards: () => void
  onExport: (format: 'md' | 'json' | 'print') => void
  onSave: () => void
  onDelete: () => void
}

const NotesEditorHeader: React.FC<NotesEditorHeaderProps> = ({
  title,
  selectedId,
  backlinkConversationId,
  backlinkConversationLabel,
  backlinkMessageId,
  sourceLinks,
  editorDisabled,
  openingLinkedChat,
  editorMode,
  hasContent,
  canSave,
  canGenerateFlashcards,
  canExport,
  canDuplicate = false,
  canPin = false,
  isPinned = false,
  templateOptions = [],
  isSaving,
  canDelete,
  isDirty,
  onOpenLinkedConversation,
  onOpenSourceLink,
  onNewNote,
  onApplyTemplate,
  onDuplicate,
  onTogglePin,
  onChangeEditorMode,
  onCopy,
  onGenerateFlashcards,
  onExport,
  onSave,
  onDelete
}) => {
  const { t } = useTranslation(['option', 'common'])
  const isMobileViewport = useMobile()
  const toolbarButtonSize: 'small' | 'large' = isMobileViewport ? 'large' : 'small'
  const touchTargetClass = isMobileViewport ? 'min-h-[44px]' : undefined
  const touchTargetIconOnlyClass = isMobileViewport ? 'min-h-[44px] min-w-[44px]' : undefined

  const displayTitle =
    selectedId == null
      ? t('option:notesSearch.newNoteTitle', { defaultValue: 'New note' })
      : title ||
        t('option:notesSearch.untitledNote', {
          defaultValue: `Note ${selectedId}`
        })
  const conversationDisplayText = backlinkConversationLabel || backlinkConversationId
  const conversationDebugTooltip =
    backlinkConversationId != null
      ? `${t('option:notesSearch.linkedConversationIdLabel', {
          defaultValue: 'Conversation ID'
        })}: ${backlinkConversationId}`
      : null

  return (
    <div className="flex flex-col gap-3 border-b border-border bg-surface px-4 py-3 md:flex-row md:items-center md:justify-between">
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
            })}{': '}
            <Tooltip title={conversationDebugTooltip}>
              <span className="font-medium">{conversationDisplayText}</span>
            </Tooltip>
            {backlinkMessageId ? ` · msg ${backlinkMessageId}` : ''}
          </div>
        )}
        {sourceLinks.length > 0 && (
          <div className="mt-1 flex flex-wrap items-center gap-1">
            <span className="text-[11px] text-text-muted">
              {t('option:notesSearch.linkedSourcesLabel', {
                defaultValue: 'Sources'
              })}
              {':'}
            </span>
            {sourceLinks.map((source) => (
              <Tooltip
                key={`source-link-${source.id}`}
                title={`${t('option:notesSearch.linkedSourceIdLabel', {
                  defaultValue: 'Source node'
                })}: ${source.id}`}
              >
                <Button
                  type="link"
                  size="small"
                  className="!h-auto !px-1 text-xs"
                  onClick={() => onOpenSourceLink(source.id, source.label)}
                  data-testid={`notes-source-link-${source.id.replace(/[^a-z0-9_-]/gi, '_')}`}
                >
                  {source.label}
                </Button>
              </Tooltip>
            ))}
          </div>
        )}
      </div>
      <div
        className={
          isMobileViewport
            ? 'flex w-full flex-wrap items-center justify-start gap-2'
            : 'flex items-center gap-2'
        }
        data-testid="notes-header-actions"
      >
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
            size={toolbarButtonSize}
            onClick={onSave}
            loading={isSaving}
            disabled={!canSave}
            icon={(<SaveIcon className="w-4 h-4" />) as any}
            className={touchTargetClass}
            aria-label={t('option:notesSearch.toolbarSaveTooltip', {
              defaultValue: 'Save note'
            })}
            data-testid="notes-save-button"
          >
            {t('common:save', { defaultValue: 'Save' })}
          </Button>
        </Tooltip>
        <div
          className={
            isMobileViewport ? 'flex w-full flex-wrap items-center gap-2' : 'flex items-center gap-2'
          }
        >
          {!editorDisabled && (
            <>
              {backlinkConversationId && (
                <Tooltip
                  title={t('option:notesSearch.openConversationTooltip', {
                    defaultValue: 'Open linked conversation'
                  })}
                >
                  <Button
                    size={toolbarButtonSize}
                    loading={openingLinkedChat}
                    onClick={onOpenLinkedConversation}
                    icon={(<LinkIcon className="w-4 h-4" />) as any}
                    className={touchTargetClass}
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
                  size={toolbarButtonSize}
                  onClick={onNewNote}
                  icon={(<PlusIcon className="w-4 h-4" />) as any}
                  className={touchTargetClass}
                >
                  {t('option:notesSearch.new', {
                    defaultValue: 'New note'
                  })}
                  </Button>
                </Tooltip>
              {onApplyTemplate && templateOptions.length > 0 && (
                <Dropdown
                  trigger={['click']}
                  menu={{
                    onClick: ({ key }) => {
                      onApplyTemplate(String(key))
                    },
                    items: templateOptions.map((template) => ({
                      key: template.id,
                      label: template.label
                    }))
                  }}
                >
                  <Tooltip
                    title={t('option:notesSearch.templateTooltip', {
                      defaultValue: 'Create from template'
                    })}
                  >
                    <Button
                      size={toolbarButtonSize}
                      icon={(<FileTemplateIcon className="w-4 h-4" />) as any}
                      className={touchTargetClass}
                      data-testid="notes-template-button"
                    >
                      {t('option:notesSearch.templateAction', {
                        defaultValue: 'Template'
                      })}
                    </Button>
                  </Tooltip>
                </Dropdown>
              )}
              {onDuplicate && (
                <Tooltip
                  title={t('option:notesSearch.duplicateNoteTooltip', {
                    defaultValue: 'Duplicate this note'
                  })}
                >
                  <Button
                    size={toolbarButtonSize}
                    onClick={onDuplicate}
                    disabled={!canDuplicate}
                    icon={(<CopyIcon className="w-4 h-4" />) as any}
                    className={touchTargetClass}
                    data-testid="notes-duplicate-button"
                  >
                    {t('option:notesSearch.duplicateNoteAction', {
                      defaultValue: 'Duplicate'
                    })}
                  </Button>
                </Tooltip>
              )}
              {onTogglePin && (
                <Tooltip
                  title={
                    isPinned
                      ? t('option:notesSearch.unpinNoteTooltip', {
                          defaultValue: 'Unpin this note'
                        })
                      : t('option:notesSearch.pinNoteTooltip', {
                          defaultValue: 'Pin this note'
                        })
                  }
                >
                  <Button
                    size={toolbarButtonSize}
                    onClick={onTogglePin}
                    disabled={!canPin}
                    icon={
                      (<StarIcon className={`w-4 h-4 ${isPinned ? 'fill-current text-amber-500' : ''}`} />) as any
                    }
                    className={touchTargetClass}
                    data-testid="notes-pin-button"
                  >
                    {isPinned
                      ? t('option:notesSearch.unpinNoteAction', {
                          defaultValue: 'Unpin'
                        })
                      : t('option:notesSearch.pinNoteAction', {
                          defaultValue: 'Pin'
                        })}
                  </Button>
                </Tooltip>
              )}
              <Tooltip
                title={t('option:notesSearch.generateFlashcardsTooltip', {
                  defaultValue: 'Generate flashcards from this note'
                })}
              >
                <Button
                  size={toolbarButtonSize}
                  onClick={onGenerateFlashcards}
                  disabled={!canGenerateFlashcards}
                  icon={(<SparklesIcon className="w-4 h-4" />) as any}
                  className={touchTargetClass}
                  data-testid="notes-generate-flashcards-button"
                >
                  {t('option:notesSearch.generateFlashcardsAction', {
                    defaultValue: 'Generate cards'
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
                size={toolbarButtonSize}
                type={editorMode === 'edit' ? 'primary' : 'text'}
                onClick={() => onChangeEditorMode('edit')}
                icon={(<EditIcon className="w-4 h-4" />) as any}
                className={touchTargetClass}
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
                size={toolbarButtonSize}
                type={editorMode === 'split' ? 'primary' : 'text'}
                onClick={() => onChangeEditorMode('split')}
                icon={(<SplitIcon className="w-4 h-4" />) as any}
                className={touchTargetClass}
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
                size={toolbarButtonSize}
                type={editorMode === 'preview' ? 'primary' : 'text'}
                onClick={() => onChangeEditorMode('preview')}
                icon={(<EyeIcon className="w-4 h-4" />) as any}
                className={touchTargetClass}
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
          <Dropdown
            trigger={['click']}
            disabled={!hasContent}
            menu={{
              onClick: ({ key }) => {
                if (key === 'copy-markdown') {
                  onCopy('markdown')
                  return
                }
                onCopy('content')
              },
              items: [
                {
                  key: 'copy-content',
                  label: t('option:notesSearch.copyModeContentOnly', {
                    defaultValue: 'Copy content only'
                  })
                },
                {
                  key: 'copy-markdown',
                  label: t('option:notesSearch.copyModeMarkdown', {
                    defaultValue: 'Copy markdown with title'
                  })
                }
              ]
            }}
          >
            <Tooltip
              title={t('option:notesSearch.toolbarCopyTooltip', {
                defaultValue: 'Copy note'
              })}
            >
              <Button
                size={toolbarButtonSize}
                icon={(<CopyIcon className="w-4 h-4" />) as any}
                disabled={!hasContent}
                className={touchTargetIconOnlyClass}
                aria-label={t('option:notesSearch.toolbarCopyTooltip', {
                  defaultValue: 'Copy note'
                })}
                data-testid="notes-copy-button"
              />
            </Tooltip>
          </Dropdown>
          <Dropdown
            trigger={['click']}
            disabled={!canExport}
            menu={{
              onClick: ({ key }) => {
                if (key === 'export-json') {
                  onExport('json')
                  return
                }
                if (key === 'export-print') {
                  onExport('print')
                  return
                }
                onExport('md')
              },
              items: [
                {
                  key: 'export-md',
                  label: t('option:notesSearch.exportSingleMd', {
                    defaultValue: 'Export as Markdown (.md)'
                  })
                },
                {
                  key: 'export-json',
                  label: t('option:notesSearch.exportSingleJson', {
                    defaultValue: 'Export as JSON (.json)'
                  })
                },
                {
                  key: 'export-print',
                  label: t('option:notesSearch.exportSinglePrint', {
                    defaultValue: 'Print / Save as PDF'
                  })
                }
              ]
            }}
          >
            <Tooltip
              title={t('option:notesSearch.toolbarExportMdTooltip', {
                defaultValue: 'Export note'
              })}
            >
              <Button
                size={toolbarButtonSize}
                icon={(<FileDownIcon className="w-4 h-4" />) as any}
                disabled={!canExport}
                className={touchTargetClass}
                aria-label={t('option:notesSearch.toolbarExportMdTooltip', {
                  defaultValue: 'Export note'
                })}
                data-testid="notes-export-button"
              >
                {t('option:notesSearch.exportSingleAction', {
                  defaultValue: 'Export'
                })}
              </Button>
            </Tooltip>
          </Dropdown>
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
            size={toolbarButtonSize}
            onClick={onDelete}
            icon={(<TrashIcon className="w-4 h-4" />) as any}
            disabled={!canDelete}
            className={touchTargetClass}
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
