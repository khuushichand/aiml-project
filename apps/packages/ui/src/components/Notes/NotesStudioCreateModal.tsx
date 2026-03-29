import React from 'react'
import { Button, Modal, Radio, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import type { NotesStudioHandwritingMode, NotesStudioTemplateType } from './notes-studio-types'
import {
  NOTES_STUDIO_HANDWRITING_OPTIONS,
  NOTES_STUDIO_TEMPLATE_OPTIONS,
} from './notes-manager-utils'

interface NotesStudioCreateModalProps {
  open: boolean
  excerptText: string
  templateType: NotesStudioTemplateType
  handwritingMode: NotesStudioHandwritingMode
  loading?: boolean
  onClose: () => void
  onTemplateChange: (value: NotesStudioTemplateType) => void
  onHandwritingChange: (value: NotesStudioHandwritingMode) => void
  onSubmit: () => void
}

const NotesStudioCreateModal: React.FC<NotesStudioCreateModalProps> = ({
  open,
  excerptText,
  templateType,
  handwritingMode,
  loading = false,
  onClose,
  onTemplateChange,
  onHandwritingChange,
  onSubmit,
}) => {
  const { t } = useTranslation(['option', 'common'])

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      destroyOnHidden
      title={t('option:notesSearch.notesStudioAction', {
        defaultValue: 'Notes Studio',
      })}
    >
      <div className="flex flex-col gap-4" data-testid="notes-studio-create-modal">
        <div className="flex flex-col gap-2">
          <Typography.Text strong>
            {t('option:notesSearch.notesStudioTemplateLabel', {
              defaultValue: 'Choose notebook template',
            })}
          </Typography.Text>
          <Radio.Group
            value={templateType}
            onChange={(event) => onTemplateChange(event.target.value as NotesStudioTemplateType)}
          >
            <div className="flex flex-col gap-2">
              {NOTES_STUDIO_TEMPLATE_OPTIONS.map((option) => (
                <Radio key={option.value} value={option.value}>
                  {t(option.labelKey, { defaultValue: option.defaultLabel })}
                </Radio>
              ))}
            </div>
          </Radio.Group>
        </div>

        <div className="flex flex-col gap-2">
          <Typography.Text strong>
            {t('option:notesSearch.notesStudioHandwritingLabel', {
              defaultValue: 'Handwriting treatment',
            })}
          </Typography.Text>
          <Radio.Group
            value={handwritingMode}
            onChange={(event) => onHandwritingChange(event.target.value as NotesStudioHandwritingMode)}
          >
            <div className="flex flex-col gap-2">
              {NOTES_STUDIO_HANDWRITING_OPTIONS.map((option) => (
                <Radio key={option.value} value={option.value}>
                  {t(option.labelKey, { defaultValue: option.defaultLabel })}
                </Radio>
              ))}
            </div>
          </Radio.Group>
        </div>

        <div className="rounded border border-border bg-surface px-3 py-2 text-sm text-text-muted">
          <Typography.Text strong className="block !text-text">
            {t('option:notesSearch.notesStudioExcerptLabel', {
              defaultValue: 'Selected excerpt',
            })}
          </Typography.Text>
          <Typography.Paragraph className="!mb-0 whitespace-pre-wrap !text-text-muted">
            {excerptText}
          </Typography.Paragraph>
        </div>

        <div className="flex justify-end gap-2">
          <Button onClick={onClose}>
            {t('common:cancel', { defaultValue: 'Cancel' })}
          </Button>
          <Button type="primary" loading={loading} onClick={onSubmit}>
            {t('option:notesSearch.notesStudioCreateAction', {
              defaultValue: 'Create Notes Studio note',
            })}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default NotesStudioCreateModal
